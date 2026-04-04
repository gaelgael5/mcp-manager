from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from mcp_manager.api.deps import get_db
from mcp_manager.db.models import McpService, McpSummary

router = APIRouter(tags=["stats"])

@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_services = (await db.execute(select(func.count()).select_from(McpService))).scalar() or 0

    by_source_result = await db.execute(
        select(McpService.source_type, func.count()).group_by(McpService.source_type)
    )
    by_source = {row[0]: row[1] for row in by_source_result}

    by_category_result = await db.execute(
        select(McpService.category, func.count())
        .where(McpService.category.isnot(None))
        .group_by(McpService.category)
    )
    by_category = {row[0]: row[1] for row in by_category_result}

    outdated_query = (
        select(func.count()).select_from(McpSummary)
        .join(McpService, McpSummary.mcp_service_id == McpService.id)
        .where(McpSummary.source_hash != McpService.doc_hash)
    )
    outdated = (await db.execute(outdated_query)).scalar() or 0

    return {
        "total_services": total_services,
        "by_source": by_source,
        "by_category": by_category,
        "outdated_summaries": outdated,
    }
