import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_manager.api.deps import get_db
from mcp_manager.db.models import McpParameter, McpService

router = APIRouter(tags=["parameters"])
logger = logging.getLogger(__name__)


class ParameterCreate(BaseModel):
    name: str
    description: str | None = None
    is_required: bool = False
    is_secret: bool = False


@router.get("/parameters/{service_id}")
async def list_parameters(service_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(McpParameter).where(McpParameter.mcp_service_id == service_id).order_by(McpParameter.name)
    )
    params = result.scalars().all()
    return [_serialize(p) for p in params]


@router.post("/parameters/{service_id}")
async def add_parameter(service_id: uuid.UUID, body: ParameterCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(McpService).where(McpService.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    param = McpParameter(
        mcp_service_id=service_id,
        parent_id=service._id,
        name=body.name,
        description=body.description,
        is_required=body.is_required,
        is_secret=body.is_secret,
        source="manual",
    )
    db.add(param)
    await db.commit()
    await db.refresh(param)
    return _serialize(param)


@router.delete("/parameters/{param_id}")
async def delete_parameter(param_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(McpParameter).where(McpParameter.id == param_id))
    param = result.scalar_one_or_none()
    if not param:
        raise HTTPException(status_code=404, detail="Parameter not found")
    await db.delete(param)
    await db.commit()
    return {"status": "deleted"}


async def detect_parameters_for_service(
    db: AsyncSession,
    service: McpService,
    doc_content: str | None = None,
) -> dict:
    """Detect parameters for a service via registry + AI and persist them.

    Two sources, fused by exact name:
      1. package_info.env_vars (source='registry')
      2. AI analysis of documentation (source='ai')

    Idempotent by parameter name: existing params for this service are kept
    as-is, only new names are inserted. The caller is responsible for the
    commit.

    If ``doc_content`` is not provided, it is fetched via the connector
    associated with ``service.source_type``.

    Returns ``{"detected": N, "added": N}``.
    """
    import mcp_manager.connectors  # noqa: F401
    from mcp_manager.connectors.registry import get_connector
    from mcp_manager.connectors.base import RawMcpService

    detected: list[dict] = []

    # Source 1: registry env_vars from connector sync
    pkg = service.package_info or {}
    for var_name, var_desc in (pkg.get("env_vars") or {}).items():
        lowered = var_name.lower()
        detected.append({
            "name": var_name,
            "description": var_desc or "",
            "is_required": True,
            "is_secret": "key" in lowered or "token" in lowered or "secret" in lowered,
            "source": "registry",
        })

    # Source 2: AI detection from documentation
    if doc_content is None:
        connector = get_connector(service.source_type)
        if connector:
            raw = RawMcpService(
                name=service.name,
                source_url=service.source_url,
                source_type=service.source_type,
                doc_url=service.doc_url,
            )
            try:
                doc_content = await connector.fetch_doc_content(raw)
            except Exception:
                logger.exception("Param detection: fetch_doc_content failed for %s", service.name)
                doc_content = None

    if doc_content:
        try:
            ai_params = await _detect_params_with_ai(doc_content)
        except Exception:
            logger.exception("Param detection: AI analysis failed for %s", service.name)
            ai_params = []
        known_names = {d["name"] for d in detected}
        for p in ai_params:
            if p["name"] not in known_names:
                detected.append(p)

    # Upsert: skip names that already exist for this service
    existing_names_q = await db.execute(
        select(McpParameter.name).where(McpParameter.mcp_service_id == service.id)
    )
    existing_names = {row[0] for row in existing_names_q.all()}

    added = 0
    for p in detected:
        if p["name"] in existing_names:
            continue
        stmt = pg_insert(McpParameter.__table__).values(
            mcp_service_id=service.id,
            parent_id=service._id,
            name=p["name"],
            description=p.get("description", ""),
            is_required=p.get("is_required", False),
            is_secret=p.get("is_secret", False),
            source=p.get("source", "ai"),
        ).on_conflict_do_nothing(index_elements=["mcp_service_id", "name"])
        await db.execute(stmt)
        existing_names.add(p["name"])
        added += 1

    return {"detected": len(detected), "added": added}


@router.post("/parameters/{service_id}/detect")
async def detect_parameters(service_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Detect parameters from sources + AI analysis of documentation."""
    result = await db.execute(select(McpService).where(McpService.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    stats = await detect_parameters_for_service(db, service)
    await db.commit()
    return {"status": "done", **stats}


async def _detect_params_with_ai(doc_content: str) -> list[dict]:
    from mcp_manager.summarizer.ollama_client import ollama_generate

    # Truncate doc
    content = doc_content[:6000] if len(doc_content) > 6000 else doc_content

    prompt = f"""Analyze this MCP server documentation and identify ALL required environment variables or configuration parameters.

For each parameter found, return a JSON array with objects containing:
- "name": the exact environment variable name (e.g., "GITHUB_TOKEN")
- "description": what this parameter is for (one sentence, in English)
- "is_required": true or false
- "is_secret": true if it's a token, key, password, or credential

Return ONLY a valid JSON array, nothing else. If no parameters found, return [].

Documentation:
---
{content}
---

JSON array:"""

    try:
        response = await ollama_generate(prompt)
        # Extract JSON from response
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1].rsplit("```", 1)[0]
        params = json.loads(response)
        if not isinstance(params, list):
            return []
        # Validate and clean
        result = []
        for p in params:
            if isinstance(p, dict) and "name" in p:
                result.append({
                    "name": p["name"],
                    "description": p.get("description", ""),
                    "is_required": bool(p.get("is_required", False)),
                    "is_secret": bool(p.get("is_secret", False)),
                    "source": "ai",
                })
        return result
    except Exception:
        logger.exception("AI parameter detection failed")
        return []


def _serialize(p: McpParameter) -> dict:
    return {
        "id": str(p.id),
        "mcp_service_id": str(p.mcp_service_id),
        "name": p.name,
        "description": p.description,
        "is_required": p.is_required,
        "is_secret": p.is_secret,
        "source": p.source,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
