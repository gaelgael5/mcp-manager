"""Public search API — designed for external consumers (agents, scripts, dashboards)."""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, exists, text, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_manager.api.deps import get_db
from mcp_manager.db.models import (
    McpService, McpSummary, McpInstallation, McpParameter,
    InstallTarget, McpEmbedding,
)

router = APIRouter(tags=["search"])


@router.get("/search")
async def search_services(
    q: str | None = Query(None, description="Full-text search in name and summaries"),
    semantic: bool = Query(False, description="Enable semantic search via embeddings (requires q)"),
    transport: str | None = Query(None, description="Filter by transport: stdio, sse, streamable-http"),
    category: str | None = Query(None, description="Filter by category"),
    source_type: str | None = Query(None, description="Filter by source"),
    repo_status: str | None = Query(None, description="Filter by repo status: ok, 404"),
    has_summaries: bool | None = Query(None, description="Filter by summary availability"),
    targets: str | None = Query(None, description="Comma-separated target names to include recipes for"),
    page: int = Query(1, ge=1, le=1000),
    per_page: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    # Semantic search path — uses pgvector similarity
    if q and semantic:
        return await _semantic_search(
            q=q, transport=transport, category=category, source_type=source_type,
            repo_status=repo_status, has_summaries=has_summaries, targets=targets,
            page=page, per_page=per_page, db=db,
        )

    # Standard text search path — uses PostgreSQL tsvector for performance
    query = select(McpService)

    if q:
        ts_query = func.plainto_tsquery("english", q)
        query = query.where(McpService.search_vector.op("@@")(ts_query))

    query = _apply_filters(query, transport, category, source_type, repo_status, has_summaries)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    if q:
        ts_query = func.plainto_tsquery("english", q)
        rank = func.ts_rank(McpService.search_vector, ts_query)
        query = query.order_by(rank.desc()).offset((page - 1) * per_page).limit(per_page)
    else:
        query = query.order_by(McpService.name).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    services = result.scalars().all()

    items = await _build_response_items(db, services, targets)

    return {"items": items, "total": total, "page": page, "per_page": per_page}


async def _semantic_search(
    q: str, transport, category, source_type, repo_status, has_summaries,
    targets, page, per_page, db: AsyncSession,
):
    """Search using vector similarity in pgvector."""
    from mcp_manager.indexer.embedder import embed_text

    # Embed the query
    query_vec = await embed_text(q)
    if not query_vec:
        # Fallback to text search if embedding fails
        return {"items": [], "total": 0, "page": page, "per_page": per_page}

    vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"

    # Build WHERE clauses dynamically
    where_parts = []
    params: dict = {"limit": per_page, "offset": (page - 1) * per_page}

    if transport:
        where_parts.append("s.transport = :transport")
        params["transport"] = transport
    if category:
        where_parts.append("s.category = :category")
        params["category"] = category
    if source_type:
        where_parts.append("s.source_type = :source_type")
        params["source_type"] = source_type
    if repo_status:
        where_parts.append("s.repo_status = :repo_status")
        params["repo_status"] = repo_status

    where_clause = (" AND " + " AND ".join(where_parts)) if where_parts else ""

    wrapped = text(f"""
        SELECT sub.mcp_service_id, sub.similarity
        FROM (
            SELECT DISTINCT ON (e.mcp_service_id)
                e.mcp_service_id,
                1 - (e.embedding <=> '{vec_str}'::vector) as similarity
            FROM mcp_embeddings e
            JOIN mcp_services s ON s.id = e.mcp_service_id
            WHERE 1=1 {where_clause}
            ORDER BY e.mcp_service_id, similarity DESC
        ) sub
        ORDER BY sub.similarity DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await db.execute(wrapped, params)
    rows = result.all()

    if not rows:
        return {"items": [], "total": 0, "page": page, "per_page": per_page}

    count_query = text(f"""
        SELECT COUNT(DISTINCT e.mcp_service_id)
        FROM mcp_embeddings e
        JOIN mcp_services s ON s.id = e.mcp_service_id
        WHERE 1=1 {where_clause}
    """)
    total = (await db.execute(count_query, params)).scalar() or 0

    # Load services in order
    service_ids = [row[0] for row in rows]
    similarity_scores = {row[0]: float(row[1]) for row in rows}

    services_result = await db.execute(
        select(McpService).where(McpService.id.in_(service_ids))
    )
    services_map = {s.id: s for s in services_result.scalars().all()}
    services = [services_map[sid] for sid in service_ids if sid in services_map]

    items = await _build_response_items(db, services, targets)

    # Add similarity score to each item
    for item in items:
        item["similarity"] = round(similarity_scores.get(uuid.UUID(item["id"]), 0), 4)

    return {"items": items, "total": total, "page": page, "per_page": per_page}


def _apply_filters(query, transport, category, source_type, repo_status, has_summaries):
    if transport:
        query = query.where(McpService.transport == transport)
    if category:
        query = query.where(McpService.category == category)
    if source_type:
        query = query.where(McpService.source_type == source_type)
    if repo_status:
        query = query.where(McpService.repo_status == repo_status)
    if has_summaries is not None:
        sub = select(McpSummary.id).where(McpSummary.mcp_service_id == McpService.id)
        if has_summaries:
            query = query.where(exists(sub))
        else:
            query = query.where(~exists(sub))
    return query


async def _build_response_items(
    db: AsyncSession, services: list[McpService], targets: str | None,
) -> list[dict]:
    """Build enriched response items for a list of services."""
    if not services:
        return []

    target_names: list[str] | None = None
    if targets:
        target_names = [t.strip() for t in targets.split(",") if t.strip()]

    targets_result = await db.execute(select(InstallTarget))
    all_targets = {t.id: t for t in targets_result.scalars().all()}
    target_name_to_id = {t.name: t.id for t in all_targets.values()}

    service_ids = [s.id for s in services]

    # Summaries (EN)
    summaries_result = await db.execute(
        select(McpSummary).where(
            McpSummary.mcp_service_id.in_(service_ids),
            McpSummary.culture == "en",
        )
    )
    summaries_map = {s.mcp_service_id: s.summary for s in summaries_result.scalars().all()}

    # Parameters
    params_result = await db.execute(
        select(McpParameter).where(McpParameter.mcp_service_id.in_(service_ids))
    )
    params_map: dict[uuid.UUID, list] = {}
    for p in params_result.scalars().all():
        params_map.setdefault(p.mcp_service_id, []).append({
            "name": p.name,
            "description": p.description,
            "is_required": p.is_required,
            "is_secret": p.is_secret,
        })

    # Installations
    install_query = select(McpInstallation).where(
        McpInstallation.mcp_service_id.in_(service_ids)
    )
    if target_names:
        target_ids = [target_name_to_id[n] for n in target_names if n in target_name_to_id]
        if target_ids:
            install_query = install_query.where(McpInstallation.install_target_id.in_(target_ids))

    installs_result = await db.execute(install_query)
    installs_map: dict[uuid.UUID, dict] = {}
    for inst in installs_result.scalars().all():
        target = all_targets.get(inst.install_target_id)
        if not target:
            continue
        installs_map.setdefault(inst.mcp_service_id, {})[target.name] = {
            "action_type": inst.action_type,
            "data": inst.data,
        }

    items = []
    for svc in services:
        items.append({
            "id": str(svc.id),
            "name": svc.name,
            "description": summaries_map.get(svc.id),
            "source_url": svc.source_url or None,
            "doc_url": svc.doc_url,
            "transport": svc.transport,
            "category": svc.category,
            "repo_status": svc.repo_status,
            "parameters": params_map.get(svc.id, []),
            "recipes": installs_map.get(svc.id, {}),
        })

    return items
