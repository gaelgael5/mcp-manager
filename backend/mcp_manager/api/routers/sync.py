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


@router.post("/services/enrich-skills")
async def trigger_enrich_skills(
    background_tasks: BackgroundTasks,
):
    if _sync_status.get("enriching"):
        return {"status": "already_running"}
    _sync_status["enriching"] = True
    _sync_status["enrich_cancel"] = False
    background_tasks.add_task(_run_enrich_skills_bg)
    return {"status": "started"}


@router.post("/services/enrich-skills/stop")
async def stop_enrich_skills():
    if not _sync_status.get("enriching"):
        return {"status": "not_running"}
    _sync_status["enrich_cancel"] = True
    return {"status": "stopping"}


@router.get("/services/sync/status")
async def sync_status():
    return _sync_status

async def _run_sync_bg(source: str | None):
    from datetime import datetime, timezone
    try:
        from mcp_manager.connectors.registry import get_all_connectors, get_connector
        from mcp_manager.db.session import SessionLocal
        from mcp_manager.db.models import McpService
        from mcp_manager.enrichment.canonical import compute_canonical_id
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
                    cid = compute_canonical_id(
                        source_url=raw.source_url,
                        package_identifier=getattr(raw, "package_identifier", None),
                        registry_type=getattr(raw, "registry_type", None),
                        source_type=raw.source_type,
                        name=raw.name,
                    )
                    if not existing:
                        db.add(McpService(
                            name=raw.name, source_url=raw.source_url,
                            source_type=raw.source_type, doc_url=raw.doc_url,
                            doc_hash=raw.doc_hash, branch_hash=raw.branch_hash,
                            transport=raw.transport, category=raw.category,
                            tags=raw.tags, is_deprecated=raw.is_deprecated,
                            canonical_id=cid,
                        ))
                        stats["new"] += 1
                    elif existing.doc_hash != raw.doc_hash or existing.branch_hash != raw.branch_hash:
                        existing.doc_url = raw.doc_url
                        existing.doc_hash = raw.doc_hash
                        existing.branch_hash = raw.branch_hash
                        existing.transport = raw.transport
                        existing.category = raw.category
                        existing.tags = raw.tags
                        existing.canonical_id = cid
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


async def _run_enrich_skills_bg():
    import logging
    from datetime import datetime, timezone
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import SkillSource
    from mcp_manager.api.routers.skill_sources import (
        _enrich_repo_url, _enrich_summaries, _enrich_sync_skills,
    )
    from sqlalchemy import select, or_

    enrich_logger = logging.getLogger("enrich-pipeline")

    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(SkillSource).where(
                    or_(
                        SkillSource.enrichment_status == "pending",
                        SkillSource.enrichment_status == "enriching",
                        SkillSource.enrichment_status.is_(None),
                    )
                ).order_by(SkillSource.created_at)
            )
            sources = result.scalars().all()
            total = len(sources)
            enrich_logger.info("enrich-pipeline: %d sources to process", total)

            stats = {"total": total, "done": 0, "repos_filled": 0, "summaries": 0, "syncs": 0, "failed": 0}
            _sync_status["enrich_progress"] = stats

            for i, source in enumerate(sources):
                if _sync_status.get("enrich_cancel"):
                    enrich_logger.info("enrich-pipeline: cancelled at %d/%d", i, total)
                    break

                source.enrichment_status = "enriching"
                await db.commit()

                try:
                    if await _enrich_repo_url(source):
                        stats["repos_filled"] += 1

                    try:
                        if await _enrich_summaries(source, db):
                            stats["summaries"] += 1
                    except Exception:
                        enrich_logger.warning("enrich-pipeline: summary failed for %s", source.name)

                    try:
                        added = await _enrich_sync_skills(source, db)
                        if added > 0:
                            stats["syncs"] += 1
                    except Exception:
                        enrich_logger.warning("enrich-pipeline: sync failed for %s", source.name)

                    source.enrichment_status = "done"
                    stats["done"] += 1

                except Exception:
                    enrich_logger.exception("enrich-pipeline: failed for %s", source.name)
                    source.enrichment_status = "failed"
                    stats["failed"] += 1

                await db.commit()

                if (i + 1) % 10 == 0:
                    enrich_logger.info("enrich-pipeline: %d/%d done", i + 1, total)
                    _sync_status["enrich_progress"] = dict(stats)

            _sync_status["enrich_progress"] = dict(stats)

        _sync_status["last_enrich"] = {
            "time": datetime.now(timezone.utc).isoformat(),
            **stats,
        }
        enrich_logger.info(
            "enrich-pipeline: done — %d done, %d failed, %d repos, %d summaries, %d syncs",
            stats["done"], stats["failed"], stats["repos_filled"], stats["summaries"], stats["syncs"],
        )
    except Exception:
        enrich_logger.exception("enrich-pipeline failed")
    finally:
        _sync_status["enriching"] = False
        _sync_status["enrich_cancel"] = False


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
