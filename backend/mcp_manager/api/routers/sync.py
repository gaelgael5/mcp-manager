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

@router.post("/services/index")
async def trigger_index(
    background_tasks: BackgroundTasks,
    limit: int = Query(500),
):
    if _sync_status.get("indexing"):
        return {"status": "already_running"}
    _sync_status["indexing"] = True
    background_tasks.add_task(_run_index_bg, limit)
    return {"status": "started", "limit": limit}


@router.post("/services/scrape-skills")
async def trigger_scrape_skills(
    background_tasks: BackgroundTasks,
    limit: int = Query(None),
    skip_summaries: bool = Query(False),
):
    if _sync_status.get("scraping"):
        return {"status": "already_running"}
    _sync_status["scraping"] = True
    background_tasks.add_task(_run_scrape_skills_bg, limit, skip_summaries)
    return {"status": "started"}


@router.get("/services/sync/status")
async def sync_status():
    return _sync_status

async def _run_sync_bg(source: str | None):
    from datetime import datetime, timezone
    try:
        from mcp_manager.connectors.registry import get_all_connectors, get_connector
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


async def _run_scrape_skills_bg(limit: int | None, skip_summaries: bool):
    from datetime import datetime, timezone
    try:
        from scripts.scrape_skills_sh import scrape_skills_sh
        await scrape_skills_sh(limit=limit, skip_summaries=skip_summaries)
        _sync_status["last_scrape"] = {
            "time": datetime.now(timezone.utc).isoformat(),
            "limit": limit,
        }
    except Exception:
        logger.exception("Scrape skills failed")
    finally:
        _sync_status["scraping"] = False


async def _run_index_bg(limit: int):
    from datetime import datetime, timezone
    try:
        from mcp_manager.summarizer.ollama_client import get_llm_manager
        from mcp_manager.indexer.pipeline import run_index

        manager = get_llm_manager()
        manager.load()
        manager.start_all()

        try:
            result = await run_index(limit=limit)
            _sync_status["last_index"] = {
                "stats": result,
                "time": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            manager.stop_all()
    except Exception:
        logger.exception("Index failed")
    finally:
        _sync_status["indexing"] = False
