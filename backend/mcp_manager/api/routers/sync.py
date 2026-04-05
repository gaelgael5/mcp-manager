import logging
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from mcp_manager.api.deps import get_db

router = APIRouter(tags=["sync"])
logger = logging.getLogger(__name__)

_sync_status = {"running": False, "last_run": None, "last_stats": None}

@router.post("/services/sync")
async def trigger_sync(
    background_tasks: BackgroundTasks,
    source: str | None = Query(None),
):
    if _sync_status["running"]:
        return {"status": "already_running"}
    _sync_status["running"] = True
    background_tasks.add_task(_run_sync_bg, source)
    return {"status": "started"}

@router.get("/services/sync/status")
async def sync_status():
    return _sync_status

async def _run_sync_bg(source: str | None):
    from datetime import datetime, timezone
    try:
        from mcp_manager.connectors.registry import get_all_connectors, get_connector
        import mcp_manager.connectors.docker_registry  # noqa: F401
        import mcp_manager.connectors.mcp_registry  # noqa: F401
        import mcp_manager.connectors.mcp_servers_repo  # noqa: F401
        import mcp_manager.connectors.pulsemcp  # noqa: F401
        from mcp_manager.db.session import SessionLocal
        from mcp_manager.db.models import McpService
        from sqlalchemy import select

        if source:
            connector = get_connector(source)
            connectors = [connector] if connector else []
        else:
            connectors = get_all_connectors()

        stats = {"new": 0, "updated": 0, "unchanged": 0}
        for conn in connectors:
            services = await conn.fetch_services()
            async with SessionLocal() as db:
                for raw in services:
                    result = await db.execute(
                        select(McpService).where(
                            McpService.source_type == raw.source_type,
                            McpService.name == raw.name,
                        )
                    )
                    existing = result.scalar_one_or_none()
                    if not existing:
                        db.add(McpService(
                            name=raw.name, source_url=raw.source_url,
                            source_type=raw.source_type, doc_url=raw.doc_url,
                            doc_hash=raw.doc_hash, branch_hash=raw.branch_hash,
                            transport=raw.transport, category=raw.category,
                            tags=raw.tags, is_deprecated=raw.is_deprecated,
                        ))
                        stats["new"] += 1
                    elif existing.doc_hash != raw.doc_hash or existing.branch_hash != raw.branch_hash:
                        existing.doc_url = raw.doc_url
                        existing.doc_hash = raw.doc_hash
                        existing.branch_hash = raw.branch_hash
                        existing.transport = raw.transport
                        existing.category = raw.category
                        existing.tags = raw.tags
                        stats["updated"] += 1
                    else:
                        stats["unchanged"] += 1
                await db.commit()

        _sync_status["last_stats"] = stats
        _sync_status["last_run"] = datetime.now(timezone.utc).isoformat()
    except Exception:
        logger.exception("Sync failed")
    finally:
        _sync_status["running"] = False
