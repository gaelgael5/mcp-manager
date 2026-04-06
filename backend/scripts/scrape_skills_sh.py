"""Scrape skills.sh catalog → create SkillSources + Skills with summaries.

Strategy:
1. Fetch RSC data from /, /trending, /hot pages → extract {source, skillId, name, installs}
2. For each unique repo, fetch the repo page to discover additional skills
3. For each skill, build the install command
4. Upsert into DB as SkillSources + Skills
5. Optionally generate summaries via Ollama

Usage (inside container):
    python -m scripts.scrape_skills_sh [--limit N] [--skip-summaries]
"""
import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from mcp_manager.db.session import SessionLocal
from mcp_manager.db.models import SkillSource, Skill

logger = logging.getLogger(__name__)

SKILLS_SH_BASE = "https://skills.sh"
CONCURRENCY = 5


async def fetch_page(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code == 200:
            return resp.text
        logger.warning("GET %s → %d", url, resp.status_code)
    except httpx.HTTPError as exc:
        logger.error("HTTP error for %s: %s", url, exc)
    return None


def extract_rsc_skills(html: str) -> list[dict]:
    """Extract skill entries from Next.js RSC __next_f data chunks."""
    # Collect all __next_f script content
    soup = BeautifulSoup(html, "html.parser")
    chunks = []
    for script in soup.find_all("script"):
        text = script.string or ""
        if "__next_f" in text:
            chunks.append(text)

    all_text = "".join(chunks)

    # Unescape double-escaped JSON
    unescaped = all_text.replace('\\"', '"')

    # Extract skill objects with regex
    pattern = r'\{"source":"([^"]+)","skillId":"([^"]+)","name":"([^"]+)","installs":(\d+)\}'
    skills = []
    for m in re.finditer(pattern, unescaped):
        skills.append({
            "source": m.group(1),
            "skillId": m.group(2),
            "name": m.group(3),
            "installs": int(m.group(4)),
        })

    return skills


def extract_html_skill_links(html: str) -> list[str]:
    """Extract /owner/repo/skill links from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        parts = [p for p in href.strip("/").split("/") if p]
        if len(parts) == 3 and not href.startswith("http"):
            links.add(href)
    return sorted(links)


def extract_repo_skills_from_page(html: str, owner: str, repo: str) -> list[dict]:
    """Extract skills from a repo page (/owner/repo)."""
    skills = extract_rsc_skills(html)
    if skills:
        return skills

    # Fallback: parse HTML links
    links = extract_html_skill_links(html)
    result = []
    for link in links:
        parts = [p for p in link.strip("/").split("/") if p]
        if len(parts) == 3 and parts[0] == owner and parts[1] == repo:
            result.append({
                "source": f"{owner}/{repo}",
                "skillId": parts[2],
                "name": parts[2],
                "installs": 0,
            })
    return result


async def scrape_skills_sh(limit: int | None = None, skip_summaries: bool = False):
    """Main scraper."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    all_skills: dict[str, dict] = {}  # key = "source/skillId"

    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": "MCPManager/1.0"}) as client:
        # ── Step 1: Fetch leaderboard pages and extract RSC data ──
        pages = ["/", "/trending", "/hot"]
        for page_path in pages:
            url = f"{SKILLS_SH_BASE}{page_path}"
            logger.info("Fetching %s ...", url)
            html = await fetch_page(client, url)
            if not html:
                continue

            skills = extract_rsc_skills(html)
            # Also get HTML links as fallback
            links = extract_html_skill_links(html)
            for link in links:
                parts = [p for p in link.strip("/").split("/") if p]
                if len(parts) == 3:
                    key = f"{parts[0]}/{parts[1]}/{parts[2]}"
                    if key not in all_skills:
                        all_skills[key] = {
                            "source": f"{parts[0]}/{parts[1]}",
                            "skillId": parts[2],
                            "name": parts[2],
                            "installs": 0,
                        }

            for s in skills:
                key = f"{s['source']}/{s['skillId']}"
                if key not in all_skills or s["installs"] > all_skills[key]["installs"]:
                    all_skills[key] = s

            logger.info("  → %d skills from RSC, %d HTML links, total unique: %d",
                        len(skills), len(links), len(all_skills))

        # ── Step 2: Discover repos and fetch each repo page ──
        repos = set(s["source"] for s in all_skills.values())
        logger.info("Found %d unique repos, fetching repo pages...", len(repos))

        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def fetch_repo(repo_key: str):
            async with semaphore:
                url = f"{SKILLS_SH_BASE}/{repo_key}"
                html = await fetch_page(client, url)
                if not html:
                    return
                owner, repo_name = repo_key.split("/", 1)
                repo_skills = extract_repo_skills_from_page(html, owner, repo_name)
                for s in repo_skills:
                    key = f"{s['source']}/{s['skillId']}"
                    if key not in all_skills:
                        all_skills[key] = s
                await asyncio.sleep(0.3)

        await asyncio.gather(*[fetch_repo(r) for r in repos])
        logger.info("After repo pages: %d total unique skills", len(all_skills))

    # ── Step 3: Apply limit ──
    skills_list = sorted(all_skills.values(), key=lambda s: s["installs"], reverse=True)
    if limit:
        skills_list = skills_list[:limit]
        logger.info("Limited to %d skills", limit)

    # ── Step 4: Upsert into DB ──
    # Group by repo
    repos_map: dict[str, list[dict]] = {}
    for s in skills_list:
        repos_map.setdefault(s["source"], []).append(s)

    logger.info("Upserting %d skills from %d repos...", len(skills_list), len(repos_map))

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

            # Upsert Skills
            for s in skills:
                install_cmd = f"npx skills add {github_url} --skill {s['skillId']}"

                result = await db.execute(
                    select(Skill).where(
                        Skill.skill_source_id == source.id,
                        Skill.name == s["name"],
                    )
                )
                skill = result.scalar_one_or_none()
                if skill:
                    skill.install_command = install_cmd
                    skill.weekly_installs = s["installs"]
                    skill.source_url = f"{SKILLS_SH_BASE}/{s['source']}/{s['skillId']}"
                    skill.needs_summary = skill.needs_summary or not skill.summary_en
                    total_updated += 1
                else:
                    skill = Skill(
                        skill_source_id=source.id,
                        name=s["name"],
                        description=None,
                        target_type="claude",
                        source_url=f"{SKILLS_SH_BASE}/{s['source']}/{s['skillId']}",
                        install_command=install_cmd,
                        weekly_installs=s["installs"],
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

        # ── Step 5: Generate summaries ──
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
