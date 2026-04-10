import asyncio
import logging
from collections import defaultdict

import httpx
from sqlalchemy import select, delete

from mcp_manager.config import settings
from mcp_manager.connectors.github_pool import get_github_headers
from mcp_manager.db.session import SessionLocal
from mcp_manager.db.models import McpService

logger = logging.getLogger(__name__)

# Source priority: lower = higher priority when data is equal
SOURCE_PRIORITY = {
    "docker_registry": 1,
    "mcp_servers_repo": 2,
    "mcp_registry": 3,
    "glama": 4,
    "pulsemcp": 5,
}

CONCURRENCY = 20


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    url = url.strip().rstrip("/").lower()
    # Remove .git suffix
    if url.endswith(".git"):
        url = url[:-4]
    return url


def find_name_match(name_a: str, name_b: str) -> bool:
    """Check if two names refer to the same service (cross-source matching)."""
    if not name_a or not name_b:
        return False

    # Extract repo part from reverse-DNS names
    repo_a = name_a.split("/")[-1] if "/" in name_a else name_a
    repo_b = name_b.split("/")[-1] if "/" in name_b else name_b

    return repo_a == repo_b


async def check_repo_accessible(client: httpx.AsyncClient, url: str) -> bool:
    """HEAD request to check if a GitHub repo exists."""
    if not url or "github.com" not in url:
        return False
    api_url = url.replace("https://github.com/", "https://api.github.com/repos/")
    headers = get_github_headers()
    try:
        resp = await client.get(api_url, headers=headers)
        return resp.status_code == 200
    except Exception:
        return False


def score_service(svc: McpService, repo_ok: bool) -> int:
    """Score a service — higher is better. Used to pick the survivor."""
    score = 0
    if repo_ok:
        score += 1000
    if svc.source_url:
        score += 100
    if svc.category:
        score += 50
    if svc.package_info and svc.package_info != {}:
        score += 40
    if svc.doc_url:
        score += 30
    if svc.tags:
        score += 20
    # Source priority bonus
    score += (10 - SOURCE_PRIORITY.get(svc.source_type, 9))
    return score


async def run_dedup() -> dict[str, int]:
    """Cross-source deduplication. Groups by canonical_id (fallback: normalized source_url), keeps the best entry."""
    stats = {"merged": 0, "checked": 0, "groups": 0, "repo_404": 0}

    async with SessionLocal() as db:
        result = await db.execute(select(McpService).where(McpService.source_url != ""))
        all_services = result.scalars().all()
        logger.info("Dedup: %d services with source_url", len(all_services))

        # Group by canonical_id (preferred) or normalized source_url (fallback for raw:)
        groups: dict[str, list[McpService]] = defaultdict(list)
        for svc in all_services:
            if svc.canonical_id and not svc.canonical_id.startswith("raw:"):
                groups[svc.canonical_id].append(svc)
            else:
                url = normalize_url(svc.source_url)
                if url:
                    groups[url].append(svc)

        # Only process groups with duplicates
        dup_groups = {key: svcs for key, svcs in groups.items() if len(svcs) > 1}
        logger.info("Dedup: %d duplicate groups to process", len(dup_groups))
        stats["groups"] = len(dup_groups)

        # Collect unique source_urls from duplicate groups for repo accessibility check
        urls_to_check: set[str] = set()
        for svcs in dup_groups.values():
            for svc in svcs:
                url = normalize_url(svc.source_url)
                if url and "github.com" in url:
                    urls_to_check.add(url)

        semaphore = asyncio.Semaphore(CONCURRENCY)
        repo_status: dict[str, bool] = {}

        async with httpx.AsyncClient(timeout=10.0) as client:
            async def check_one(url: str):
                async with semaphore:
                    accessible = await check_repo_accessible(client, url)
                    repo_status[url] = accessible
                    if not accessible:
                        stats["repo_404"] += 1
                    stats["checked"] += 1
                    if stats["checked"] % 100 == 0:
                        logger.info("Dedup: checked %d/%d repos", stats["checked"], len(urls_to_check))

            await asyncio.gather(*[check_one(u) for u in urls_to_check])

        # Merge each group
        for key, svcs in dup_groups.items():
            # Check repo status using the first service's source_url
            first_url = normalize_url(svcs[0].source_url)
            repo_ok = repo_status.get(first_url, False)

            # Score each service
            scored = [(score_service(svc, repo_ok), svc) for svc in svcs]
            scored.sort(key=lambda x: x[0], reverse=True)

            survivor = scored[0][1]
            losers = [s[1] for s in scored[1:]]

            # Enrich survivor from losers
            for loser in losers:
                if not survivor.category and loser.category:
                    survivor.category = loser.category
                if not survivor.doc_url and loser.doc_url:
                    survivor.doc_url = loser.doc_url
                if (not survivor.package_info or survivor.package_info == {}) and loser.package_info:
                    survivor.package_info = loser.package_info
                if not survivor.tags and loser.tags:
                    survivor.tags = loser.tags
                if loser.branch_hash and (not survivor.branch_hash or loser.branch_hash > survivor.branch_hash):
                    survivor.branch_hash = loser.branch_hash

            # Track origins
            origins = set(survivor.source_origins or [])
            origins.add(survivor.source_type)
            for loser in losers:
                origins.add(loser.source_type)
            survivor.source_origins = list(origins)

            # Update repo_status and canonical_id on survivor
            survivor.repo_status = "ok" if repo_ok else "404"
            if key.startswith(("github:", "npm:", "pypi:")):
                survivor.canonical_id = key

            # Delete losers
            for loser in losers:
                await db.execute(delete(McpService).where(McpService.id == loser.id))
                stats["merged"] += 1

            logger.debug(
                "Kept %s (%s, score=%d), merged %d duplicates",
                survivor.name, survivor.source_type, scored[0][0], len(losers),
            )

        await db.commit()

    logger.info(
        "Dedup done: %d groups, %d merged, %d repos 404",
        stats["groups"], stats["merged"], stats["repo_404"],
    )
    return stats
