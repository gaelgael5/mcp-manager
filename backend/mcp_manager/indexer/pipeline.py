"""Indexation pipeline: fetch doc, summarize, detect params, generate recipes.

Uses hash-based short-circuits to skip work when nothing has changed upstream:
  - branch_hash (HEAD SHA of the default branch) governs params + installations.
    If the branch SHA is unchanged, params and installations are left alone.
  - doc_hash (sha256 of the cleaned README content) governs summaries. If the
    README content is unchanged, summaries are left alone.

Both checks are independent: a code-only commit bumps branch_hash but not
doc_hash, so params/installations get re-evaluated while summaries stay.
"""
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


async def run_index(limit: int = 100, progress_callback=None, cancel_check=None) -> dict[str, int]:
    """Process up to `limit` services that need reindexing."""
    stats = {
        "processed": 0,
        "skipped_no_doc": 0,
        "skipped_unchanged": 0,
        "summaries": 0,
        "embeddings": 0,
        "params": 0,
        "recipes": 0,
    }

    # Count total to index
    async with SessionLocal() as db:
        total_result = await db.execute(
            select(func.count()).select_from(McpService).where(McpService.needs_reindex == True)
        )
        total = min(total_result.scalar() or 0, limit)
    stats["total"] = total

    if progress_callback:
        progress_callback(stats)

    batch_size = 10
    processed = 0

    while processed < limit:
        async with SessionLocal() as db:
            result = await db.execute(
                select(McpService)
                .where(McpService.needs_reindex == True)
                .order_by(McpService.updated_at.desc())
                .limit(min(batch_size, limit - processed))
            )
            services = result.scalars().all()
            if not services:
                break

            for service in services:
                if cancel_check and cancel_check():
                    logger.info("Index cancelled at %d processed", processed)
                    return stats

                indexed = False
                try:
                    indexed = await _index_one(db, service, stats)
                except Exception:
                    logger.exception("Failed to index %s", service.name)

                service.needs_reindex = False
                if not indexed:
                    service.repo_status = "index_failed"
                processed += 1
                stats["processed"] += 1

                if progress_callback:
                    progress_callback(stats)

            await db.commit()

        logger.info(
            "Index progress: %d processed (summaries: %d, params: %d, recipes: %d, unchanged: %d)",
            stats["processed"], stats["summaries"], stats["params"],
            stats["recipes"], stats["skipped_unchanged"],
        )

    return stats


async def _index_one(db, service: McpService, stats: dict) -> bool:
    """Index a single service with hash-based short-circuits.

    Flow:
      1. Fetch the branch SHA from GitHub → branch_changed?
      2. Fetch the README and compute its sha256 → doc_changed?
      3. If doc_changed: regenerate summaries (overwrite via on_conflict_do_update)
      4. If branch_changed: re-run param detection and installation generation
      5. Update search_vector from the EN summary
      6. Persist new branch_hash and doc_hash on the service row

    Returns True if the service was processed (even if nothing was regenerated
    because everything was up-to-date). Returns False only if the service is
    inaccessible (no doc could be fetched).
    """
    from mcp_manager.connectors.github_readme import fetch_github_readme, fetch_branch_sha

    # --- Step 1: branch SHA ---------------------------------------------------
    new_branch_hash = await fetch_branch_sha(service.source_url)
    # If we can't fetch a SHA (non-github or 404), force re-evaluation so the
    # service still gets processed — the fetch_github_readme below will tell
    # us if the repo is really dead.
    branch_changed = new_branch_hash is None or service.branch_hash != new_branch_hash

    # --- Step 2: fetch README and compute doc_hash ----------------------------
    doc_content = None
    if service.doc_url:
        doc_content = await fetch_github_readme(service.doc_url)
    if not doc_content and service.source_url:
        doc_content = await fetch_github_readme(service.source_url)

    if not doc_content:
        stats["skipped_no_doc"] += 1
        return False

    cleaned = clean_markdown(doc_content)
    if not cleaned:
        stats["skipped_no_doc"] += 1
        return False

    new_doc_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    doc_changed = service.doc_hash != new_doc_hash

    # --- Step 3: summaries ----------------------------------------------------
    # Rules:
    #   - If doc_hash changed → regenerate ALL active cultures (overwrite stale)
    #   - Else → generate only the cultures that are missing in the DB
    #     (catches newly activated languages and previous-run gaps)
    cultures = await get_active_language_codes(db)
    if doc_changed:
        cultures_to_generate = list(cultures)
    else:
        existing_q = await db.execute(
            select(McpSummary.culture).where(
                McpSummary.mcp_service_id == service.id,
                McpSummary.culture.in_(cultures),
            )
        )
        existing_cultures = {row[0] for row in existing_q.all()}
        cultures_to_generate = [c for c in cultures if c not in existing_cultures]

    for culture in cultures_to_generate:
        summary_text = await generate_summary(doc_content, culture)
        if not summary_text:
            continue
        stmt = pg_insert(McpSummary.__table__).values(
            mcp_service_id=service.id,
            parent_id=service._id,
            culture=culture,
            summary=summary_text,
            source_hash=new_doc_hash,
        ).on_conflict_do_update(
            index_elements=["mcp_service_id", "culture"],
            set_={
                "summary": summary_text,
                "source_hash": new_doc_hash,
                "updated_at": func.now(),
            },
        )
        await db.execute(stmt)
        stats["summaries"] += 1

    # Track whether any real work was done (summaries, params, installations).
    did_work = bool(cultures_to_generate)

    # --- Step 4: re-detect params if branch moved -----------------------------
    if branch_changed:
        try:
            param_stats = await detect_parameters_for_service(db, service, cleaned)
            stats["params"] += param_stats["added"]
            did_work = True
        except Exception:
            logger.exception("Param detection failed for %s", service.name)

    # --- Step 5: regenerate installations if branch moved ---------------------
    if branch_changed:
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
                mcp_service_id=service.id,
                parent_id=service._id,
                install_target_id=target.id,
                action_type=data["action_type"],
                data=data["data"],
            ).on_conflict_do_update(
                index_elements=["mcp_service_id", "install_target_id"],
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

    # --- Step 6: refresh search vector from the EN summary -------------------
    en_summary = await db.execute(
        select(McpSummary.summary).where(
            McpSummary.mcp_service_id == service.id,
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

    # --- Step 7: persist the new hashes --------------------------------------
    if new_branch_hash is not None:
        service.branch_hash = new_branch_hash
    service.doc_hash = new_doc_hash
    service.repo_status = "ok"
    return True
