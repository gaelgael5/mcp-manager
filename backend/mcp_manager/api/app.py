from dotenv import load_dotenv
load_dotenv("/app/.env", override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp_manager.config import settings
from mcp_manager.api.routers import services, summaries, installations, targets, sync, stats, parameters, search, openapi_search, health, auth, api_keys, instances, community_sync, preference_groups
from mcp_manager.api.routers import settings as settings_router
from mcp_manager.api.rate_limit import RateLimitMiddleware

def create_app() -> FastAPI:
    app = FastAPI(title="MCP Manager", version="0.1.0")

    @app.on_event("startup")
    async def resume_interrupted_processes():
        import asyncio
        import logging
        from sqlalchemy import select, func
        from mcp_manager.db.session import SessionLocal
        from mcp_manager.db.models import McpService
        from mcp_manager.api.routers.sync import _sync_status, _run_index_bg
        _logger = logging.getLogger("startup")

        # Load API token pool at startup
        from mcp_manager.connectors.token_pool import load_tokens
        await load_tokens()

        async with SessionLocal() as db:
            count_result = await db.execute(
                select(func.count()).select_from(McpService).where(
                    McpService.needs_reindex == True
                )
            )
            pending_index = count_result.scalar() or 0

        # Auto-launch index pipeline
        if pending_index > 0:
            _logger.info("startup: %d services need reindex, auto-launching index pipeline", pending_index)
            _sync_status["indexing"] = True
            asyncio.create_task(_run_index_bg(pending_index))

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
    app.include_router(community_sync.router, prefix="/api/v1")
    app.include_router(preference_groups.router, prefix="/api/v1")
    return app
