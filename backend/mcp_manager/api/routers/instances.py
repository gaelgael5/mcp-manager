"""MCP Manager instances — federation management."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_manager.api.deps import get_db
from mcp_manager.api.routers.auth import require_admin
from mcp_manager.db.models import McpInstance

router = APIRouter(tags=["instances"])


class InstanceCreate(BaseModel):
    name: str
    url: str
    api_key: str | None = None


class InstanceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    api_key: str | None = None
    is_active: bool | None = None


@router.get("/instances")
async def list_instances(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(McpInstance).order_by(McpInstance.name))
    instances = result.scalars().all()
    return [_serialize(i) for i in instances]


@router.post("/instances", status_code=201)
async def create_instance(
    body: InstanceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    instance = McpInstance(
        name=body.name,
        url=body.url.rstrip("/"),
        api_key=body.api_key,
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    return _serialize(instance)


@router.put("/instances/{instance_id}")
async def update_instance(
    instance_id: uuid.UUID,
    body: InstanceUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(McpInstance).where(McpInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    if body.name is not None:
        instance.name = body.name
    if body.url is not None:
        instance.url = body.url.rstrip("/")
    if body.api_key is not None:
        instance.api_key = body.api_key
    if body.is_active is not None:
        instance.is_active = body.is_active
    await db.commit()
    await db.refresh(instance)
    return _serialize(instance)


@router.delete("/instances/{instance_id}")
async def delete_instance(
    instance_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(McpInstance).where(McpInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    await db.delete(instance)
    await db.commit()
    return {"status": "deleted"}


def _serialize(i: McpInstance) -> dict:
    return {
        "id": str(i.id),
        "name": i.name,
        "url": i.url,
        "has_api_key": bool(i.api_key),
        "is_active": i.is_active,
        "last_sync": i.last_sync.isoformat() if i.last_sync else None,
        "last_sync_count": i.last_sync_count,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }
