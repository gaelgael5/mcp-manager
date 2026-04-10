"""Indexation pipeline: fetch doc, embed, summarize, detect params, generate recipes.

Processes services with needs_reindex=TRUE, one at a time.
"""
import logging

from sqlalchemy import select

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
import mcp_manager.connectors  # noqa: F401

logger = logging.getLogger(__name__)


async def run_index(limit: int = 100, progress_callback=None, cancel_check=None) -> dict[str, int]:
    """Process up to `limit` services that need reindexing."""
    stats = {"processed": 0, "skipped_no_doc": 0, "summaries": 0, "embeddings": 0, "params": 0, "recipes": 0}

    # Count total to index
    async with SessionLocal() as db:
        from sqlalchemy import func
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
            "Index progress: %d processed (summaries: %d, embeddings: %d, params: %d, recipes: %d)",
            stats["processed"], stats["summaries"], stats["embeddings"],
            stats["params"], stats["recipes"],
        )

    return stats


async def _index_one(db, service: McpService, stats: dict) -> bool:
    """Index a single service. Returns True if content was generated."""
    from mcp_manager.connectors.github_readme import fetch_github_readme

    # 1. Fetch documentation — try doc_url then source_url directly
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

    # 2. Generate summaries for each active language
    cultures = await get_active_language_codes(db)
    for culture in cultures:
        existing = await db.execute(
            select(McpSummary).where(
                McpSummary.mcp_service_id == service.id,
                McpSummary.culture == culture,
            )
        )
        if existing.scalar_one_or_none():
            continue  # Already has summary

        summary_text = await generate_summary(doc_content, culture)
        if summary_text:
            db.add(McpSummary(
                mcp_service_id=service.id,
                culture=culture,
                summary=summary_text,
                source_hash=service.doc_hash,
            ))
            stats["summaries"] += 1

    # 3. Get EN summary for search vector update (step 6)
    en_summary = await db.execute(
        select(McpSummary.summary).where(
            McpSummary.mcp_service_id == service.id,
            McpSummary.culture == "en",
        )
    )
    en_summary_text = en_summary.scalar_one_or_none()

    # 4. Detect parameters (if none exist)
    existing_params = await db.execute(
        select(McpParameter).where(McpParameter.mcp_service_id == service.id).limit(1)
    )
    if not existing_params.scalar_one_or_none():
        detected = await _detect_params_from_doc(cleaned)
        for p in detected:
            db.add(McpParameter(
                mcp_service_id=service.id,
                name=p["name"],
                description=p.get("description", ""),
                is_required=p.get("is_required", False),
                is_secret=p.get("is_secret", False),
                source="ai",
            ))
            stats["params"] += 1

    # 5. Generate installation recipes (if none exist)
    existing_installs = await db.execute(
        select(McpInstallation).where(McpInstallation.mcp_service_id == service.id).limit(1)
    )
    if not existing_installs.scalar_one_or_none():
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
            if data:
                db.add(McpInstallation(
                    mcp_service_id=service.id,
                    install_target_id=target.id,
                    action_type=data["action_type"],
                    data=data["data"],
                ))
                stats["recipes"] += 1

    # 6. Update search vector with summary
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

    service.repo_status = "ok"
    return True


async def _detect_params_from_doc(doc_content: str) -> list[dict]:
    """Use Ollama to detect parameters from documentation."""
    import json
    from mcp_manager.summarizer.ollama_client import ollama_generate

    content = doc_content[:6000]

    prompt = f"""Analyze this MCP server documentation and identify ALL required environment variables or configuration parameters.

For each parameter, return a JSON array with objects containing:
- "name": the exact environment variable name (e.g., "GITHUB_TOKEN")
- "description": what it's for (one sentence, English)
- "is_required": true or false
- "is_secret": true if token/key/password/credential

Return ONLY a valid JSON array. If none found, return [].

Documentation:
---
{content}
---

JSON array:"""

    try:
        response = await ollama_generate(prompt)
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1].rsplit("```", 1)[0]
        params = json.loads(response)
        if not isinstance(params, list):
            return []
        return [
            {
                "name": p["name"],
                "description": p.get("description", ""),
                "is_required": bool(p.get("is_required", False)),
                "is_secret": bool(p.get("is_secret", False)),
            }
            for p in params if isinstance(p, dict) and "name" in p
        ]
    except Exception:
        return []
