"""Passe: verify repo accessibility and fetch GitHub stars."""
import asyncio
import logging

import httpx

from mcp_manager.config import settings
from mcp_manager.connectors.github_pool import get_github_headers
from mcp_manager.db.session import SessionLocal
from mcp_manager.db.models import McpService, SkillSource
from sqlalchemy import select

logger = logging.getLogger(__name__)

CONCURRENCY = 10


class RateLimitExhausted(Exception):
    def __init__(self, remaining: int):
        self.remaining = remaining


async def check_repo(client: httpx.AsyncClient, url: str) -> tuple[bool, int | None]:
    """Check repo accessibility and return (ok, stars)."""
    if not url or "github.com" not in url:
        return False, None
    api_url = url.replace("https://github.com/", "https://api.github.com/repos/")
    headers = get_github_headers()
    try:
        resp = await client.get(api_url, headers=headers)
        remaining = int(resp.headers.get("x-ratelimit-remaining", "100"))
        if remaining < 20:
            logger.warning("Rate limit low (%d remaining), stopping. Re-run later.", remaining)
            raise RateLimitExhausted(remaining)
        if resp.status_code == 200:
            data = resp.json()
            return True, data.get("stargazers_count")
        return False, None
    except RateLimitExhausted:
        raise
    except Exception:
        return False, None


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

                try:
                    for svc_id, source_url in rows:
                        ok, stars = await check_repo(client, source_url)
                        status = "ok" if ok else "404"
                        values: dict = {"repo_status": status}
                        if stars is not None:
                            values["stars"] = stars
                        await db.execute(
                            McpService.__table__.update()
                            .where(McpService.id == svc_id)
                            .values(**values)
                        )
                        if ok:
                            stats["ok"] += 1
                        else:
                            stats["not_found"] += 1
                        stats["checked"] += 1
                except RateLimitExhausted:
                    await db.commit()
                    logger.info(
                        "Repo check paused (rate limit): %d checked (ok: %d, 404: %d)",
                        stats["checked"], stats["ok"], stats["not_found"],
                    )
                    return stats

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


async def run_stars_update() -> dict[str, int]:
    """Re-fetch GitHub stars for services and skill sources with repo_status='ok'."""
    stats = {"services": 0, "skill_sources": 0}
    batch_size = 50

    async with httpx.AsyncClient(timeout=10.0) as client:
        # --- McpService stars ---
        while True:
            async with SessionLocal() as db:
                result = await db.execute(
                    select(McpService.id, McpService.source_url)
                    .where(
                        McpService.repo_status == "ok",
                        McpService.source_url.contains("github.com"),
                    )
                    .where(McpService.stars.is_(None))
                    .limit(batch_size)
                )
                rows = result.all()
                if not rows:
                    break

                try:
                    for svc_id, source_url in rows:
                        _, stars = await check_repo(client, source_url)
                        if stars is not None:
                            await db.execute(
                                McpService.__table__.update()
                                .where(McpService.id == svc_id)
                                .values(stars=stars)
                            )
                            stats["services"] += 1
                except RateLimitExhausted:
                    await db.commit()
                    logger.info("Stars update paused (rate limit): %s", stats)
                    return stats

                await db.commit()
                logger.info("Stars update (services): %d updated so far", stats["services"])

        # --- SkillSource stars ---
        async with SessionLocal() as db:
            result = await db.execute(
                select(SkillSource.id, SkillSource.repo_url)
                .where(
                    SkillSource.repo_url.isnot(None),
                    SkillSource.stars.is_(None),
                )
            )
            rows = result.all()

            try:
                for src_id, repo_url in rows:
                    _, stars = await check_repo(client, repo_url)
                    if stars is not None:
                        await db.execute(
                            SkillSource.__table__.update()
                            .where(SkillSource.id == src_id)
                            .values(stars=stars)
                        )
                        stats["skill_sources"] += 1
            except RateLimitExhausted:
                await db.commit()
                logger.info("Stars update paused (rate limit): %s", stats)
                return stats

            await db.commit()

    logger.info("Stars update done: %s", stats)
    return stats
