"""Scrape skills.sh catalog via their paginated API → create SkillSources.

API: GET /api/skills/all-time/{page} → { skills: [...], total, hasMore, page }
Each entry = one SkillSource with its install command.
250 entries per page, no auth required.

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
from mcp_manager.db.models import SkillSource

logger = logging.getLogger(__name__)

SKILLS_SH_BASE = "https://skills.sh"
API_URL = f"{SKILLS_SH_BASE}/api/skills/all-time"


async def scrape_skills_sh(limit: int | None = None, skip_summaries: bool = False):
    """Main scraper: paginate the API, upsert SkillSources."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    all_entries: list[dict] = []
    page = 0

    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": "MCPManager/1.0"}) as client:
        while True:
            url = f"{API_URL}/{page}"
            logger.info("Fetching page %d ...", url)

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

    logger.info("Fetched %d skill sources from %d pages", len(all_entries), page + 1)

    if not all_entries:
        logger.warning("No entries fetched, aborting")
        return

    # Each entry = one SkillSource
    async with SessionLocal() as db:
        total_added = 0
        total_updated = 0

        for i, entry in enumerate(all_entries):
            source_key = entry["source"]  # "owner/repo"
            skill_id = entry["skillId"]
            name = entry.get("name", skill_id)
            installs = entry.get("installs", 0)

            # URL unique per skill source = the skills.sh page
            skills_sh_url = f"{SKILLS_SH_BASE}/{source_key}/{skill_id}"
            github_url = f"https://github.com/{source_key}"
            install_cmd = f"npx skills add {github_url} --skill {skill_id}"

            result = await db.execute(
                select(SkillSource).where(SkillSource.url == skills_sh_url)
            )
            source = result.scalar_one_or_none()
            if source:
                source.name = name
                source.description = install_cmd
                source.repo_url = github_url
                total_updated += 1
            else:
                source = SkillSource(
                    name=name,
                    url=skills_sh_url,
                    repo_url=github_url,
                    skills_path=install_cmd,
                    type="claude",
                )
                db.add(source)
                total_added += 1

            # Commit in batches
            if (i + 1) % 500 == 0:
                await db.commit()
                logger.info("Progress: %d/%d (added: %d, updated: %d)",
                            i + 1, len(all_entries), total_added, total_updated)

        source_obj = None  # clear ref
        await db.commit()
        logger.info(
            "DB upsert done: %d added, %d updated (total: %d)",
            total_added, total_updated, total_added + total_updated,
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape skills.sh catalog")
    parser.add_argument("--limit", type=int, default=None, help="Max entries to scrape")
    parser.add_argument("--skip-summaries", action="store_true", help="Skip summary generation")
    args = parser.parse_args()

    asyncio.run(scrape_skills_sh(limit=args.limit, skip_summaries=args.skip_summaries))
