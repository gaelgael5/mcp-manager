"""Indexation pipeline: fetch doc, summarize, detect params, generate recipes.

Uses a fast-path short-circuit based on GitHub branch SHA:
  - If branch_hash matches DB value AND all expected outputs exist in DB
    (summaries per active culture, at least one param, at least one
    installation), the service is skipped with ZERO LLM calls and no README
    fetch. Only cost: 1 GitHub API call (branch SHA) + 3 small DB queries.
  - Otherwise the README is fetched and the pipeline generates whatever is
    missing (missing cultures) or stale (if branch moved, params and
    installations are regenerated; if the README content hash differs from
    what's stored in existing summaries' source_hash, summaries are
    regenerated too).

`service.doc_hash` is NEVER written by this pipeline — it's owned by the
connectors (each stores sha256 of its own source metadata). The README
content hash is stored per-summary in `mcp_summaries.source_hash`.
"""
import asyncio
import hashlib
import logging

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mcp_manager.db.session import SessionLocal
from mcp_manager.db.models import (
    McpService, McpSummary, McpParameter, McpInstallation,
    InstallTarget,
)
from mcp_manager.connectors.registry import get_connector
from mcp_manager.connectors.base import RawMcpService
from mcp_manager.summarizer.summarizer import generate_summary
from mcp_manager.prompts import get_active_language_codes
from mcp_manager.summarizer.cleaner import clean_markdown
from mcp_manager.exporters.engine import generate_from_modes
from mcp_manager.api.routers.parameters import detect_parameters_for_service
import mcp_manager.connectors  # noqa: F401

logger = logging.getLogger(__name__)


async def run_index(
    limit: int = 100,
    progress_callback=None,
    cancel_check=None,
    manager=None,
) -> dict[str, int]:
    """Process up to `limit` services that need reindexing.

    Uses a Queue + N workers pattern. N is `max(1, len(manager.drivers))` —
    each worker owns one LLM driver (a Docker container instance or the
    shared Ollama endpoint) via a context-local single-driver sub-manager.
    """
    from mcp_manager.summarizer.ollama_client import get_llm_manager, set_llm_manager
    from mcp_manager.llm.manager import LLMManager
    from mcp_manager.llm.driver_docker import LLMProviderDead

    stats = {
        "processed": 0,
        "skipped_no_doc": 0,
        "skipped_unchanged": 0,
        "summaries": 0,
        "embeddings": 0,
        "params": 0,
        "recipes": 0,
    }

    async with SessionLocal() as db:
        total_result = await db.execute(
            select(func.count()).select_from(McpService).where(McpService.needs_reindex == True)
        )
        total = min(total_result.scalar() or 0, limit)
    stats["total"] = total

    if progress_callback:
        progress_callback(stats)

    if total == 0:
        return stats

    async with SessionLocal() as db:
        id_result = await db.execute(
            select(McpService.id)
            .where(McpService.needs_reindex == True)
            .order_by(McpService.updated_at.desc())
            .limit(limit)
        )
        service_ids = [row[0] for row in id_result.all()]

    queue: asyncio.Queue = asyncio.Queue()
    for sid in service_ids:
        queue.put_nowait(sid)

    if manager is None:
        manager = get_llm_manager()
    if not manager.drivers:
        logger.error("run_index: no LLM provider configured in /settings.")
        return stats
    num_workers = len(manager.drivers)
    abort_event = asyncio.Event()

    async def _worker(worker_id: int, driver):
        worker_mgr = LLMManager.__new__(LLMManager)
        worker_mgr.drivers = [driver]
        worker_mgr._current = 0
        worker_mgr._config = {}
        worker_mgr._batch_id = f"mcp-w{worker_id}"
        worker_mgr._pipeline = "mcp"
        set_llm_manager(worker_mgr)

        driver_name = getattr(driver, "container_name", None) or type(driver).__name__
        logger.info("mcp index worker %d started with driver %s", worker_id, driver_name)

        while True:
            if abort_event.is_set():
                break
            if cancel_check and cancel_check():
                break
            try:
                sid = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            async with SessionLocal() as wdb:
                result = await wdb.execute(select(McpService).where(McpService.id == sid))
                service = result.scalar_one_or_none()
                if not service:
                    continue

                indexed = False
                try:
                    indexed = await _index_one(wdb, service, stats)
                except LLMProviderDead as e:
                    logger.error(
                        "mcp index worker %d: LLM provider dead — aborting pipeline: %s",
                        worker_id, e,
                    )
                    abort_event.set()
                    try:
                        await wdb.rollback()
                    except Exception:
                        pass
                    break
                except Exception:
                    logger.exception("Failed to index %s", service.name)
                    service.repo_status = "index_failed"

                service.needs_reindex = False

                stats["processed"] += 1
                processed = stats["processed"]

                try:
                    await wdb.commit()
                except Exception:
                    logger.exception("Commit failed for %s", service.name)
                    await wdb.rollback()

                if progress_callback:
                    progress_callback(stats)

                if processed % 10 == 0:
                    logger.info(
                        "Index progress: %d processed (summaries: %d, params: %d, recipes: %d, unchanged: %d)",
                        processed, stats["summaries"], stats["params"],
                        stats["recipes"], stats["skipped_unchanged"],
                    )

    workers = [
        asyncio.create_task(_worker(i, manager.drivers[i]))
        for i in range(num_workers)
    ]
    await asyncio.gather(*workers)

    if abort_event.is_set():
        stats["aborted"] = "llm_provider_dead"
        logger.error(
            "Index aborted: %d processed before LLM provider failure "
            "(summaries: %d, params: %d, recipes: %d, unchanged: %d)",
            stats["processed"], stats["summaries"], stats["params"],
            stats["recipes"], stats["skipped_unchanged"],
        )
    else:
        logger.info(
            "Index done: %d processed (summaries: %d, params: %d, recipes: %d, unchanged: %d)",
            stats["processed"], stats["summaries"], stats["params"],
            stats["recipes"], stats["skipped_unchanged"],
        )
    return stats


async def _index_one(db, service: McpService, stats: dict) -> bool:
    """Index a single service with fast-path short-circuit.

    Flow:
      1. Fetch branch SHA. Compare to service.branch_hash → branch_changed?
      2. Check DB state: missing cultures, has_params, has_installs
      3. Fast path: if branch unchanged AND everything present → return (skip)
      4. Else: fetch README, compute new_doc_hash
      5. Generate missing cultures (always)
      6. If branch_changed and content_changed (per summary.source_hash), regen all cultures
      7. If branch_changed or missing params: re-run param detection
      8. If branch_changed or missing installations: regen installations
      9. Update service.branch_hash (do NOT touch service.doc_hash — connector-owned)
    """
    from mcp_manager.connectors.github_readme import fetch_github_readme, fetch_branch_sha

    # --- Step 1: branch SHA ---------------------------------------------------
    new_branch_hash = await fetch_branch_sha(service.source_url)
    branch_changed = new_branch_hash is None or service.branch_hash != new_branch_hash

    # --- Step 2: inspect current DB state ------------------------------------
    cultures = await get_active_language_codes(db)

    existing_cultures_q = await db.execute(
        select(McpSummary.culture).where(
            McpSummary.parent_id == service._id,
            McpSummary.culture.in_(cultures),
        )
    )
    existing_cultures_set = {row[0] for row in existing_cultures_q.all()}
    missing_cultures = [c for c in cultures if c not in existing_cultures_set]

    has_params_q = await db.execute(
        select(func.count()).select_from(McpParameter).where(
            McpParameter.parent_id == service._id
        )
    )
    has_params = (has_params_q.scalar() or 0) > 0

    has_installs_q = await db.execute(
        select(func.count()).select_from(McpInstallation).where(
            McpInstallation.parent_id == service._id
        )
    )
    has_installs = (has_installs_q.scalar() or 0) > 0

    # --- Step 3: fast-path short-circuit -------------------------------------
    if not branch_changed and not missing_cultures and has_params and has_installs:
        stats["skipped_unchanged"] += 1
        # Persist branch_hash in case it was NULL (first observation).
        if new_branch_hash is not None and service.branch_hash != new_branch_hash:
            service.branch_hash = new_branch_hash
        service.repo_status = "ok"
        return True

    # --- Step 4: fetch README (only reached when there's real work) ----------
    doc_content = None
    if service.doc_url:
        doc_content = await fetch_github_readme(service.doc_url)
    if not doc_content and service.source_url:
        doc_content = await fetch_github_readme(service.source_url)

    if not doc_content:
        stats["skipped_no_doc"] += 1
        if service.repo_status not in ("404",):
            service.repo_status = "no_doc"
        return False

    cleaned = clean_markdown(doc_content)
    if not cleaned:
        stats["skipped_no_doc"] += 1
        if service.repo_status not in ("404",):
            service.repo_status = "no_doc"
        return False

    new_doc_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

    # --- Step 5: summaries ----------------------------------------------------
    # Decide which cultures need regeneration:
    #   - missing_cultures: always generate
    #   - if branch_changed: compare new_doc_hash to existing summary.source_hash
    #     (not service.doc_hash, which is connector-owned). If different, README
    #     content actually changed → regenerate all cultures that have a stale
    #     source_hash. If same, README unchanged, only fill gaps.
    cultures_to_generate = list(missing_cultures)

    if branch_changed and len(existing_cultures_set) > 0:
        existing_hashes_q = await db.execute(
            select(McpSummary.culture, McpSummary.source_hash).where(
                McpSummary.parent_id == service._id,
                McpSummary.culture.in_(cultures),
            )
        )
        for culture, stored_hash in existing_hashes_q.all():
            if stored_hash != new_doc_hash and culture not in cultures_to_generate:
                cultures_to_generate.append(culture)

    for culture in cultures_to_generate:
        summary_text = await generate_summary(doc_content, culture)
        if not summary_text:
            continue
        stmt = pg_insert(McpSummary.__table__).values(
            parent_id=service._id,
            culture=culture,
            summary=summary_text,
            source_hash=new_doc_hash,
        ).on_conflict_do_update(
            index_elements=["parent_id", "culture"],
            set_={
                "summary": summary_text,
                "source_hash": new_doc_hash,
                "updated_at": func.now(),
            },
        )
        await db.execute(stmt)
        stats["summaries"] += 1

    did_work = bool(cultures_to_generate)

    # --- Step 6: params -------------------------------------------------------
    if branch_changed or not has_params:
        from mcp_manager.llm.driver_docker import LLMProviderDead
        try:
            param_stats = await detect_parameters_for_service(db, service, cleaned)
            stats["params"] += param_stats["added"]
            did_work = True
        except LLMProviderDead:
            raise
        except Exception:
            logger.exception("Param detection failed for %s", service.name)

    # --- Step 7: installations -----------------------------------------------
    if branch_changed or not has_installs:
        targets_result = await db.execute(select(InstallTarget))
        targets = targets_result.scalars().all()
        pkg = service.package_info or {}

        for target in targets:
            if not target.modes:
                continue
            data = generate_from_modes(
                modes=target.modes,
                runtime_hint=pkg.get("runtime_hint"),
                package_identifier=pkg.get("package_identifier"),
                service_name=service.name,
                env_vars=pkg.get("env_vars", {}),
            )
            if not data:
                continue
            stmt = pg_insert(McpInstallation.__table__).values(
                parent_id=service._id,
                install_target_id=target.id,
                action_type=data["action_type"],
                data=data["data"],
            ).on_conflict_do_update(
                index_elements=["parent_id", "install_target_id"],
                set_={
                    "action_type": data["action_type"],
                    "data": data["data"],
                    "updated_at": func.now(),
                },
            )
            await db.execute(stmt)
            stats["recipes"] += 1
            did_work = True

    if not did_work:
        stats["skipped_unchanged"] += 1

    # --- Step 8: refresh search vector from the EN summary -------------------
    en_summary = await db.execute(
        select(McpSummary.summary).where(
            McpSummary.parent_id == service._id,
            McpSummary.culture == "en",
        )
    )
    en_summary_text = en_summary.scalar_one_or_none()
    if en_summary_text:
        from sqlalchemy import text as sql_text
        await db.execute(
            sql_text("""
                UPDATE mcp_services SET search_vector = to_tsvector('english',
                    coalesce(name, '') || ' ' || coalesce(category, '') || ' ' || :summary
                ) WHERE id = :sid
            """),
            {"summary": en_summary_text, "sid": service.id},
        )

    # --- Step 9: persist branch_hash only (leave doc_hash alone) --------------
    if new_branch_hash is not None:
        service.branch_hash = new_branch_hash
    service.repo_status = "ok"
    return True
