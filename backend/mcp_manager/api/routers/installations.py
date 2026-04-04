import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from mcp_manager.api.deps import get_db
from mcp_manager.db.models import McpInstallation

router = APIRouter(tags=["installations"])

class InstallationUpdate(BaseModel):
    action_type: str | None = None
    data: str | None = None
    env_vars: dict[str, str] | None = None

@router.get("/installations")
async def list_installations(
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
    install_target_id: uuid.UUID | None = None,
    mcp_service_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(McpInstallation)
    if install_target_id:
        query = query.where(McpInstallation.install_target_id == install_target_id)
    if mcp_service_id:
        query = query.where(McpInstallation.mcp_service_id == mcp_service_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    installations = result.scalars().all()

    return {
        "items": [_serialize_installation(i) for i in installations],
        "total": total, "page": page, "per_page": per_page,
    }

@router.get("/installations/{installation_id}")
async def get_installation(installation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(McpInstallation).where(McpInstallation.id == installation_id))
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail="Installation not found")
    return _serialize_installation(inst)

@router.put("/installations/{installation_id}")
async def update_installation(installation_id: uuid.UUID, body: InstallationUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(McpInstallation).where(McpInstallation.id == installation_id))
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail="Installation not found")
    if body.action_type is not None:
        inst.action_type = body.action_type
    if body.data is not None:
        inst.data = body.data
    if body.env_vars is not None:
        inst.env_vars = body.env_vars
    await db.commit()
    return _serialize_installation(inst)

def _serialize_installation(i: McpInstallation) -> dict:
    return {
        "id": str(i.id), "mcp_service_id": str(i.mcp_service_id),
        "install_target_id": str(i.install_target_id),
        "action_type": i.action_type, "data": i.data,
        "env_vars": i.env_vars or {},
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
    }
