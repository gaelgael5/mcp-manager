"""Scrape skills.sh catalog via their paginated API → create SkillSources + Skills.

API: GET /api/skills/all-time/{page} → { skills: [...], total, hasMore, page }
Each entry = one Skill linked to a SkillSource (one per repo).
250 entries per page, no auth required.

Usage (inside container):
    python -m scripts.scrape_skills_sh [--limit N] [--skip-summaries]
"""
import asyncio
import logging
import os
import sys
from collections import defaultdict

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from mcp_manager.db.session import SessionLocal
from mcp_manager.db.models import SkillSource, Skill, skill_source_skills
from mcp_manager.enrichment.canonical import compute_skill_canonical_id

logger = logging.getLogger(__name__)

SKILLS_SH_BASE = "https://skills.sh"
API_URL = f"{SKILLS_SH_BASE}/api/skills/all-time"


async def _fetch_all_entries(client: httpx.AsyncClient, limit: int | None = None) -> list[dict]:
    """Paginate the skills.sh API until hasMore=false."""
    all_entries: list[dict] = []
    page = 0

    while True:
        url = f"{API_URL}/{page}"
        logger.info("Fetching page %d ...", page)

        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.error("API returned %d on page %d", resp.status_code, page)
                break
        except httpx.HTTPError as exc:
            logger.error("HTTP error on page %d: %s", page, exc)
            break

        data = resp.json()
        entries = data.get("skills", [])
        has_more = data.get("hasMore", False)

        if not entries:
            break

        all_entries.extend(entries)
        logger.info("  → %d entries (total so far: %d)", len(entries), len(all_entries))

        if limit and len(all_entries) >= limit:
            all_entries = all_entries[:limit]
            break

        if not has_more:
            break

        page += 1
        await asyncio.sleep(0.3)

    return all_entries


async def scrape_skills_sh(limit: int | None = None, skip_summaries: bool = False):
    """Main scraper: paginate the API, upsert SkillSources + Skills."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": "MCPManager/1.0"}) as client:
        all_entries = await _fetch_all_entries(client, limit)

    logger.info("Fetched %d skill entries total", len(all_entries))
    if not all_entries:
        logger.warning("No entries fetched, aborting")
        return

    # Group by repo (source)
    by_repo: dict[str, list[dict]] = defaultdict(list)
    for entry in all_entries:
        by_repo[entry["source"]].append(entry)

    logger.info("Grouped into %d unique repos", len(by_repo))

    async with SessionLocal() as db:
        # Pre-load existing SkillSources by repo_url
        result = await db.execute(select(SkillSource))
        existing_sources = {s.repo_url: s for s in result.scalars().all() if s.repo_url}

        # Pre-load existing Skills by canonical_id
        result = await db.execute(select(Skill))
        existing_skills = {s.canonical_id: s for s in result.scalars().all() if s.canonical_id}

        # Pre-load existing links
        result = await db.execute(select(skill_source_skills))
        existing_links: set[tuple] = {(r[0], r[1]) for r in result}

        stats = {"sources_created": 0, "sources_updated": 0, "skills_created": 0, "skills_updated": 0, "links_created": 0}

        for repo_key, entries in by_repo.items():
            github_url = f"https://github.com/{repo_key}"
            skills_sh_url = f"https://skills.sh/{repo_key}"
            total_installs = sum(e.get("installs", 0) for e in entries)

            # Find or create SkillSource
            source = existing_sources.get(github_url)
            if not source:
                source = SkillSource(
                    name=repo_key.split("/")[-1],
                    url=skills_sh_url,
                    repo_url=github_url,
                    skills_path="skills",
                    type="claude",
                )
                db.add(source)
                await db.flush()
                existing_sources[github_url] = source
                stats["sources_created"] += 1
            else:
                # Update URL to skills.sh if it was a plain github URL
                if source.url == github_url:
                    source.url = skills_sh_url
                stats["sources_updated"] += 1

            # Create/update Skills for this repo
            for entry in entries:
                skill_name = entry.get("name", entry["skillId"])
                installs = entry.get("installs", 0)
                skill_url = f"https://github.com/{repo_key}"
                cid = compute_skill_canonical_id(source_url=skill_url, name=skill_name)
                install_cmd = f"npx skills add {github_url} --skill {entry['skillId']}"

                skill = existing_skills.get(cid)
                if not skill:
                    skill = Skill(
                        name=skill_name,
                        target_type="claude",
                        source_url=f"https://github.com/{repo_key}/tree/main/skills/{entry['skillId']}",
                        install_command=install_cmd,
                        weekly_installs=installs,
                        canonical_id=cid,
                        needs_summary=True,
                    )
                    db.add(skill)
                    await db.flush()
                    existing_skills[cid] = skill
                    stats["skills_created"] += 1
                else:
                    skill.weekly_installs = installs
                    if not skill.install_command:
                        skill.install_command = install_cmd
                    stats["skills_updated"] += 1

                # Link skill ↔ source
                link_key = (source._id, skill._id)
                if link_key not in existing_links:
                    await db.execute(
                        skill_source_skills.insert().values(
                            source_pid=source._id, skill_pid=skill._id
                        )
                    )
                    existing_links.add(link_key)
                    stats["links_created"] += 1

        await db.commit()
        logger.info(
            "Done: %d sources created, %d updated | %d skills created, %d updated | %d links created",
            stats["sources_created"], stats["sources_updated"],
            stats["skills_created"], stats["skills_updated"],
            stats["links_created"],
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape skills.sh catalog")
    parser.add_argument("--limit", type=int, default=None, help="Max entries to scrape")
    parser.add_argument("--skip-summaries", action="store_true", help="Skip summary generation")
    args = parser.parse_args()

    asyncio.run(scrape_skills_sh(limit=args.limit, skip_summaries=args.skip_summaries))
