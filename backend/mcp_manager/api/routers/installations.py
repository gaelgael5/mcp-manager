import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from mcp_manager.api.deps import get_db
from mcp_manager.db.models import McpInstallation, McpService, InstallTarget

router = APIRouter(tags=["installations"])

class InstallationUpdate(BaseModel):
    action_type: str | None = None
    data: str | None = None
    env_vars: dict[str, str] | None = None

@router.get("/installations")
async def list_installations(
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
    install_target_id: uuid.UUID | None = None,
    service_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(McpInstallation)
    if install_target_id:
        query = query.where(McpInstallation.install_target_id == install_target_id)
    if service_id:
        query = query.join(McpService, McpInstallation.mcp_service_id == McpService.id).where(McpService._id == service_id)

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

@router.post("/installations/generate/{service_id}")
async def generate_installations(service_id: int, db: AsyncSession = Depends(get_db)):
    """Generate installation recipes for all targets for a single service."""
    from mcp_manager.exporters.engine import generate_from_modes, generate_installation_data

    result = await db.execute(select(McpService).where(McpService._id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    targets_result = await db.execute(select(InstallTarget))
    targets = targets_result.scalars().all()

    pkg = service.package_info or {}

    generated = []
    for target in targets:
        # Use target modes from DB if available, else fallback to legacy
        if target.modes:
            data = generate_from_modes(
                modes=target.modes,
                runtime_hint=pkg.get("runtime_hint"),
                package_identifier=pkg.get("package_identifier"),
                service_name=service.name,
                env_vars=pkg.get("env_vars", {}),
            )
        else:
            data = generate_installation_data(
                registry_type=pkg.get("registry_type"),
                package_identifier=pkg.get("package_identifier"),
                runtime_hint=pkg.get("runtime_hint"),
                transport=service.transport,
                target_name=target.name,
                service_name=service.name,
                env_vars=pkg.get("env_vars", {}),
            )
        if not data:
            continue

        existing = await db.execute(
            select(McpInstallation).where(
                McpInstallation.mcp_service_id == service.id,
                McpInstallation.install_target_id == target.id,
            )
        )
        install_row = existing.scalar_one_or_none()
        if install_row:
            install_row.action_type = data["action_type"]
            install_row.data = data["data"]
        else:
            db.add(McpInstallation(
                mcp_service_id=service.id,
                install_target_id=target.id,
                action_type=data["action_type"],
                data=data["data"],
            ))
        generated.append(target.name)

    await db.commit()
    return {"status": "done", "service_id": str(service_id), "targets": generated}


def _serialize_installation(i: McpInstallation) -> dict:
    return {
        "id": i._id, "service_id": i.parent_id,
        "install_target_id": str(i.install_target_id),
        "action_type": i.action_type, "data": i.data,
        "env_vars": i.env_vars or {},
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
    }
