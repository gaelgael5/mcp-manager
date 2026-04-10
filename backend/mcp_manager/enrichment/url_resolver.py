import asyncio
import logging
import re

import httpx

from mcp_manager.config import settings
from mcp_manager.connectors.github_pool import get_github_headers

logger = logging.getLogger(__name__)


def parse_reverse_dns_to_github_url(name: str) -> str | None:
    if not name or "/" not in name:
        return None

    parts = name.split("/", 1)
    if len(parts) != 2:
        return None

    prefix = parts[0]
    repo = parts[1]

    match = re.match(r"^io\.github\.(.+)$", prefix)
    if match:
        owner = match.group(1)
        return f"https://github.com/{owner}/{repo}"

    domain_match = re.match(r"^(?:com|ai|net|org|io|dev)\.(.+)$", prefix)
    if domain_match:
        domain = domain_match.group(1)
        return f"https://github.com/{domain}/{repo}"

    return None


async def verify_github_url(client: httpx.AsyncClient, url: str) -> bool:
    headers = get_github_headers()
    try:
        api_url = url.replace("https://github.com/", "https://api.github.com/repos/")
        resp = await client.get(api_url, headers=headers)
        return resp.status_code == 200
    except Exception:
        return False


async def run_url_resolve() -> dict[str, int]:
    from sqlalchemy import select
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import McpService

    stats = {"resolved": 0, "not_found": 0, "skipped": 0}
    semaphore = asyncio.Semaphore(10)

    async with SessionLocal() as db:
        result = await db.execute(
            select(McpService).where(McpService.source_url == "")
        )
        services = result.scalars().all()
        logger.info("URL resolve: %d services without source_url", len(services))

        async with httpx.AsyncClient(timeout=15.0) as client:
            for service in services:
                candidate = parse_reverse_dns_to_github_url(service.name)
                if not candidate:
                    stats["skipped"] += 1
                    continue

                async with semaphore:
                    exists = await verify_github_url(client, candidate)

                if exists:
                    service.source_url = candidate
                    if not service.doc_url:
                        service.doc_url = candidate
                    # Recompute canonical_id now that we have a source_url
                    from mcp_manager.enrichment.canonical import compute_canonical_id
                    pkg = service.package_info or {}
                    service.canonical_id = compute_canonical_id(
                        source_url=candidate,
                        package_identifier=pkg.get("package_identifier"),
                        registry_type=pkg.get("registry_type"),
                        source_type=service.source_type,
                        name=service.name,
                    )
                    stats["resolved"] += 1
                    logger.debug("Resolved: %s -> %s", service.name, candidate)
                else:
                    stats["not_found"] += 1
                    logger.debug("Not found: %s -> %s", service.name, candidate)

        await db.commit()

    logger.info("URL resolve done: %d resolved, %d not found, %d skipped", stats["resolved"], stats["not_found"], stats["skipped"])
    return stats
