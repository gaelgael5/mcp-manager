"""Public search API — designed for external consumers (agents, scripts, dashboards)."""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, exists
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_manager.api.deps import get_db
from mcp_manager.db.models import McpService, McpSummary, McpInstallation, McpParameter, InstallTarget

router = APIRouter(tags=["search"])


@router.get("/search")
async def search_services(
    q: str | None = Query(None, description="Full-text search in name and summaries"),
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
    # Build base query
    query = select(McpService)

    if q:
        pattern = f"%{q}%"
        # Search in name + summaries
        summary_match = exists(
            select(McpSummary.id).where(
                McpSummary.mcp_service_id == McpService.id,
                McpSummary.summary.ilike(pattern),
            )
        )
        query = query.where(McpService.name.ilike(pattern) | summary_match)

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

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch services
    query = query.order_by(McpService.name).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    services = result.scalars().all()

    # Parse target filter
    target_names: list[str] | None = None
    if targets:
        target_names = [t.strip() for t in targets.split(",") if t.strip()]

    # Batch load targets map
    targets_result = await db.execute(select(InstallTarget))
    all_targets = {t.id: t for t in targets_result.scalars().all()}
    target_name_to_id = {t.name: t.id for t in all_targets.values()}

    # Batch load related data for these services
    service_ids = [s.id for s in services]
    items = []

    if service_ids:
        # Summaries (EN preferred)
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

        # Build response items
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

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
    }
