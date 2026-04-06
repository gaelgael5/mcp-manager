"""Scrape skills.sh catalog via their paginated API → create SkillSources + Skills.

API: GET /api/skills/all-time/{page} → { skills: [...], total, hasMore, page }
Each skill: { source, skillId, name, installs }
250 skills per page, no auth required.

Usage (inside container):
    python -m scripts.scrape_skills_sh [--limit N] [--skip-summaries]
"""
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from mcp_manager.db.session import SessionLocal
from mcp_manager.db.models import SkillSource, Skill

logger = logging.getLogger(__name__)

SKILLS_SH_BASE = "https://skills.sh"
API_URL = f"{SKILLS_SH_BASE}/api/skills/all-time"
PAGE_SIZE = 250


async def scrape_skills_sh(limit: int | None = None, skip_summaries: bool = False):
    """Main scraper: paginate the API, upsert into DB."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    all_skills: list[dict] = []
    page = 0

    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": "MCPManager/1.0"}) as client:
        while True:
            url = f"{API_URL}/{page}"
            logger.info("Fetching page %d (%s) ...", page, url)

            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.error("API returned %d on page %d", resp.status_code, page)
                    break
            except httpx.HTTPError as exc:
                logger.error("HTTP error on page %d: %s", page, exc)
                break

            data = resp.json()
            skills = data.get("skills", [])
            has_more = data.get("hasMore", False)

            if not skills:
                break

            all_skills.extend(skills)
            logger.info("  → %d skills (total so far: %d)", len(skills), len(all_skills))

            if limit and len(all_skills) >= limit:
                all_skills = all_skills[:limit]
                break

            if not has_more:
                break

            page += 1
            await asyncio.sleep(0.3)

    logger.info("Fetched %d skills from %d pages", len(all_skills), page + 1)

    if not all_skills:
        logger.warning("No skills fetched, aborting")
        return

    # Group by repo
    repos_map: dict[str, list[dict]] = {}
    for s in all_skills:
        repos_map.setdefault(s["source"], []).append(s)

    logger.info("Upserting %d skills from %d repos...", len(all_skills), len(repos_map))

    async with SessionLocal() as db:
        total_sources = 0
        total_added = 0
        total_updated = 0

        for repo_key, skills in repos_map.items():
            github_url = f"https://github.com/{repo_key}"

            # Upsert SkillSource
            result = await db.execute(
                select(SkillSource).where(SkillSource.url == github_url)
            )
            source = result.scalar_one_or_none()
            if not source:
                source = SkillSource(
                    name=repo_key,
                    url=github_url,
                    skills_path="",
                    type="claude",
                )
                db.add(source)
                await db.flush()
                total_sources += 1

            for s in skills:
                install_cmd = f"npx skills add {github_url} --skill {s['skillId']}"
                source_url = f"{SKILLS_SH_BASE}/{s['source']}/{s['skillId']}"

                result = await db.execute(
                    select(Skill).where(
                        Skill.skill_source_id == source.id,
                        Skill.name == s["name"],
                    )
                )
                skill = result.scalar_one_or_none()
                if skill:
                    skill.install_command = install_cmd
                    skill.weekly_installs = s.get("installs", 0)
                    skill.source_url = source_url
                    skill.needs_summary = skill.needs_summary or not skill.summary_en
                    total_updated += 1
                else:
                    skill = Skill(
                        skill_source_id=source.id,
                        name=s["name"],
                        description=None,
                        target_type="claude",
                        source_url=source_url,
                        install_command=install_cmd,
                        weekly_installs=s.get("installs", 0),
                        needs_summary=True,
                    )
                    db.add(skill)
                    total_added += 1

            source.last_sync = datetime.now(timezone.utc)
            source.last_sync_count = len(skills)

        await db.commit()
        logger.info(
            "DB upsert done: %d sources, %d added, %d updated",
            total_sources, total_added, total_updated,
        )

        if not skip_summaries:
            await _generate_summaries(db)


async def _generate_summaries(db):
    """Generate EN/FR summaries for skills that need them."""
    from mcp_manager.summarizer.ollama_client import ollama_generate
    from mcp_manager.summarizer.cleaner import clean_markdown

    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")

    result = await db.execute(
        select(Skill).where(Skill.needs_summary == True).limit(500)
    )
    skills = result.scalars().all()
    logger.info("Generating summaries for %d skills...", len(skills))

    count = 0
    for skill in skills:
        content = skill.description or skill.name
        cleaned = clean_markdown(content)
        if not cleaned or len(cleaned) < 10:
            skill.needs_summary = False
            continue

        if len(cleaned) > 8000:
            cleaned = cleaned[:8000]

        try:
            with open(os.path.join(prompts_dir, "skill_summary_en.md"), encoding="utf-8") as f:
                prompt_en = f.read().replace("{content}", cleaned)
            skill.summary_en = await ollama_generate(prompt_en)
        except Exception:
            logger.exception("EN summary failed for %s", skill.name)

        try:
            with open(os.path.join(prompts_dir, "skill_summary_fr.md"), encoding="utf-8") as f:
                prompt_fr = f.read().replace("{content}", cleaned)
            skill.summary_fr = await ollama_generate(prompt_fr)
        except Exception:
            logger.exception("FR summary failed for %s", skill.name)

        skill.needs_summary = False
        count += 1

        if count % 10 == 0:
            await db.commit()
            logger.info("Summaries: %d/%d done", count, len(skills))

    await db.commit()
    logger.info("Summary generation complete: %d skills", count)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape skills.sh catalog")
    parser.add_argument("--limit", type=int, default=None, help="Max skills to scrape")
    parser.add_argument("--skip-summaries", action="store_true", help="Skip summary generation")
    args = parser.parse_args()

    asyncio.run(scrape_skills_sh(limit=args.limit, skip_summaries=args.skip_summaries))
