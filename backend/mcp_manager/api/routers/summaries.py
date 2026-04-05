import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
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


@router.post("/summaries/generate/{service_id}")
async def generate_for_service(
    service_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Generate summaries (en + fr) for a single service."""
    result = await db.execute(select(McpService).where(McpService.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    background_tasks.add_task(_generate_summaries_for_service, service_id)
    return {"status": "started", "service_id": str(service_id)}


async def _generate_summaries_for_service(service_id: uuid.UUID) -> None:
    import logging
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.connectors.registry import get_connector
    from mcp_manager.connectors.base import RawMcpService
    from mcp_manager.summarizer.summarizer import generate_summary, CULTURES

    import mcp_manager.connectors.docker_registry  # noqa: F401
    import mcp_manager.connectors.mcp_registry  # noqa: F401
    import mcp_manager.connectors.mcp_servers_repo  # noqa: F401

    logger = logging.getLogger(__name__)

    async with SessionLocal() as db:
        result = await db.execute(select(McpService).where(McpService.id == service_id))
        service = result.scalar_one_or_none()
        if not service:
            return

        connector = get_connector(service.source_type)
        if not connector:
            logger.warning("No connector for source_type: %s", service.source_type)
            return

        raw = RawMcpService(
            name=service.name,
            source_url=service.source_url,
            source_type=service.source_type,
            doc_url=service.doc_url,
        )
        doc_content = await connector.fetch_doc_content(raw)
        if not doc_content:
            logger.warning("No doc content for service: %s", service.name)
            return

        for culture in CULTURES:
            summary_text = await generate_summary(doc_content, culture)
            if not summary_text:
                continue

            existing = await db.execute(
                select(McpSummary).where(
                    McpSummary.mcp_service_id == service.id,
                    McpSummary.culture == culture,
                )
            )
            summary_row = existing.scalar_one_or_none()
            if summary_row:
                summary_row.summary = summary_text
                summary_row.source_hash = service.doc_hash
            else:
                db.add(McpSummary(
                    mcp_service_id=service.id,
                    culture=culture,
                    summary=summary_text,
                    source_hash=service.doc_hash,
                ))

        await db.commit()
        logger.info("Summaries generated for: %s", service.name)
