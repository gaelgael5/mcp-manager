"""Community sync API.

Exposes a cursor-paginated sync endpoint for community nodes that want to
replicate the MCP catalog. Authentication via existing API keys.

Design:
- Single POST endpoint that takes a JSON body with {table, cursor, since, limit}
- Cursor is the `_id` BIGINT auto-increment column, strict `_id > cursor`
- Diff mode: optional `since` filter on `updated_at >= since`
- Client detects end of stream when returned count < limit
- Response includes `server_time` so clients avoid clock skew when tracking
  the next `since` value.

Tables exposed (8): mcp_services, mcp_summaries, mcp_parameters,
mcp_installations, skill_sources, skill_sources_translations, skills,
skills_translations.
"""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_manager.api.deps import get_db
from mcp_manager.db.models import (
    ApiKey,
    McpInstallation,
    McpParameter,
    McpService,
    McpSummary,
    Skill,
    SkillSource,
    SkillSourceTranslation,
    SkillTranslation,
)

router = APIRouter(tags=["community_sync"])
logger = logging.getLogger(__name__)


DEFAULT_LIMIT = 200
MAX_LIMIT = 500


class SyncRequest(BaseModel):
    table: str = Field(..., description="Table to sync (whitelisted)")
    cursor: int = Field(0, ge=0, description="Last _id seen; 0 = start from beginning")
    since: datetime | None = Field(None, description="Optional diff filter on updated_at")
    limit: int = Field(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)


class SyncResponse(BaseModel):
    table: str
    items: list[dict]
    next_cursor: int
    count: int
    server_time: datetime


async def _require_api_key(request: Request, db: AsyncSession) -> ApiKey:
    """Validate API key from X-API-Key or Authorization: Bearer mcp_..."""
    key = request.headers.get("X-API-Key", "")
    if not key:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer mcp_"):
            key = auth[7:]
    if not key:
        raise HTTPException(status_code=401, detail="API key required")

    key_hash = hashlib.sha256(key.encode()).hexdigest()
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="API key expired")
    return api_key


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _serialize_mcp_service(row: McpService) -> dict:
    return {
        "_id": row._id,
        "id": str(row.id),
        "name": row.name,
        "source_url": row.source_url,
        "doc_url": row.doc_url,
        "source_type": row.source_type,
        "transport": row.transport,
        "category": row.category,
        "tags": row.tags or [],
        "package_info": row.package_info or {},
        "source_origins": row.source_origins or [],
        "repo_status": row.repo_status,
        "is_deprecated": row.is_deprecated,
        "stars": row.stars,
        "canonical_id": row.canonical_id,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _serialize_mcp_summary(row: McpSummary) -> dict:
    return {
        "_id": row._id,
        "parent_id": row.parent_id,
        "id": str(row.id),
        "mcp_service_id": str(row.mcp_service_id),
        "culture": row.culture,
        "summary": row.summary,
        "heuristic_quality": row.heuristic_quality,
        "llm_quality": row.llm_quality,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _serialize_mcp_parameter(row: McpParameter) -> dict:
    return {
        "_id": row._id,
        "parent_id": row.parent_id,
        "id": str(row.id),
        "mcp_service_id": str(row.mcp_service_id),
        "name": row.name,
        "description": row.description,
        "is_required": row.is_required,
        "is_secret": row.is_secret,
        "source": row.source,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _serialize_mcp_installation(row: McpInstallation) -> dict:
    return {
        "_id": row._id,
        "parent_id": row.parent_id,
        "id": str(row.id),
        "mcp_service_id": str(row.mcp_service_id),
        "install_target_id": str(row.install_target_id),
        "action_type": row.action_type,
        "data": row.data,
        "env_vars": row.env_vars or {},
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _serialize_skill_source(row: SkillSource) -> dict:
    return {
        "_id": row._id,
        "id": str(row.id),
        "name": row.name,
        "url": row.url,
        "repo_url": row.repo_url,
        "skills_path": row.skills_path,
        "type": row.type,
        "description": row.description,
        "repo_format": row.repo_format,
        "repo_status": row.repo_status,
        "is_active": row.is_active,
        "stars": row.stars,
        "last_sync": _iso(row.last_sync),
        "last_sync_count": row.last_sync_count,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _serialize_skill_source_translation(row: SkillSourceTranslation) -> dict:
    return {
        "_id": row._id,
        "parent_id": row.parent_id,
        "id": str(row.id),
        "skill_source_id": str(row.skill_source_id),
        "culture": row.culture,
        "summary": row.summary,
        "heuristic_quality": row.heuristic_quality,
        "llm_quality": row.llm_quality,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _serialize_skill(row: Skill) -> dict:
    return {
        "_id": row._id,
        "id": str(row.id),
        "name": row.name,
        "description": row.description,
        "target_type": row.target_type,
        "licence": row.licence,
        "licence_url": row.licence_url,
        "source_url": row.source_url,
        "category": row.category,
        "install_command": row.install_command,
        "weekly_installs": row.weekly_installs,
        "canonical_id": row.canonical_id,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _serialize_skill_translation(row: SkillTranslation) -> dict:
    return {
        "_id": row._id,
        "parent_id": row.parent_id,
        "id": str(row.id),
        "skill_id": str(row.skill_id),
        "culture": row.culture,
        "summary": row.summary,
        "heuristic_quality": row.heuristic_quality,
        "llm_quality": row.llm_quality,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


# Whitelist of syncable tables: maps the table name to (ORM model, serializer).
# Adding a table here is the only place where the exposed contract changes.
TABLES: dict[str, tuple[type, Callable]] = {
    "mcp_services": (McpService, _serialize_mcp_service),
    "mcp_summaries": (McpSummary, _serialize_mcp_summary),
    "mcp_parameters": (McpParameter, _serialize_mcp_parameter),
    "mcp_installations": (McpInstallation, _serialize_mcp_installation),
    "skill_sources": (SkillSource, _serialize_skill_source),
    "skill_sources_translations": (SkillSourceTranslation, _serialize_skill_source_translation),
    "skills": (Skill, _serialize_skill),
    "skills_translations": (SkillTranslation, _serialize_skill_translation),
}


@router.post("/community/sync", response_model=SyncResponse)
async def community_sync(
    body: SyncRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    """Cursor-paginated sync endpoint for community nodes.

    Full mode: omit `since`, paginate through the whole table ordered by `_id`.
    Diff mode: pass `since` (ISO-8601 with tz offset) to only get rows where
    `updated_at >= since`. The client should store `response.server_time` and
    use it as the next `since` value to avoid clock skew.
    """
    await _require_api_key(request, db)

    entry = TABLES.get(body.table)
    if entry is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown table '{body.table}'. Allowed: {sorted(TABLES)}",
        )
    model, serializer = entry

    stmt = select(model).where(model._id > body.cursor)
    if body.since is not None:
        stmt = stmt.where(model.updated_at >= body.since)
    stmt = stmt.order_by(model._id.asc()).limit(body.limit)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    items = [serializer(r) for r in rows]
    next_cursor = rows[-1]._id if rows else body.cursor

    return SyncResponse(
        table=body.table,
        items=items,
        next_cursor=next_cursor,
        count=len(items),
        server_time=datetime.now(timezone.utc),
    )
