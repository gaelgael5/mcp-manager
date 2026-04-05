from fastapi import APIRouter, Depends
from sqlalchemy import select, func, exists
from sqlalchemy.ext.asyncio import AsyncSession
from mcp_manager.api.deps import get_db
from mcp_manager.db.models import McpService, McpSummary, McpEmbedding, McpInstallation, McpParameter

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
        .order_by(func.count().desc())
        .limit(20)
    )
    by_category = {row[0]: row[1] for row in by_category_result}

    # Repo status
    repo_result = await db.execute(
        select(McpService.repo_status, func.count()).group_by(McpService.repo_status)
    )
    by_repo_status = {}
    for row in repo_result:
        key = row[0] or "unchecked"
        by_repo_status[key] = row[1]

    # Indexation stats
    with_summaries = (await db.execute(
        select(func.count(func.distinct(McpSummary.mcp_service_id)))
    )).scalar() or 0

    with_embeddings = (await db.execute(
        select(func.count(func.distinct(McpEmbedding.mcp_service_id)))
    )).scalar() or 0

    total_embeddings = (await db.execute(
        select(func.count()).select_from(McpEmbedding)
    )).scalar() or 0

    with_params = (await db.execute(
        select(func.count(func.distinct(McpParameter.mcp_service_id)))
    )).scalar() or 0

    with_installations = (await db.execute(
        select(func.count(func.distinct(McpInstallation.mcp_service_id)))
    )).scalar() or 0

    needs_reindex = (await db.execute(
        select(func.count()).select_from(McpService).where(McpService.needs_reindex == True)
    )).scalar() or 0

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
        "by_repo_status": by_repo_status,
        "indexation": {
            "with_summaries": with_summaries,
            "with_embeddings": with_embeddings,
            "total_embeddings": total_embeddings,
            "with_params": with_params,
            "with_installations": with_installations,
            "needs_reindex": needs_reindex,
            "outdated_summaries": outdated,
        },
    }
