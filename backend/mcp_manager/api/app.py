from dotenv import load_dotenv
load_dotenv("/app/.env", override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp_manager.config import settings
from mcp_manager.api.routers import services, summaries, installations, targets, sync, stats, parameters, search, openapi_search, health, auth, api_keys, instances, skill_sources, community_sync, preference_groups
from mcp_manager.api.routers import settings as settings_router
from mcp_manager.api.rate_limit import RateLimitMiddleware

def create_app() -> FastAPI:
    app = FastAPI(title="MCP Manager", version="0.1.0")

    @app.on_event("startup")
    async def resume_interrupted_processes():
        import asyncio
        import logging
        from sqlalchemy import update, select, func, or_
        from mcp_manager.db.session import SessionLocal
        from mcp_manager.db.models import SkillSource, McpService, Skill
        from mcp_manager.api.routers.sync import _sync_status, _run_enrich_skills_bg, _run_index_bg, _run_index_skills_bg
        _logger = logging.getLogger("startup")

        # Load API token pool at startup
        from mcp_manager.connectors.token_pool import load_tokens
        await load_tokens()

        async with SessionLocal() as db:
            # 1. Reset enriching -> pending
            result = await db.execute(
                update(SkillSource)
                .where(SkillSource.enrichment_status == "enriching")
                .values(enrichment_status="pending")
            )
            await db.commit()
            if result.rowcount > 0:
                _logger.info("startup: reset %d interrupted enrichments to pending", result.rowcount)

            # 2. Count pending enrichments
            count_result = await db.execute(
                select(func.count()).select_from(SkillSource).where(
                    or_(
                        SkillSource.enrichment_status == "pending",
                        SkillSource.enrichment_status.is_(None),
                    )
                )
            )
            pending_enrich = count_result.scalar() or 0

            # 3. Count services needing reindex
            count_result = await db.execute(
                select(func.count()).select_from(McpService).where(
                    McpService.needs_reindex == True
                )
            )
            pending_index = count_result.scalar() or 0

        # Auto-launch enrich pipeline
        if pending_enrich > 0:
            _logger.info("startup: %d pending enrichments, auto-launching enrich pipeline", pending_enrich)
            _sync_status["enriching"] = True
            _sync_status["enrich_cancel"] = False
            asyncio.create_task(_run_enrich_skills_bg())

        # Auto-launch index pipeline
        if pending_index > 0:
            _logger.info("startup: %d services need reindex, auto-launching index pipeline", pending_index)
            _sync_status["indexing"] = True
            asyncio.create_task(_run_index_bg(pending_index))

        # 4. Count skills needing summary
        async with SessionLocal() as db:
            count_result = await db.execute(
                select(func.count()).select_from(Skill).where(
                    Skill.needs_summary == True
                )
            )
            pending_skills = count_result.scalar() or 0

        if pending_skills > 0:
            _logger.info("startup: %d skills need summary, auto-launching index-skills pipeline", pending_skills)
            _sync_status["indexing_skills"] = True
            _sync_status["index_skills_cancel"] = False
            asyncio.create_task(_run_index_skills_bg())

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins,
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    )
    app.include_router(services.router, prefix="/api/v1")
    app.include_router(summaries.router, prefix="/api/v1")
    app.include_router(installations.router, prefix="/api/v1")
    app.include_router(targets.router, prefix="/api/v1")
    app.include_router(sync.router, prefix="/api/v1")
    app.include_router(stats.router, prefix="/api/v1")
    app.include_router(parameters.router, prefix="/api/v1")
    app.include_router(search.router, prefix="/api/v1")
    app.include_router(openapi_search.router, prefix="/api/v1")
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(api_keys.router, prefix="/api/v1")
    app.include_router(instances.router, prefix="/api/v1")
    app.include_router(settings_router.router, prefix="/api/v1")
    app.include_router(skill_sources.router, prefix="/api/v1")
    app.include_router(community_sync.router, prefix="/api/v1")
    app.include_router(preference_groups.router, prefix="/api/v1")
    return app
