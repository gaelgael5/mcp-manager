from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp_manager.config import settings
from mcp_manager.api.routers import services, summaries, installations, targets, sync, stats, parameters, search, openapi_search, health

def create_app() -> FastAPI:
    app = FastAPI(title="MCP Manager", version="0.1.0")
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
    return app
