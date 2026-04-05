"""Health check and monitoring endpoints."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_manager.api.deps import get_db
from mcp_manager.db.models import McpService, McpSummary, McpEmbedding

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)

START_TIME = datetime.now(timezone.utc)


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Basic health check — verifies DB connection."""
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    uptime = (datetime.now(timezone.utc) - START_TIME).total_seconds()

    status = "healthy" if db_ok else "unhealthy"
    return {
        "status": status,
        "uptime_seconds": int(uptime),
        "database": "ok" if db_ok else "error",
    }


@router.get("/health/detailed")
async def detailed_health(db: AsyncSession = Depends(get_db)):
    """Detailed health with data quality metrics."""
    try:
        total = (await db.execute(select(func.count()).select_from(McpService))).scalar() or 0
        with_summaries = (await db.execute(
            select(func.count(func.distinct(McpSummary.mcp_service_id)))
        )).scalar() or 0
        with_embeddings = (await db.execute(
            select(func.count(func.distinct(McpEmbedding.mcp_service_id)))
        )).scalar() or 0
        needs_reindex = (await db.execute(
            select(func.count()).select_from(McpService).where(McpService.needs_reindex == True)
        )).scalar() or 0
        repos_ok = (await db.execute(
            select(func.count()).select_from(McpService).where(McpService.repo_status == "ok")
        )).scalar() or 0
        repos_404 = (await db.execute(
            select(func.count()).select_from(McpService).where(McpService.repo_status == "404")
        )).scalar() or 0

        # Check Ollama connectivity
        import httpx
        from mcp_manager.config import settings
        ollama_ok = False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/tags")
                ollama_ok = resp.status_code == 200
        except Exception:
            pass

        uptime = (datetime.now(timezone.utc) - START_TIME).total_seconds()

        return {
            "status": "healthy",
            "uptime_seconds": int(uptime),
            "database": "ok",
            "ollama": "ok" if ollama_ok else "unreachable",
            "data": {
                "total_services": total,
                "repos_ok": repos_ok,
                "repos_404": repos_404,
                "with_summaries": with_summaries,
                "with_embeddings": with_embeddings,
                "needs_reindex": needs_reindex,
                "summary_coverage": f"{round(with_summaries / total * 100, 1)}%" if total > 0 else "0%",
                "embedding_coverage": f"{round(with_embeddings / total * 100, 1)}%" if total > 0 else "0%",
            },
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }
