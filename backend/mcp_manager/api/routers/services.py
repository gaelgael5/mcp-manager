import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from mcp_manager.api.deps import get_db
from mcp_manager.db.models import McpService, McpSummary, PreferenceGroup, preference_group_services


class ServiceUpdate(BaseModel):
    source_url: str | None = None
    doc_url: str | None = None
    transport: str | None = None
    category: str | None = None

router = APIRouter(tags=["services"])

@router.get("/services")
async def list_services(
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
    source_type: str | None = None, category: str | None = None,
    transport: str | None = None, repo_status: str | None = None,
    has_summaries: bool | None = None,
    search: str | None = None, is_deprecated: bool | None = None,
    group_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(McpService)
    if group_id:
        query = query.join(
            preference_group_services,
            preference_group_services.c.mcp_service_id == McpService.id,
        ).where(preference_group_services.c.group_id == group_id)
    if source_type:
        query = query.where(McpService.source_type == source_type)
    if category:
        query = query.where(McpService.category == category)
    if transport:
        query = query.where(McpService.transport == transport)
    if repo_status == "404":
        query = query.where(McpService.repo_status == "404")
    elif repo_status == "ok":
        query = query.where(McpService.repo_status == "ok")
    elif repo_status == "none":
        query = query.where(McpService.repo_status.is_(None))
    if has_summaries is not None:
        from sqlalchemy import exists
        sub = select(McpSummary.id).where(McpSummary.parent_id == McpService._id)
        if has_summaries:
            query = query.where(exists(sub))
        else:
            query = query.where(~exists(sub))
    if is_deprecated is not None:
        query = query.where(McpService.is_deprecated == is_deprecated)
    if search:
        ts_query = func.plainto_tsquery("english", search)
        pattern = f"%{search}%"
        query = query.where(
            McpService.search_vector.op("@@")(ts_query)
            | McpService.name.ilike(pattern)
            | McpService.source_url.ilike(pattern)
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(McpService.name).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    services = result.scalars().all()

    # Batch fetch summary counts for these services
    service_ids = [s._id for s in services]
    summary_counts: dict[int, int] = {}
    if service_ids:
        sc_result = await db.execute(
            select(McpSummary.parent_id, func.count())
            .where(McpSummary.parent_id.in_(service_ids))
            .group_by(McpSummary.parent_id)
        )
        summary_counts = {row[0]: row[1] for row in sc_result}

    # Batch fetch public groups for these services
    groups_map: dict[str, list] = {}
    if service_ids:
        svc_uuids = [s.id for s in services]
        grp_result = await db.execute(
            select(
                preference_group_services.c.mcp_service_id,
                PreferenceGroup.id,
                PreferenceGroup.name,
            )
            .join(PreferenceGroup, preference_group_services.c.group_id == PreferenceGroup.id)
            .where(
                preference_group_services.c.mcp_service_id.in_(svc_uuids),
                PreferenceGroup.is_public == True,
            )
        )
        for svc_uuid, grp_id, grp_name in grp_result.all():
            groups_map.setdefault(str(svc_uuid), []).append({"id": str(grp_id), "name": grp_name})

    return {
        "items": [
            {**_serialize_service(s, summary_counts.get(s._id, 0)), "groups": groups_map.get(str(s.id), [])}
            for s in services
        ],
        "total": total, "page": page, "per_page": per_page,
    }

@router.get("/services/{service_id}")
async def get_service(service_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(McpService).where(McpService._id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    sc = await db.execute(
        select(func.count()).select_from(McpSummary).where(McpSummary.parent_id == service._id)
    )
    return _serialize_service(service, sc.scalar() or 0)

@router.patch("/services/{service_id}")
async def update_service(service_id: int, body: ServiceUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(McpService).where(McpService._id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    if body.source_url is not None:
        service.source_url = body.source_url
        service.repo_status = None  # Reset 404 status when URL changes
        if not service.doc_url:
            service.doc_url = body.source_url
    if body.doc_url is not None:
        service.doc_url = body.doc_url
    if body.transport is not None:
        service.transport = body.transport
    if body.category is not None:
        service.category = body.category
    await db.commit()
    await db.refresh(service)
    return _serialize_service(service)


def _serialize_service(s: McpService, summary_count: int = 0) -> dict:
    return {
        "id": s._id, "name": s.name, "source_url": s.source_url,
        "doc_url": s.doc_url, "doc_hash": s.doc_hash, "branch_hash": s.branch_hash,
        "source_type": s.source_type, "transport": s.transport,
        "category": s.category, "tags": s.tags or [],
        "repo_status": s.repo_status,
        "stars": s.stars,
        "canonical_id": s.canonical_id,
        "is_deprecated": s.is_deprecated,
        "has_summaries": summary_count > 0,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
