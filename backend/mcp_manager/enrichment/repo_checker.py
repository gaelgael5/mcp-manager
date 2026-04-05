"""Passe: verify repo accessibility for all services with source_url."""
import asyncio
import logging

import httpx

from mcp_manager.config import settings
from mcp_manager.db.session import SessionLocal
from mcp_manager.db.models import McpService
from sqlalchemy import select

logger = logging.getLogger(__name__)

CONCURRENCY = 10  # Stay well under 5000/h with token


async def check_repo(client: httpx.AsyncClient, url: str) -> bool:
    if not url or "github.com" not in url:
        return False
    api_url = url.replace("https://github.com/", "https://api.github.com/repos/")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if settings.github_token:
        headers["Authorization"] = f"token {settings.github_token}"
    try:
        resp = await client.get(api_url, headers=headers)
        # Respect rate limit
        remaining = int(resp.headers.get("x-ratelimit-remaining", "100"))
        if remaining < 50:
            reset_at = int(resp.headers.get("x-ratelimit-reset", "0"))
            import time
            wait = max(0, reset_at - int(time.time())) + 5
            logger.warning("Rate limit low (%d remaining), waiting %ds", remaining, wait)
            await asyncio.sleep(wait)
        return resp.status_code == 200
    except Exception:
        return False


async def run_repo_check() -> dict[str, int]:
    stats = {"checked": 0, "ok": 0, "not_found": 0}

    # Process in small batches to avoid OOM
    batch_size = 50
    offset = 0

    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            async with SessionLocal() as db:
                result = await db.execute(
                    select(McpService.id, McpService.source_url)
                    .where(
                        McpService.source_url != "",
                        McpService.repo_status.is_(None),
                    )
                    .limit(batch_size)
                )
                rows = result.all()
                if not rows:
                    break

                for svc_id, source_url in rows:
                    ok = await check_repo(client, source_url)
                    status = "ok" if ok else "404"
                    await db.execute(
                        McpService.__table__.update()
                        .where(McpService.id == svc_id)
                        .values(repo_status=status)
                    )
                    if ok:
                        stats["ok"] += 1
                    else:
                        stats["not_found"] += 1
                    stats["checked"] += 1

                await db.commit()
                logger.info(
                    "Repo check: %d checked (ok: %d, 404: %d)",
                    stats["checked"], stats["ok"], stats["not_found"],
                )

    logger.info(
        "Repo check done: %d checked, %d ok, %d not found",
        stats["checked"], stats["ok"], stats["not_found"],
    )
    return stats
