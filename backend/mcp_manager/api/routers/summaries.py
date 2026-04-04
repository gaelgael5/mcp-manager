import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from mcp_manager.api.deps import get_db
from mcp_manager.db.models import McpSummary, McpService

router = APIRouter(tags=["summaries"])

@router.get("/summaries")
async def list_summaries(
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
    culture: str | None = None, mcp_service_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(McpSummary)
    if culture:
        query = query.where(McpSummary.culture == culture)
    if mcp_service_id:
        query = query.where(McpSummary.mcp_service_id == mcp_service_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    summaries = result.scalars().all()

    return {
        "items": [{"id": str(s.id), "mcp_service_id": str(s.mcp_service_id),
                    "culture": s.culture, "summary": s.summary,
                    "source_hash": s.source_hash,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None}
                   for s in summaries],
        "total": total, "page": page, "per_page": per_page,
    }

@router.get("/summaries/stats")
async def summaries_stats(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count()).select_from(McpSummary))).scalar() or 0

    # Count outdated: summaries where source_hash != service.doc_hash
    outdated_query = (
        select(func.count())
        .select_from(McpSummary)
        .join(McpService, McpSummary.mcp_service_id == McpService.id)
        .where(McpSummary.source_hash != McpService.doc_hash)
    )
    outdated = (await db.execute(outdated_query)).scalar() or 0

    by_culture_result = await db.execute(
        select(McpSummary.culture, func.count()).group_by(McpSummary.culture)
    )
    by_culture = {row[0]: row[1] for row in by_culture_result}

    return {"total": total, "outdated": outdated, "by_culture": by_culture}
