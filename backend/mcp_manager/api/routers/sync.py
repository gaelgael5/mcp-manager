import logging
import time
from collections import deque
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from mcp_manager.api.deps import get_db

router = APIRouter(tags=["sync"])
logger = logging.getLogger(__name__)

_sync_status = {"running": False, "last_run": None, "last_stats": None}

# Ring buffers for throughput: deque of (monotonic_time, done_count)
# One per operation type, max ~12 entries (5min / 30s interval + margin)
_throughput_history: dict[str, deque] = {
    "indexing": deque(maxlen=15),
    "enriching": deque(maxlen=15),
    "indexing_skills": deque(maxlen=15),
}
_SNAPSHOT_INTERVAL = 30  # seconds between snapshots
_last_snapshot: dict[str, float] = {}


def _record_throughput(op: str, done: int):
    """Record a throughput snapshot if enough time has passed."""
    now = time.monotonic()
    last = _last_snapshot.get(op, 0)
    if now - last >= _SNAPSHOT_INTERVAL:
        _throughput_history[op].append((now, done))
        _last_snapshot[op] = now


def _compute_throughput(op: str) -> int | None:
    """Compute items/hour over the last ~5 minutes."""
    history = _throughput_history.get(op)
    if not history or len(history) < 2:
        return None
    now = time.monotonic()
    # Find oldest entry within 5min window
    oldest = None
    for ts, count in history:
        if now - ts <= 330:  # 5.5min to have margin
            oldest = (ts, count)
            break
    if not oldest:
        oldest = history[0]
    newest = history[-1]
    elapsed = newest[0] - oldest[0]
    if elapsed < 10:
        return None
    delta = newest[1] - oldest[1]
    return round(delta / elapsed * 3600)

@router.post("/services/sync")
async def trigger_sync(
    background_tasks: BackgroundTasks,
    source: str | None = Query(None),
):
    if _sync_status["running"]:
        return {"status": "already_running"}
    from datetime import datetime, timezone
    _sync_status["running"] = True
    _sync_status["running_started_at"] = datetime.now(timezone.utc).isoformat()
    background_tasks.add_task(_run_sync_bg, source)
    return {"status": "started"}

@router.post("/services/index")
async def trigger_index(
    background_tasks: BackgroundTasks,
    limit: int = Query(500),
):
    if _sync_status.get("indexing"):
        return {"status": "already_running"}
    from datetime import datetime, timezone
    _sync_status["indexing"] = True
    _sync_status["indexing_started_at"] = datetime.now(timezone.utc).isoformat()
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
    from datetime import datetime, timezone
    _sync_status["enriching"] = True
    _sync_status["enrich_cancel"] = False
    _sync_status["enriching_started_at"] = datetime.now(timezone.utc).isoformat()
    background_tasks.add_task(_run_enrich_skills_bg)
    return {"status": "started"}


@router.post("/services/enrich-skills/stop")
async def stop_enrich_skills():
    if not _sync_status.get("enriching"):
        return {"status": "not_running"}
    _sync_status["enrich_cancel"] = True
    return {"status": "stopping"}


@router.post("/services/index-skills")
async def trigger_index_skills(
    background_tasks: BackgroundTasks,
):
    if _sync_status.get("indexing_skills"):
        return {"status": "already_running"}
    from datetime import datetime, timezone
    _sync_status["indexing_skills"] = True
    _sync_status["index_skills_cancel"] = False
    _sync_status["indexing_skills_started_at"] = datetime.now(timezone.utc).isoformat()
    background_tasks.add_task(_run_index_skills_bg)
    return {"status": "started"}


@router.post("/services/index-skills/stop")
async def stop_index_skills():
    if not _sync_status.get("indexing_skills"):
        return {"status": "not_running"}
    _sync_status["index_skills_cancel"] = True
    return {"status": "stopping"}


@router.get("/services/sync/status")
async def sync_status():
    result = dict(_sync_status)
    # Add computed throughput (items/hour over last 5min)
    for op in ("indexing", "enriching", "indexing_skills"):
        tp = _compute_throughput(op)
        if tp is not None:
            result[f"{op}_throughput"] = tp
    return result

async def _run_sync_bg(source: str | None):
    from datetime import datetime, timezone
    if not _sync_status.get("running_started_at"):
        _sync_status["running_started_at"] = datetime.now(timezone.utc).isoformat()
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
                            needs_reindex=True,
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
                        existing.needs_reindex = True
                        stats["updated"] += 1
                    else:
                        stats["unchanged"] += 1
                await db.commit()

        _sync_status["last_stats"] = stats
        _sync_status["last_run"] = datetime.now(timezone.utc).isoformat()

        # Auto-launch index if new/updated services need reindexing
        reindex_count = stats["new"] + stats["updated"]
        if reindex_count > 0 and not _sync_status.get("indexing"):
            import asyncio
            logger.info("Sync done with %d new/updated — auto-launching index", reindex_count)
            _sync_status["indexing"] = True
            asyncio.create_task(_run_index_bg(reindex_count))

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
    if not _sync_status.get("enriching_started_at"):
        _sync_status["enriching_started_at"] = datetime.now(timezone.utc).isoformat()
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
                _record_throughput("enriching", stats["done"])

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

        # Full RAG reindex of all skill_sources with summaries
        enrich_logger.info("enrich-pipeline: starting full RAG reindex of skill_sources")
        try:
            from mcp_manager.indexer.embedder import embed_text
            from mcp_manager.db.models import McpEmbedding
            from sqlalchemy import delete

            async with SessionLocal() as db:
                result = await db.execute(
                    select(SkillSource).where(SkillSource.summary_en.isnot(None))
                )
                all_sources = result.scalars().all()
                rag_count = 0

                for source in all_sources:
                    try:
                        await db.execute(delete(McpEmbedding).where(
                            McpEmbedding.chunk_type == "source_summary",
                            McpEmbedding.content.like(f"source:{source.id}%"),
                        ))
                        vec = await embed_text(source.summary_en)
                        if vec:
                            db.add(McpEmbedding(
                                chunk_type="source_summary",
                                chunk_index=0,
                                content=f"source:{source.id} {source.summary_en}",
                                embedding=vec,
                            ))
                            rag_count += 1
                    except Exception:
                        pass

                    if rag_count % 100 == 0 and rag_count > 0:
                        await db.commit()
                        enrich_logger.info("enrich-pipeline: RAG reindex %d/%d", rag_count, len(all_sources))

                await db.commit()
                enrich_logger.info("enrich-pipeline: RAG reindex complete — %d sources indexed", rag_count)
        except Exception:
            enrich_logger.exception("enrich-pipeline: RAG reindex failed")

    except Exception:
        enrich_logger.exception("enrich-pipeline failed")
    finally:
        _sync_status["enriching"] = False
        _sync_status["enrich_cancel"] = False


async def _run_index_skills_bg():
    import logging
    from datetime import datetime, timezone
    if not _sync_status.get("indexing_skills_started_at"):
        _sync_status["indexing_skills_started_at"] = datetime.now(timezone.utc).isoformat()
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import Skill, McpEmbedding
    from mcp_manager.api.routers.skill_sources import _enrich_one_skill
    from mcp_manager.indexer.embedder import embed_text
    from sqlalchemy import select, delete

    skills_logger = logging.getLogger("index-skills")

    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(Skill).where(Skill.needs_summary == True).order_by(Skill.created_at)
            )
            skills = result.scalars().all()
            total = len(skills)
            skills_logger.info("index-skills: %d skills to process", total)

            stats = {"total": total, "done": 0, "summaries": 0, "unchanged": 0, "failed": 0}
            _sync_status["index_skills_progress"] = stats

            for i, skill in enumerate(skills):
                if _sync_status.get("index_skills_cancel"):
                    skills_logger.info("index-skills: cancelled at %d/%d", i, total)
                    break

                try:
                    updated = await _enrich_one_skill(skill, db)
                    if updated:
                        stats["summaries"] += 1
                    else:
                        stats["unchanged"] += 1
                    skill.needs_summary = False
                    stats["done"] += 1
                except Exception:
                    skills_logger.warning("index-skills: failed for %s", skill.name)
                    skill.needs_summary = False
                    stats["failed"] += 1

                await db.commit()
                _record_throughput("indexing_skills", stats["done"])

                if (i + 1) % 10 == 0:
                    skills_logger.info("index-skills: %d/%d done", i + 1, total)
                    _sync_status["index_skills_progress"] = dict(stats)

            _sync_status["index_skills_progress"] = dict(stats)

        # Full RAG reindex of all skills with summaries
        skills_logger.info("index-skills: starting full RAG reindex of skills")
        try:
            async with SessionLocal() as db:
                result = await db.execute(
                    select(Skill).where(Skill.summary_en.isnot(None))
                )
                all_skills = result.scalars().all()
                rag_count = 0

                for skill in all_skills:
                    try:
                        await db.execute(delete(McpEmbedding).where(
                            McpEmbedding.skill_id == skill.id,
                            McpEmbedding.chunk_type == "skill_summary",
                        ))
                        vec = await embed_text(skill.summary_en)
                        if vec:
                            db.add(McpEmbedding(
                                skill_id=skill.id,
                                chunk_type="skill_summary",
                                chunk_index=0,
                                content=skill.summary_en,
                                embedding=vec,
                            ))
                            rag_count += 1
                    except Exception:
                        pass

                    if rag_count % 100 == 0 and rag_count > 0:
                        await db.commit()
                        skills_logger.info("index-skills: RAG reindex %d/%d", rag_count, len(all_skills))

                await db.commit()
                skills_logger.info("index-skills: RAG reindex complete — %d skills indexed", rag_count)
        except Exception:
            skills_logger.exception("index-skills: RAG reindex failed")

        _sync_status["last_index_skills"] = {
            "time": datetime.now(timezone.utc).isoformat(),
            **stats,
        }
        skills_logger.info(
            "index-skills: done — %d done, %d summaries, %d unchanged, %d failed",
            stats["done"], stats["summaries"], stats["unchanged"], stats["failed"],
        )
    except Exception:
        skills_logger.exception("index-skills failed")
    finally:
        _sync_status["indexing_skills"] = False
        _sync_status["index_skills_cancel"] = False


async def _run_index_bg(limit: int):
    from datetime import datetime, timezone
    if not _sync_status.get("indexing_started_at"):
        _sync_status["indexing_started_at"] = datetime.now(timezone.utc).isoformat()
    try:
        from mcp_manager.summarizer.ollama_client import get_llm_manager
        from mcp_manager.indexer.pipeline import run_index

        manager = get_llm_manager()
        manager.load()
        manager.start_all()

        def _update_index_progress(stats):
            _sync_status["indexing_progress"] = dict(stats)
            _record_throughput("indexing", stats.get("processed", 0))

        try:
            result = await run_index(limit=limit, progress_callback=_update_index_progress)
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
