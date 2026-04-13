import logging
import time
from collections import deque
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from mcp_manager.api.deps import get_db

router = APIRouter(tags=["sync"])
logger = logging.getLogger(__name__)

_sync_status = {"running": False, "last_run": None, "last_stats": None}

# Active LLM managers per batch (for exposing driver stats)
_batch_managers: dict = {}


def _register_batch_manager(batch_id: str, manager):
    """Register a batch manager and set it as the context-local LLM manager."""
    from mcp_manager.summarizer.ollama_client import set_llm_manager
    _batch_managers[batch_id] = manager
    set_llm_manager(manager)


def _unregister_batch_manager(batch_id: str):
    """Unregister a batch manager and clear the context-local LLM manager."""
    from mcp_manager.summarizer.ollama_client import set_llm_manager
    _batch_managers.pop(batch_id, None)
    set_llm_manager(None)

# Ring buffers for throughput: deque of (monotonic_time, done_count)
# One per operation type, max ~12 entries (5min / 30s interval + margin)
_throughput_history: dict[str, deque] = {
    "indexing": deque(maxlen=15),
    "enriching": deque(maxlen=15),
    "indexing_skills": deque(maxlen=15),
    "rag_indexing": deque(maxlen=15),
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
    _sync_status["index_cancel"] = False
    _sync_status["indexing_started_at"] = datetime.now(timezone.utc).isoformat()
    background_tasks.add_task(_run_index_bg, limit)
    return {"status": "started", "limit": limit}


@router.post("/services/index/stop")
async def stop_index():
    if not _sync_status.get("indexing"):
        return {"status": "not_running"}
    _sync_status["index_cancel"] = True
    return {"status": "stopping"}


@router.post("/services/agents/{batch_id}/start")
async def start_agents(batch_id: str, provider_id: int = Query(None)):
    """Start Docker agent containers for a batch. If provider_id given, start only that one."""
    from mcp_manager.llm.manager import LLMManager
    from mcp_manager.llm.driver_docker import DockerDriver
    import subprocess

    if batch_id not in _batch_managers:
        manager = LLMManager(batch_id=batch_id)
        manager.load()
        _register_batch_manager(batch_id, manager)
    else:
        manager = _batch_managers[batch_id]

    if provider_id is not None:
        for d in manager.drivers:
            if isinstance(d, DockerDriver) and d.provider_id == provider_id:
                await d.start()
                return {"status": "started", "container": d.container_name}
        return {"status": "not_found"}

    await manager.start_all()
    return {"status": "started", "drivers": len(manager.drivers)}


@router.post("/services/agents/{batch_id}/stop")
async def stop_agents(batch_id: str, provider_id: int = Query(None)):
    """Stop Docker agent containers for a batch. If provider_id given, stop only that one."""
    from mcp_manager.llm.driver_docker import DockerDriver
    import subprocess

    manager = _batch_managers.get(batch_id)
    if not manager:
        return {"status": "not_running"}

    if provider_id is not None:
        for d in manager.drivers:
            if isinstance(d, DockerDriver) and d.provider_id == provider_id:
                await d.stop()
                return {"status": "stopped", "container": d.container_name}
        return {"status": "not_found"}

    await manager.stop_all()
    _unregister_batch_manager(batch_id)
    return {"status": "stopped"}


@router.post("/services/rag-index")
async def trigger_rag_index(
    background_tasks: BackgroundTasks,
    scope: str = Query("all"),  # "all", "mcp", "sources", "skills"
):
    if _sync_status.get("rag_indexing"):
        return {"status": "already_running"}
    from datetime import datetime, timezone
    _sync_status["rag_indexing"] = True
    _sync_status["rag_cancel"] = False
    _sync_status["rag_started_at"] = datetime.now(timezone.utc).isoformat()
    background_tasks.add_task(_run_rag_index_bg, scope)
    return {"status": "started", "scope": scope}


@router.post("/services/rag-index/stop")
async def stop_rag_index():
    if not _sync_status.get("rag_indexing"):
        return {"status": "not_running"}
    _sync_status["rag_cancel"] = True
    return {"status": "stopping"}


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
    for op in ("indexing", "enriching", "indexing_skills", "rag_indexing"):
        tp = _compute_throughput(op)
        if tp is not None:
            result[f"{op}_throughput"] = tp
    # Add Docker agent container status per batch
    result["docker_agents"] = _get_docker_agents_status()
    # Add driver stats per active batch
    result["driver_stats"] = {
        batch_id: mgr.get_driver_stats()
        for batch_id, mgr in _batch_managers.items()
    }
    return result


def _get_docker_agents_status() -> dict:
    """Check which Docker agent containers are running for each batch."""
    import subprocess
    from mcp_manager.llm.config import load_config

    config = load_config()
    docker_providers = [p for p in config.get("llm", []) if p.get("type") == "docker"]

    if not docker_providers:
        return {"providers": [], "batches": {}}

    # List all running mcp-llm-worker containers
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=mcp-llm-worker", "--format", "{{.Names}} {{.Status}}"],
            capture_output=True, text=True, timeout=5,
        )
        running = {}
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split(" ", 1)
                running[parts[0]] = parts[1] if len(parts) > 1 else "running"
    except Exception:
        running = {}

    # Check which images exist
    providers_info = []
    for p in docker_providers:
        image = p.get("image", "")
        pid = p.get("id", 0)
        # Check if image exists
        try:
            img_result = subprocess.run(
                ["docker", "images", f"agent-{image}", "--format", "{{.Repository}}:{{.Tag}}"],
                capture_output=True, text=True, timeout=5,
            )
            image_exists = bool(img_result.stdout.strip())
            image_ref = img_result.stdout.strip().split("\n")[0] if image_exists else None
        except Exception:
            image_exists = False
            image_ref = None

        providers_info.append({
            "id": pid,
            "image": image,
            "image_exists": image_exists,
            "image_ref": image_ref,
        })

    # Check running containers per batch
    batch_ids = ["enrich", "skills", "scrape", "mcp"]
    batches = {}
    for batch_id in batch_ids:
        containers = []
        for p in docker_providers:
            name = f"mcp-llm-worker-{p['id']}-{batch_id}"
            containers.append({
                "provider_id": p["id"],
                "image": p.get("image", ""),
                "container": name,
                "running": name in running,
                "status": running.get(name, "stopped"),
            })
        batches[batch_id] = containers

    return {"providers": providers_info, "batches": batches}

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
                        # Only re-index if not already successfully indexed
                        if existing.repo_status != "ok":
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
    from mcp_manager.llm.manager import LLMManager

    manager = LLMManager(batch_id="scrape")
    manager.load()
    await manager.start_all()
    _register_batch_manager("scrape", manager)

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
        await manager.stop_all()
        _unregister_batch_manager("scrape")
        _sync_status["scraping"] = False


async def _run_enrich_skills_bg():
    import asyncio
    import logging
    from datetime import datetime, timezone
    if not _sync_status.get("enriching_started_at"):
        _sync_status["enriching_started_at"] = datetime.now(timezone.utc).isoformat()
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import SkillSource
    from mcp_manager.api.routers.skill_sources import (
        _enrich_repo_url, _enrich_summaries, _enrich_sync_skills,
    )
    from mcp_manager.llm.manager import LLMManager
    from sqlalchemy import select, or_

    enrich_logger = logging.getLogger("enrich-pipeline")

    manager = LLMManager(batch_id="enrich", pipeline="skill_sources")
    manager.load()
    await manager.start_all()
    _register_batch_manager("enrich", manager)

    try:
        # Get source IDs to process
        async with SessionLocal() as db:
            result = await db.execute(
                select(SkillSource.id).where(
                    or_(
                        SkillSource.enrichment_status == "pending",
                        SkillSource.enrichment_status == "enriching",
                        SkillSource.enrichment_status.is_(None),
                    )
                ).order_by(SkillSource.created_at)
            )
            source_ids = [row[0] for row in result.all()]

        total = len(source_ids)

        if not manager.drivers:
            enrich_logger.error("enrich-pipeline: no LLM provider configured. Aborting.")
            return

        enrich_logger.info("enrich-pipeline: %d sources to process with %d workers", total, len(manager.drivers))

        stats = {"total": total, "done": 0, "repos_filled": 0, "summaries": 0, "syncs": 0, "failed": 0}
        _sync_status["enrich_progress"] = stats

        queue: asyncio.Queue = asyncio.Queue()
        for sid in source_ids:
            queue.put_nowait(sid)

        num_workers = len(manager.drivers)
        enrich_abort_event = asyncio.Event()

        async def _worker(worker_id: int, driver):
            # Each worker uses its own dedicated driver
            from mcp_manager.summarizer.ollama_client import set_llm_manager
            from mcp_manager.llm.manager import LLMManager
            from mcp_manager.llm.driver_docker import LLMProviderDead

            # Create a single-driver manager for this worker
            worker_mgr = LLMManager.__new__(LLMManager)
            worker_mgr.drivers = [driver]
            worker_mgr._current = 0
            worker_mgr._config = {}
            worker_mgr._batch_id = f"enrich-w{worker_id}"
            set_llm_manager(worker_mgr)

            driver_name = getattr(driver, 'image', 'ollama')
            enrich_logger.info("enrich worker %d started with driver %s", worker_id, driver_name)

            while not queue.empty():
                if enrich_abort_event.is_set():
                    break
                if _sync_status.get("enrich_cancel"):
                    break
                try:
                    sid = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                async with SessionLocal() as wdb:
                    result = await wdb.execute(select(SkillSource).where(SkillSource.id == sid))
                    source = result.scalar_one_or_none()
                    if not source:
                        continue

                    source.enrichment_status = "enriching"
                    await wdb.commit()

                    try:
                        if await asyncio.wait_for(_enrich_repo_url(source), timeout=30):
                            stats["repos_filled"] += 1

                        if _sync_status.get("enrich_cancel") or enrich_abort_event.is_set():
                            source.enrichment_status = "pending"
                            break

                        try:
                            if await asyncio.wait_for(_enrich_summaries(source, wdb), timeout=120):
                                stats["summaries"] += 1
                        except asyncio.TimeoutError:
                            enrich_logger.warning("enrich-pipeline: summary timeout for %s", source.name)
                        except LLMProviderDead:
                            raise
                        except Exception:
                            enrich_logger.warning("enrich-pipeline: summary failed for %s", source.name)
                            await wdb.rollback()

                        if _sync_status.get("enrich_cancel") or enrich_abort_event.is_set():
                            source.enrichment_status = "pending"
                            break

                        try:
                            added = await asyncio.wait_for(_enrich_sync_skills(source, wdb), timeout=120)
                            if added > 0:
                                stats["syncs"] += 1
                        except asyncio.TimeoutError:
                            enrich_logger.warning("enrich-pipeline: sync timeout for %s", source.name)
                        except LLMProviderDead:
                            raise
                        except Exception:
                            enrich_logger.warning("enrich-pipeline: sync failed for %s", source.name)
                            await wdb.rollback()

                        source.enrichment_status = "done"
                        stats["done"] += 1

                    except LLMProviderDead as e:
                        enrich_logger.error(
                            "enrich worker %d: LLM provider dead — aborting pipeline: %s",
                            worker_id, e,
                        )
                        enrich_abort_event.set()
                        source.enrichment_status = "pending"
                        try:
                            await wdb.commit()
                        except Exception:
                            await wdb.rollback()
                        break
                    except Exception:
                        enrich_logger.exception("enrich-pipeline: failed for %s", source.name)
                        await wdb.rollback()
                        source.enrichment_status = "failed"
                        stats["failed"] += 1

                    try:
                        await wdb.commit()
                    except Exception:
                        enrich_logger.warning("enrich-pipeline: commit failed for %s", source.name)
                        await wdb.rollback()

                    _record_throughput("enriching", stats["done"])
                    done = stats["done"] + stats["failed"]
                    if done % 10 == 0:
                        enrich_logger.info("enrich-pipeline: %d/%d done", done, total)
                        _sync_status["enrich_progress"] = dict(stats)

        worker_tasks = [asyncio.create_task(_worker(i, manager.drivers[i])) for i in range(num_workers)]
        while worker_tasks:
            done_tasks, worker_tasks = await asyncio.wait(worker_tasks, timeout=5)
            if _sync_status.get("enrich_cancel") and worker_tasks:
                for task in worker_tasks:
                    task.cancel()
                await asyncio.gather(*worker_tasks, return_exceptions=True)
                break

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
        await manager.stop_all()
        _unregister_batch_manager("enrich")
        _sync_status["enriching"] = False
        _sync_status["enrich_cancel"] = False


async def _run_index_skills_bg():
    import asyncio
    import logging
    from datetime import datetime, timezone
    if not _sync_status.get("indexing_skills_started_at"):
        _sync_status["indexing_skills_started_at"] = datetime.now(timezone.utc).isoformat()
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import Skill
    from mcp_manager.api.routers.skill_sources import _enrich_one_skill
    from mcp_manager.llm.manager import LLMManager
    from sqlalchemy import select

    skills_logger = logging.getLogger("index-skills")

    manager = LLMManager(batch_id="skills", pipeline="skills")
    manager.load()
    await manager.start_all()
    _register_batch_manager("skills", manager)

    try:
        # Get skill IDs to process
        async with SessionLocal() as db:
            result = await db.execute(
                select(Skill.id).where(Skill.needs_summary == True).order_by(Skill.created_at)
            )
            skill_ids = [row[0] for row in result.all()]

        total = len(skill_ids)

        if not manager.drivers:
            skills_logger.error("index-skills: no LLM provider configured. Aborting.")
            return

        skills_logger.info("index-skills: %d skills to process with %d workers", total, len(manager.drivers))

        stats = {"total": total, "done": 0, "summaries": 0, "unchanged": 0, "failed": 0}
        _sync_status["index_skills_progress"] = stats

        queue: asyncio.Queue = asyncio.Queue()
        for sid in skill_ids:
            queue.put_nowait(sid)

        num_workers = len(manager.drivers)
        skills_abort_event = asyncio.Event()

        async def _worker(worker_id: int, driver):
            from mcp_manager.summarizer.ollama_client import set_llm_manager
            from mcp_manager.llm.manager import LLMManager
            from mcp_manager.llm.driver_docker import LLMProviderDead

            worker_mgr = LLMManager.__new__(LLMManager)
            worker_mgr.drivers = [driver]
            worker_mgr._current = 0
            worker_mgr._config = {}
            worker_mgr._batch_id = f"skills-w{worker_id}"
            set_llm_manager(worker_mgr)

            driver_name = getattr(driver, 'image', 'ollama')
            skills_logger.info("skills worker %d started with driver %s", worker_id, driver_name)

            while not queue.empty():
                if skills_abort_event.is_set():
                    break
                if _sync_status.get("index_skills_cancel"):
                    break
                try:
                    sid = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                async with SessionLocal() as wdb:
                    result = await wdb.execute(select(Skill).where(Skill.id == sid))
                    skill = result.scalar_one_or_none()
                    if not skill:
                        continue

                    try:
                        updated = await asyncio.wait_for(_enrich_one_skill(skill, wdb), timeout=120)
                        if updated:
                            stats["summaries"] += 1
                        else:
                            stats["unchanged"] += 1
                        skill.needs_summary = False
                        stats["done"] += 1
                    except asyncio.TimeoutError:
                        skills_logger.warning("index-skills: timeout for %s", skill.name)
                        skill.needs_summary = False
                        stats["failed"] += 1
                    except LLMProviderDead as e:
                        skills_logger.error(
                            "skills worker %d: LLM provider dead — aborting pipeline: %s",
                            worker_id, e,
                        )
                        skills_abort_event.set()
                        try:
                            await wdb.rollback()
                        except Exception:
                            pass
                        break
                    except Exception:
                        skills_logger.warning("index-skills: failed for %s", skill.name)
                        skill.needs_summary = False
                        stats["failed"] += 1

                    try:
                        await wdb.commit()
                    except Exception:
                        await wdb.rollback()

                    _record_throughput("indexing_skills", stats["done"])
                    done = stats["done"] + stats["failed"]
                    if done % 10 == 0:
                        skills_logger.info("index-skills: %d/%d done", done, total)
                        _sync_status["index_skills_progress"] = dict(stats)

        worker_tasks = [asyncio.create_task(_worker(i, manager.drivers[i])) for i in range(num_workers)]
        while worker_tasks:
            done_tasks, worker_tasks = await asyncio.wait(worker_tasks, timeout=5)
            if _sync_status.get("index_skills_cancel") and worker_tasks:
                for task in worker_tasks:
                    task.cancel()
                await asyncio.gather(*worker_tasks, return_exceptions=True)
                break

        _sync_status["index_skills_progress"] = dict(stats)

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
        await manager.stop_all()
        _unregister_batch_manager("skills")
        _sync_status["indexing_skills"] = False
        _sync_status["index_skills_cancel"] = False


async def _run_index_bg(limit: int):
    from datetime import datetime, timezone
    if not _sync_status.get("indexing_started_at"):
        _sync_status["indexing_started_at"] = datetime.now(timezone.utc).isoformat()
    try:
        from mcp_manager.llm.manager import LLMManager
        from mcp_manager.indexer.pipeline import run_index

        manager = LLMManager(batch_id="mcp", pipeline="mcp")
        manager.load()
        await manager.start_all()
        _register_batch_manager("mcp", manager)

        def _update_index_progress(stats):
            _sync_status["indexing_progress"] = dict(stats)
            _record_throughput("indexing", stats.get("processed", 0))

        try:
            result = await run_index(
                limit=limit,
                progress_callback=_update_index_progress,
                cancel_check=lambda: _sync_status.get("index_cancel", False),
                manager=manager,
            )
            _sync_status["last_index"] = {
                "stats": result,
                "time": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            await manager.stop_all()
            _unregister_batch_manager("mcp")
    except Exception:
        logger.exception("Index failed")
    finally:
        _sync_status["indexing"] = False
        _sync_status["index_cancel"] = False


async def _run_rag_index_bg(scope: str = "all"):
    """RAG reindex: embed summaries into pgvector. Scope: all, mcp, sources, skills."""
    import asyncio
    from datetime import datetime, timezone
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import (
        McpService, McpSummary, McpEmbedding, SkillSource, Skill,
        SkillSourceTranslation, SkillTranslation,
    )
    from mcp_manager.indexer.embedder import embed_text
    from sqlalchemy import select, delete, func, or_
    from sqlalchemy.orm import selectinload

    rag_logger = logging.getLogger("rag-index")

    run_started = datetime.now(timezone.utc)
    _sync_status["rag_started_at"] = run_started.isoformat()
    _sync_status["rag_scope"] = scope

    stats = {"total": 0, "done": 0, "mcp_summaries": 0, "mcp_chunks": 0, "sources": 0, "skills": 0, "failed": 0}
    _sync_status["rag_progress"] = stats

    do_mcp = scope in ("all", "mcp")
    do_sources = scope in ("all", "sources")
    do_skills = scope in ("all", "skills")

    try:
        # Filter: rag_indexed_at IS NULL OR rag_indexed_at < updated_at
        # Note: RAG embedding is pinned to 'en' because mxbai-embed-large
        # performs significantly better on English than on other languages.
        mcp_filter = (McpSummary.culture == "en") & (
            or_(McpSummary.rag_indexed_at.is_(None), McpSummary.rag_indexed_at < McpSummary.updated_at)
        )
        source_filter = (SkillSourceTranslation.culture == "en") & (
            or_(
                SkillSourceTranslation.rag_indexed_at.is_(None),
                SkillSourceTranslation.rag_indexed_at < SkillSourceTranslation.updated_at,
            )
        )
        skill_filter = (SkillTranslation.culture == "en") & (
            or_(
                SkillTranslation.rag_indexed_at.is_(None),
                SkillTranslation.rag_indexed_at < SkillTranslation.updated_at,
            )
        )

        # Count items to process
        async with SessionLocal() as db:
            mcp_count = (await db.execute(select(func.count()).select_from(McpSummary).where(mcp_filter))).scalar() or 0 if do_mcp else 0
            source_count = (await db.execute(select(func.count()).select_from(SkillSourceTranslation).where(source_filter))).scalar() or 0 if do_sources else 0
            skill_count = (await db.execute(select(func.count()).select_from(SkillTranslation).where(skill_filter))).scalar() or 0 if do_skills else 0

        stats["total"] = mcp_count + source_count + skill_count
        _sync_status["rag_progress"] = dict(stats)
        rag_logger.info("rag-index [%s]: %d to index (mcp=%d, sources=%d, skills=%d)", scope, stats["total"], mcp_count, source_count, skill_count)

        if stats["total"] == 0:
            rag_logger.info("rag-index: nothing to index")
            return

        # Phase 1: MCP summaries
        # Phase 1: MCP summaries
        rag_logger.info("rag-index: phase 1 — %d MCP summaries", mcp_count)
        async with SessionLocal() as db:
            result = await db.execute(
                select(McpSummary, McpService.id.label("service_uuid"))
                .join(McpService, McpSummary.parent_id == McpService._id)
                .where(mcp_filter)
            ) if do_mcp else None
            summary_rows = result.all() if result else []

            for summary, service_uuid in summary_rows:
                if _sync_status.get("rag_cancel"):
                    rag_logger.info("rag-index: cancelled")
                    break

                try:
                    await db.execute(delete(McpEmbedding).where(
                        McpEmbedding.mcp_service_id == service_uuid,
                        McpEmbedding.chunk_type == "summary",
                    ))
                    vec = await embed_text(summary.summary)
                    if vec:
                        db.add(McpEmbedding(
                            mcp_service_id=service_uuid,
                            chunk_type="summary",
                            chunk_index=0,
                            content=summary.summary,
                            embedding=vec,
                        ))
                        summary.rag_indexed_at = datetime.now(timezone.utc)
                        stats["mcp_summaries"] += 1
                except Exception:
                    stats["failed"] += 1

                stats["done"] += 1
                _record_throughput("rag_indexing", stats["done"])
                await asyncio.sleep(0.05)

                if stats["done"] % 50 == 0:
                    await db.commit()
                    _sync_status["rag_progress"] = dict(stats)
                    rag_logger.info("rag-index: %d/%d done", stats["done"], stats["total"])

            await db.commit()

        if _sync_status.get("rag_cancel"):
            return

        # Phase 2: Skill source summaries
        rag_logger.info("rag-index: phase 2 — %d skill sources", source_count)
        async with SessionLocal() as db:
            result = await db.execute(select(SkillSourceTranslation).where(source_filter))
            translations = result.scalars().all() if do_sources else []

            for translation in translations:
                if _sync_status.get("rag_cancel"):
                    break

                try:
                    await db.execute(delete(McpEmbedding).where(
                        McpEmbedding.chunk_type == "source_summary",
                        McpEmbedding.content.like(f"source:{translation.parent_id}%"),
                    ))
                    vec = await embed_text(translation.summary)
                    if vec:
                        db.add(McpEmbedding(
                            chunk_type="source_summary",
                            chunk_index=0,
                            content=f"source:{translation.parent_id} {translation.summary}",
                            embedding=vec,
                        ))
                        translation.rag_indexed_at = datetime.now(timezone.utc)
                        stats["sources"] += 1
                except Exception:
                    stats["failed"] += 1

                stats["done"] += 1
                _record_throughput("rag_indexing", stats["done"])
                await asyncio.sleep(0.05)

                if stats["done"] % 50 == 0:
                    await db.commit()
                    _sync_status["rag_progress"] = dict(stats)

            await db.commit()

        if _sync_status.get("rag_cancel"):
            return

        # Phase 3: Skill summaries
        rag_logger.info("rag-index: phase 3 — %d skills", skill_count)
        async with SessionLocal() as db:
            result = await db.execute(
                select(SkillTranslation)
                .options(selectinload(SkillTranslation.skill))
                .where(skill_filter)
            )
            translations = result.scalars().all() if do_skills else []

            for translation in translations:
                if _sync_status.get("rag_cancel"):
                    break

                try:
                    skill_uuid = translation.skill.id
                    await db.execute(delete(McpEmbedding).where(
                        McpEmbedding.skill_id == skill_uuid,
                        McpEmbedding.chunk_type == "skill_summary",
                    ))
                    vec = await embed_text(translation.summary)
                    if vec:
                        db.add(McpEmbedding(
                            skill_id=skill_uuid,
                            chunk_type="skill_summary",
                            chunk_index=0,
                            content=translation.summary,
                            embedding=vec,
                        ))
                        translation.rag_indexed_at = datetime.now(timezone.utc)
                        stats["skills"] += 1
                except Exception:
                    stats["failed"] += 1

                stats["done"] += 1
                _record_throughput("rag_indexing", stats["done"])
                await asyncio.sleep(0.05)

                if stats["done"] % 50 == 0:
                    await db.commit()
                    _sync_status["rag_progress"] = dict(stats)

            await db.commit()

        _sync_status["last_rag"] = {"time": datetime.now(timezone.utc).isoformat(), **stats}
        rag_logger.info("rag-index: done — %d mcp, %d sources, %d skills, %d failed",
                        stats["mcp_summaries"], stats["sources"], stats["skills"], stats["failed"])

    except Exception:
        rag_logger.exception("rag-index failed")
    finally:
        _sync_status["rag_indexing"] = False
        _sync_status["rag_cancel"] = False


# ──── Quality Eval endpoints ────


@router.post("/quality/eval-heuristic/{scope}")
async def trigger_eval_heuristic(
    scope: str,
    background_tasks: BackgroundTasks,
):
    """Launch heuristic quality eval. scope: mcp, skills, sources."""
    key = f"eval_heuristic_{scope}"
    if _sync_status.get(key):
        return {"status": "already_running"}
    _sync_status[key] = True
    _sync_status[f"{key}_cancel"] = False
    background_tasks.add_task(_run_eval_heuristic_bg, scope)
    return {"status": "started"}


@router.post("/quality/eval-heuristic/{scope}/stop")
async def stop_eval_heuristic(scope: str):
    key = f"eval_heuristic_{scope}"
    if not _sync_status.get(key):
        return {"status": "not_running"}
    _sync_status[f"{key}_cancel"] = True
    return {"status": "stopping"}


@router.post("/quality/eval-llm/{scope}")
async def trigger_eval_llm(
    scope: str,
    background_tasks: BackgroundTasks,
):
    """Launch LLM quality eval. scope: mcp, skills, sources."""
    key = f"eval_llm_{scope}"
    if _sync_status.get(key):
        return {"status": "already_running"}
    _sync_status[key] = True
    _sync_status[f"{key}_cancel"] = False
    background_tasks.add_task(_run_eval_llm_bg, scope)
    return {"status": "started"}


@router.post("/quality/eval-llm/{scope}/stop")
async def stop_eval_llm(scope: str):
    key = f"eval_llm_{scope}"
    if not _sync_status.get(key):
        return {"status": "not_running"}
    _sync_status[f"{key}_cancel"] = True
    return {"status": "stopping"}


@router.get("/quality/eval-stats")
async def get_eval_stats(db: AsyncSession = Depends(get_db)):
    """Return P20 percentiles and counts for heuristic/llm quality."""
    from sqlalchemy import text as sa_text

    _PERCENTILE_TEMPLATE = (
        "SELECT PERCENTILE_CONT(0.20) WITHIN GROUP (ORDER BY heuristic_quality) as p20_h, "
        "PERCENTILE_CONT(0.20) WITHIN GROUP (ORDER BY llm_quality) as p20_l, "
        "COUNT(*) FILTER (WHERE heuristic_quality IS NOT NULL) as h_count, "
        "COUNT(*) FILTER (WHERE llm_quality IS NOT NULL) as l_count "
        "FROM {table} WHERE culture='en'"
    )

    results = {}
    for scope, query in [
        ("mcp", _PERCENTILE_TEMPLATE.format(table="mcp_summaries")),
        ("skills", _PERCENTILE_TEMPLATE.format(table="skills_translations")),
        ("sources", _PERCENTILE_TEMPLATE.format(table="skill_sources_translations")),
    ]:
        row = (await db.execute(sa_text(query))).first()
        results[scope] = {
            "p20_heuristic": round(row[0]) if row[0] is not None else None,
            "p20_llm": round(row[1]) if row[1] is not None else None,
            "heuristic_count": row[2] or 0,
            "llm_count": row[3] or 0,
        }

    # Include running status
    for scope in ("mcp", "skills", "sources"):
        results[scope]["heuristic_running"] = bool(_sync_status.get(f"eval_heuristic_{scope}"))
        results[scope]["llm_running"] = bool(_sync_status.get(f"eval_llm_{scope}"))
        results[scope]["heuristic_progress"] = _sync_status.get(f"eval_heuristic_{scope}_progress")
        results[scope]["llm_progress"] = _sync_status.get(f"eval_llm_{scope}_progress")

    return results


async def _run_eval_heuristic_bg(scope: str):
    """Background task: heuristic quality scoring."""
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import McpSummary, SkillTranslation, SkillSourceTranslation
    from mcp_manager.enrichment.quality_heuristic import score_mcp_summary, score_skill_summary
    from sqlalchemy import select, func

    eval_logger = logging.getLogger("eval-heuristic")
    key = f"eval_heuristic_{scope}"

    _SCOPE_MODEL = {
        "mcp": McpSummary,
        "skills": SkillTranslation,
        "sources": SkillSourceTranslation,
    }

    try:
        model = _SCOPE_MODEL.get(scope)
        if model is None:
            return

        async with SessionLocal() as db:
            # Quality scoring is pinned to 'en' — the heuristic and LLM scorers
            # were trained/tuned on English summaries.
            filter_clause = (model.culture == "en") & (model.heuristic_quality.is_(None))
            total = (await db.execute(
                select(func.count()).select_from(model).where(filter_clause)
            )).scalar() or 0

            result = await db.execute(select(model).where(filter_clause))
            items = result.scalars().all()

            eval_logger.info("eval-heuristic [%s]: %d items to score", scope, total)
            stats = {"done": 0, "total": total}
            _sync_status[f"{key}_progress"] = stats

            scorer = score_mcp_summary if scope == "mcp" else score_skill_summary

            for item in items:
                if _sync_status.get(f"{key}_cancel"):
                    break

                item.heuristic_quality = scorer(item.summary)
                stats["done"] += 1

                if stats["done"] % 500 == 0:
                    await db.commit()
                    _sync_status[f"{key}_progress"] = dict(stats)
                    eval_logger.info("eval-heuristic [%s]: %d/%d", scope, stats["done"], total)

            await db.commit()
            _sync_status[f"{key}_progress"] = dict(stats)
            eval_logger.info("eval-heuristic [%s]: done — %d scored", scope, stats["done"])

    except Exception:
        eval_logger.exception("eval-heuristic [%s] failed", scope)
    finally:
        _sync_status[key] = False
        _sync_status[f"{key}_cancel"] = False


async def _run_eval_llm_bg(scope: str):
    """Background task: LLM quality scoring."""
    import asyncio
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import McpSummary, SkillTranslation, SkillSourceTranslation
    from mcp_manager.enrichment.quality_llm import llm_score_summary
    from sqlalchemy import select, func

    eval_logger = logging.getLogger("eval-llm")
    key = f"eval_llm_{scope}"

    _SCOPE_MODEL = {
        "mcp": McpSummary,
        "skills": SkillTranslation,
        "sources": SkillSourceTranslation,
    }

    try:
        model = _SCOPE_MODEL.get(scope)
        if model is None:
            return

        async with SessionLocal() as db:
            filter_clause = (model.culture == "en") & (model.llm_quality.is_(None))
            total = (await db.execute(
                select(func.count()).select_from(model).where(filter_clause)
            )).scalar() or 0

            result = await db.execute(select(model).where(filter_clause))
            items = result.scalars().all()

            eval_logger.info("eval-llm [%s]: %d items to score", scope, total)
            stats = {"done": 0, "total": total, "failed": 0}
            _sync_status[f"{key}_progress"] = stats

            entity_type = "mcp" if scope == "mcp" else "skill"

            for item in items:
                if _sync_status.get(f"{key}_cancel"):
                    break

                score = await llm_score_summary(item.summary, entity_type)
                if score is not None:
                    item.llm_quality = score
                else:
                    stats["failed"] += 1

                stats["done"] += 1

                if stats["done"] % 50 == 0:
                    await db.commit()
                    _sync_status[f"{key}_progress"] = dict(stats)
                    eval_logger.info("eval-llm [%s]: %d/%d (failed: %d)", scope, stats["done"], total, stats["failed"])

            await db.commit()
            _sync_status[f"{key}_progress"] = dict(stats)
            eval_logger.info("eval-llm [%s]: done — %d scored, %d failed", scope, stats["done"], stats["failed"])

    except Exception:
        eval_logger.exception("eval-llm [%s] failed", scope)
    finally:
        _sync_status[key] = False
        _sync_status[f"{key}_cancel"] = False
