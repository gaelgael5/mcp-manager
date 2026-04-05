"""Indexation pipeline: fetch doc, embed, summarize, detect params, generate recipes.

Processes services with needs_reindex=TRUE, one at a time.
"""
import logging

from sqlalchemy import select, delete

from mcp_manager.db.session import SessionLocal
from mcp_manager.db.models import (
    McpService, McpSummary, McpParameter, McpInstallation,
    McpEmbedding, InstallTarget,
)
from mcp_manager.connectors.registry import get_connector
from mcp_manager.connectors.base import RawMcpService
from mcp_manager.summarizer.summarizer import generate_summary, CULTURES
from mcp_manager.summarizer.cleaner import clean_markdown
from mcp_manager.indexer.chunker import chunk_text
from mcp_manager.indexer.embedder import embed_text
from mcp_manager.exporters.engine import generate_from_modes
import mcp_manager.connectors  # noqa: F401

logger = logging.getLogger(__name__)


async def run_index(limit: int = 100) -> dict[str, int]:
    """Process up to `limit` services that need reindexing."""
    stats = {"processed": 0, "skipped_no_doc": 0, "summaries": 0, "embeddings": 0, "params": 0, "recipes": 0}

    batch_size = 10
    processed = 0

    while processed < limit:
        async with SessionLocal() as db:
            result = await db.execute(
                select(McpService)
                .where(McpService.needs_reindex == True)
                .where(McpService.source_url != "")
                .where(McpService.repo_status == "ok")
                .order_by(McpService.updated_at.desc())
                .limit(min(batch_size, limit - processed))
            )
            services = result.scalars().all()
            if not services:
                break

            for service in services:
                indexed = False
                try:
                    indexed = await _index_one(db, service, stats)
                except Exception:
                    logger.exception("Failed to index %s", service.name)

                if indexed:
                    service.needs_reindex = False
                processed += 1
                stats["processed"] += 1

            await db.commit()

        logger.info(
            "Index progress: %d processed (summaries: %d, embeddings: %d, params: %d, recipes: %d)",
            stats["processed"], stats["summaries"], stats["embeddings"],
            stats["params"], stats["recipes"],
        )

    return stats


async def _index_one(db, service: McpService, stats: dict) -> bool:
    """Index a single service. Returns True if content was generated."""

    # 1. Fetch documentation
    connector = get_connector(service.source_type)
    if not connector:
        stats["skipped_no_doc"] += 1
        return False

    raw = RawMcpService(
        name=service.name,
        source_url=service.source_url,
        source_type=service.source_type,
        doc_url=service.doc_url,
    )
    doc_content = await connector.fetch_doc_content(raw)
    if not doc_content:
        stats["skipped_no_doc"] += 1
        return False

    cleaned = clean_markdown(doc_content)
    if not cleaned:
        stats["skipped_no_doc"] += 1
        return False

    # 2. Generate summaries (en/fr)
    for culture in CULTURES:
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

    # 3. Embed into pgvector
    # Delete old embeddings
    await db.execute(
        delete(McpEmbedding).where(McpEmbedding.mcp_service_id == service.id)
    )

    # Embed summary (EN)
    en_summary = await db.execute(
        select(McpSummary.summary).where(
            McpSummary.mcp_service_id == service.id,
            McpSummary.culture == "en",
        )
    )
    en_summary_text = en_summary.scalar_one_or_none()
    if en_summary_text:
        vec = await embed_text(en_summary_text)
        if vec:
            db.add(McpEmbedding(
                mcp_service_id=service.id,
                chunk_type="summary",
                chunk_index=0,
                content=en_summary_text,
                embedding=vec,
            ))
            stats["embeddings"] += 1

    # Embed doc chunks
    chunks = chunk_text(cleaned)
    for i, chunk in enumerate(chunks[:10]):  # Max 10 chunks per service
        vec = await embed_text(chunk)
        if vec:
            db.add(McpEmbedding(
                mcp_service_id=service.id,
                chunk_type="doc_chunk",
                chunk_index=i,
                content=chunk,
                embedding=vec,
            ))
            stats["embeddings"] += 1

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
