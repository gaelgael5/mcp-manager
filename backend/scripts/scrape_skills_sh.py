"""Scrape skills.sh catalog → create SkillSources + Skills with summaries.

Usage (inside container):
    python -m scripts.scrape_skills_sh [--limit N] [--skip-summaries]
"""
import asyncio
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
CONCURRENCY = 3  # max parallel detail-page fetches


async def fetch_page(client: httpx.AsyncClient, url: str) -> str | None:
    """Fetch a URL and return HTML text."""
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code == 200:
            return resp.text
        logger.warning("GET %s → %d", url, resp.status_code)
    except httpx.HTTPError as exc:
        logger.error("HTTP error for %s: %s", url, exc)
    return None


def extract_skill_links(html: str) -> list[str]:
    """Extract all skill links from the skills.sh leaderboard page.

    Links look like: /owner/repo/skill-name (3 segments after /).
    """
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Skill links have exactly 3 path segments: /owner/repo/skill
        parts = [p for p in href.strip("/").split("/") if p]
        if len(parts) == 3 and not href.startswith("http"):
            links.add(href)
    return sorted(links)


def parse_skill_detail(html: str, path: str) -> dict | None:
    """Parse a skill detail page and extract all metadata."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) != 3:
        return None
    owner, repo, skill_id = parts

    # Extract GitHub URL
    github_url = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "github.com" in href and owner in href:
            github_url = href.rstrip("/")
            break

    if not github_url:
        github_url = f"https://github.com/{owner}/{repo}"

    # Extract install command — look for "npx skills add" pattern
    install_cmd = None
    match = re.search(r"npx\s+skills?\s+add\s+[^\n]+", text)
    if match:
        install_cmd = match.group(0).strip()
    else:
        install_cmd = f"npx skills add {github_url} --skill {skill_id}"

    # Extract description / summary — usually the first paragraph-like text after the title
    description = None
    # Look for a summary-style text (short paragraph)
    for p in soup.find_all(["p", "div"]):
        t = p.get_text(strip=True)
        if 20 < len(t) < 500 and not t.startswith("npx") and not t.startswith("$"):
            description = t
            break

    # Extract weekly installs
    weekly_installs = 0
    installs_match = re.search(r"([\d,.]+)K?\s*(?:weekly\s*)?installs?", text, re.IGNORECASE)
    if installs_match:
        val = installs_match.group(1).replace(",", "")
        try:
            num = float(val)
            if "K" in (installs_match.group(0)):
                num *= 1000
            weekly_installs = int(num)
        except ValueError:
            pass

    # Extract the main content (SKILL.md body)
    # Usually in a <pre> or large content block
    raw_content = ""
    # Find the largest text block as the skill content
    blocks = []
    for el in soup.find_all(["pre", "code", "article", "section", "div"]):
        t = el.get_text("\n", strip=True)
        if len(t) > 200:
            blocks.append(t)
    if blocks:
        raw_content = max(blocks, key=len)
    if not raw_content:
        raw_content = description or ""

    return {
        "owner": owner,
        "repo": repo,
        "skill_id": skill_id,
        "name": skill_id,
        "description": description,
        "raw_content": raw_content,
        "github_url": github_url,
        "install_command": install_cmd,
        "weekly_installs": weekly_installs,
        "source_url": f"{SKILLS_SH_BASE}/{owner}/{repo}/{skill_id}",
    }


async def scrape_skills_sh(limit: int | None = None, skip_summaries: bool = False):
    """Main scraper: fetch catalog, parse detail pages, upsert into DB."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    logger.info("Fetching skills.sh catalog...")
    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": "MCPManager/1.0"}) as client:
        # Step 1: Get the main page
        main_html = await fetch_page(client, SKILLS_SH_BASE)
        if not main_html:
            logger.error("Failed to fetch skills.sh main page")
            return

        skill_links = extract_skill_links(main_html)
        logger.info("Found %d skill links on main page", len(skill_links))

        if limit:
            skill_links = skill_links[:limit]
            logger.info("Limited to %d skills", limit)

        # Step 2: Fetch detail pages with concurrency control
        semaphore = asyncio.Semaphore(CONCURRENCY)
        parsed_skills: list[dict] = []

        async def fetch_and_parse(link: str):
            async with semaphore:
                url = f"{SKILLS_SH_BASE}{link}"
                html = await fetch_page(client, url)
                if html:
                    skill = parse_skill_detail(html, link)
                    if skill:
                        parsed_skills.append(skill)
                        if len(parsed_skills) % 20 == 0:
                            logger.info("Parsed %d/%d skill pages...", len(parsed_skills), len(skill_links))
                # Small delay to be polite
                await asyncio.sleep(0.5)

        tasks = [fetch_and_parse(link) for link in skill_links]
        await asyncio.gather(*tasks)

        logger.info("Parsed %d skill detail pages", len(parsed_skills))

    # Step 3: Group by repo → create/update SkillSources + Skills
    repos: dict[str, list[dict]] = {}
    for s in parsed_skills:
        key = f"{s['owner']}/{s['repo']}"
        repos.setdefault(key, []).append(s)

    logger.info("Found %d unique repos", len(repos))

    async with SessionLocal() as db:
        total_sources = 0
        total_skills_added = 0
        total_skills_updated = 0

        for repo_key, skills in repos.items():
            github_url = skills[0]["github_url"]

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
                    type="claude",  # skills.sh skills are multi-platform
                )
                db.add(source)
                await db.flush()
                total_sources += 1
                logger.info("Created SkillSource: %s", repo_key)

            # Upsert Skills
            for s in skills:
                result = await db.execute(
                    select(Skill).where(
                        Skill.skill_source_id == source.id,
                        Skill.name == s["name"],
                    )
                )
                skill = result.scalar_one_or_none()
                if skill:
                    skill.description = s["description"]
                    skill.source_url = s["source_url"]
                    skill.install_command = s["install_command"]
                    skill.weekly_installs = s["weekly_installs"]
                    skill.needs_summary = True
                    total_skills_updated += 1
                else:
                    skill = Skill(
                        skill_source_id=source.id,
                        name=s["name"],
                        description=s["description"],
                        target_type="claude",
                        source_url=s["source_url"],
                        install_command=s["install_command"],
                        weekly_installs=s["weekly_installs"],
                        needs_summary=True,
                    )
                    db.add(skill)
                    total_skills_added += 1

            source.last_sync = datetime.now(timezone.utc)
            source.last_sync_count = len(skills)

        await db.commit()
        logger.info(
            "DB upsert done: %d sources, %d skills added, %d updated",
            total_sources, total_skills_added, total_skills_updated,
        )

        # Step 4: Generate summaries
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
