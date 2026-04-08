"""Import skill_sources_export.csv into the skill_sources table.

Upserts rows based on url (unique key). Skips rows that already exist
with the same url, updates them if data has changed.

Usage (inside container):
    python -m scripts.import_skill_sources_csv [--dry-run]
"""
import asyncio
import csv
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from mcp_manager.db.session import SessionLocal
from mcp_manager.db.models import SkillSource

logger = logging.getLogger(__name__)

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "skill_sources_export.csv"


async def import_csv(dry_run: bool = False):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not CSV_PATH.exists():
        logger.error("CSV not found: %s", CSV_PATH)
        return

    # Read CSV
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    logger.info("Read %d rows from CSV", len(rows))

    async with SessionLocal() as db:
        # Load existing sources by url and repo_url
        result = await db.execute(select(SkillSource))
        all_existing = result.scalars().all()
        existing_by_url = {s.url: s for s in all_existing}
        used_repo_urls: set[str] = {s.repo_url for s in all_existing if s.repo_url}
        logger.info("Existing skill_sources in DB: %d", len(existing_by_url))

        stats = {"created": 0, "updated": 0, "skipped": 0}

        for row in rows:
            url = row.get("url", "").strip()
            if not url:
                stats["skipped"] += 1
                continue

            name = row.get("name", "").strip()
            repo_url = row.get("repo_url", "").strip() or None
            skills_path = row.get("skills_path", "").strip()
            type_val = row.get("type", "").strip()
            description = row.get("description", "").strip() or None
            is_active = row.get("is_active", "true").strip().lower() == "true"
            stars_raw = row.get("stars", "").strip()
            stars = int(stars_raw) if stars_raw.isdigit() else None

            # Avoid unique constraint violation on repo_url
            if repo_url and repo_url in used_repo_urls:
                repo_url = None
            if repo_url:
                used_repo_urls.add(repo_url)

            source = existing_by_url.get(url)

            if source:
                # Update fields that are empty in DB but present in CSV
                changed = False
                if not source.repo_url and repo_url:
                    source.repo_url = repo_url
                    changed = True
                if not source.type and type_val:
                    source.type = type_val
                    changed = True
                if not source.description and description:
                    source.description = description
                    changed = True
                if stars is not None and source.stars is None:
                    source.stars = stars
                    changed = True

                if changed:
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
            else:
                new_source = SkillSource(
                    name=name,
                    url=url,
                    repo_url=repo_url,
                    skills_path=skills_path,
                    type=type_val or "unknown",
                    description=description,
                    is_active=is_active,
                    stars=stars,
                )
                db.add(new_source)
                existing_by_url[url] = new_source
                stats["created"] += 1

        if dry_run:
            logger.info("DRY RUN — rolling back")
            await db.rollback()
        else:
            await db.commit()
            logger.info("Committed to database")

        logger.info(
            "Done: %d created, %d updated, %d skipped",
            stats["created"], stats["updated"], stats["skipped"],
        )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Import skill_sources CSV into DB")
    parser.add_argument("--dry-run", action="store_true", help="Don't commit, just preview")
    args = parser.parse_args()

    asyncio.run(import_csv(dry_run=args.dry_run))
