import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from mcp_manager.api.deps import get_db
from mcp_manager.db.models import McpService


class ServiceUpdate(BaseModel):
    source_url: str | None = None
    doc_url: str | None = None

router = APIRouter(tags=["services"])

@router.get("/services")
async def list_services(
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
    source_type: str | None = None, category: str | None = None,
    search: str | None = None, is_deprecated: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(McpService)
    if source_type:
        query = query.where(McpService.source_type == source_type)
    if category:
        query = query.where(McpService.category == category)
    if is_deprecated is not None:
        query = query.where(McpService.is_deprecated == is_deprecated)
    if search:
        pattern = f"%{search}%"
        query = query.where(McpService.name.ilike(pattern) | McpService.source_url.ilike(pattern))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(McpService.name).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    services = result.scalars().all()

    return {
        "items": [_serialize_service(s) for s in services],
        "total": total, "page": page, "per_page": per_page,
    }

@router.get("/services/{service_id}")
async def get_service(service_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(McpService).where(McpService.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return _serialize_service(service)

@router.patch("/services/{service_id}")
async def update_service(service_id: uuid.UUID, body: ServiceUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(McpService).where(McpService.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    if body.source_url is not None:
        service.source_url = body.source_url
        if not service.doc_url:
            service.doc_url = body.source_url
    if body.doc_url is not None:
        service.doc_url = body.doc_url
    await db.commit()
    await db.refresh(service)
    return _serialize_service(service)


def _serialize_service(s: McpService) -> dict:
    return {
        "id": str(s.id), "name": s.name, "source_url": s.source_url,
        "doc_url": s.doc_url, "doc_hash": s.doc_hash, "branch_hash": s.branch_hash,
        "source_type": s.source_type, "transport": s.transport,
        "category": s.category, "tags": s.tags or [],
        "is_deprecated": s.is_deprecated,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
