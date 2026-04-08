"""Generate skill_sources CSV by scraping skills.sh pages.

Reads backend/data/skills_sh_dump.csv, scrapes each skill page for
repo_url, targets (type), and description, then writes
backend/data/skill_sources_export.csv.

Usage:
    python scripts/generate_skill_sources_csv.py [--limit N] [--concurrency N]
"""
import argparse
import asyncio
import csv
import json
import logging
import os
import re
import sys
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INPUT_CSV = DATA_DIR / "skills_sh_dump.csv"
OUTPUT_CSV = DATA_DIR / "skill_sources_export.csv"

SKILLS_SH_BASE = "https://skills.sh"

FIELDNAMES = [
    "name", "url", "repo_url", "skills_path", "type",
    "description", "is_active", "stars",
]


def _parse_page(html: str, source: str) -> dict:
    """Extract repo_url, targets, and description from raw HTML."""
    result = {"repo_url": None, "type": "", "description": ""}

    # --- Try __NEXT_DATA__ JSON first (Next.js apps embed page props) ---
    nd_match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
    )
    if nd_match:
        try:
            nd = json.loads(nd_match.group(1))
            props = nd.get("props", {}).get("pageProps", {})
            skill_data = props.get("skill") or props.get("data") or {}

            if isinstance(skill_data, dict):
                repo = skill_data.get("repoUrl") or skill_data.get("repo_url") or skill_data.get("repository")
                if repo:
                    result["repo_url"] = repo

                desc = skill_data.get("summary") or skill_data.get("description") or ""
                if desc:
                    result["description"] = desc.strip()

                targets = skill_data.get("installedOn") or skill_data.get("targets") or []
                if isinstance(targets, list):
                    result["type"] = "|".join(t if isinstance(t, str) else t.get("name", "") for t in targets)
        except (json.JSONDecodeError, AttributeError):
            pass

    # --- Fallback: regex on raw HTML text ---
    # Strip tags for text-based extraction
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)

    # repo_url from "npx skills add <URL>"
    if not result["repo_url"]:
        m = re.search(r"npx\s+skills\s+add\s+(https?://[^\s\"'<]+)", text)
        result["repo_url"] = m.group(1) if m else f"https://github.com/{source}"

    # targets from "Installed On" / "installed on" section
    if not result["type"]:
        known_platforms = [
            "opencode", "codex", "gemini-cli", "github-copilot",
            "amp", "kimi-cli", "claude", "cursor", "windsurf",
            "cline", "roo-code", "zed", "vscode",
        ]
        found = [p for p in known_platforms if re.search(rf"\b{re.escape(p)}\b", text, re.IGNORECASE)]
        result["type"] = "|".join(found) if found else ""

    # description from summary block
    if not result["description"]:
        # Try to grab text after "Summary" heading or the first substantial paragraph
        m = re.search(r"(?:Summary|SUMMARY)[:\s]*([^<]{20,2000})", text)
        if m:
            result["description"] = m.group(1).strip()

    return result


async def _scrape_one(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    source: str,
    skill_id: str,
    installs: str,
) -> dict | None:
    """Scrape a single skills.sh page and return a row dict."""
    name = f"{source}/{skill_id}"
    url = f"{SKILLS_SH_BASE}/{source}/{skill_id}"

    async with sem:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning("HTTP %d for %s", resp.status_code, url)
                return {
                    "name": name, "url": url,
                    "repo_url": f"https://github.com/{source}",
                    "skills_path": "", "type": "", "description": "",
                    "is_active": "true", "stars": "",
                }
            parsed = _parse_page(resp.text, source)
            return {
                "name": name,
                "url": url,
                "repo_url": parsed["repo_url"],
                "skills_path": "",
                "type": parsed["type"],
                "description": parsed["description"],
                "is_active": "true",
                "stars": "",
            }
        except Exception as exc:
            logger.error("Error scraping %s: %s", url, exc)
            return {
                "name": name, "url": url,
                "repo_url": f"https://github.com/{source}",
                "skills_path": "", "type": "", "description": "",
                "is_active": "true", "stars": "",
            }
        finally:
            await asyncio.sleep(0.1)


async def main(limit: int | None = None, concurrency: int = 10):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    # --- Read input CSV ---
    rows = []
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    logger.info("Read %d entries from %s", len(rows), INPUT_CSV)

    if limit:
        rows = rows[:limit]
        logger.info("Limited to %d entries", limit)

    # --- Resume: load already-scraped URLs ---
    done_urls: set[str] = set()
    existing_rows: list[dict] = []
    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_rows.append(row)
                done_urls.add(row["url"])
        logger.info("Resuming: %d entries already scraped", len(done_urls))

    # --- Scrape ---
    sem = asyncio.Semaphore(concurrency)
    results = list(existing_rows)
    todo = [r for r in rows if f"{SKILLS_SH_BASE}/{r['source']}/{r['skillId']}" not in done_urls]
    logger.info("To scrape: %d entries", len(todo))

    if not todo:
        logger.info("Nothing to scrape, all done")
        return

    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": "MCPManager/1.0"},
        follow_redirects=True,
    ) as client:
        tasks = [
            _scrape_one(client, sem, r["source"], r["skillId"], r.get("installs", "0"))
            for r in todo
        ]
        done_count = 0
        errors = 0
        batch_size = 100

        for i in range(0, len(tasks), batch_size):
            batch = tasks[i : i + batch_size]
            batch_results = await asyncio.gather(*batch)

            for row in batch_results:
                if row:
                    results.append(row)
                    if not row["description"] and not row["type"]:
                        errors += 1
                    done_count += 1

            # Write progress after each batch
            with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerows(results)

            logger.info(
                "Progress: %d/%d scraped (batch %d)",
                done_count, len(todo), i // batch_size + 1,
            )

    logger.info(
        "Done: %d total rows, %d with missing data",
        len(results), errors,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate skill_sources CSV from skills.sh")
    parser.add_argument("--limit", type=int, default=None, help="Max entries to scrape")
    parser.add_argument("--concurrency", type=int, default=10, help="Max concurrent requests")
    args = parser.parse_args()

    asyncio.run(main(limit=args.limit, concurrency=args.concurrency))
