import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from mcp_manager.api.deps import get_db
from mcp_manager.db.models import InstallTarget

router = APIRouter(tags=["targets"])


class ModeSchema(BaseModel):
    runtime: str
    action_type: str
    template: str


class TargetCreate(BaseModel):
    name: str
    description: str | None = None
    modes: list[ModeSchema] = []


class TargetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    modes: list[ModeSchema] | None = None


def _serialize(t: InstallTarget) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "description": t.description,
        "modes": t.modes or [],
        "skill_modes": t.skill_modes or [],
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("/targets")
async def list_targets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InstallTarget).order_by(InstallTarget.name))
    targets = result.scalars().all()
    return [_serialize(t) for t in targets]


@router.get("/targets/{target_id}")
async def get_target(target_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InstallTarget).where(InstallTarget.id == target_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return _serialize(target)


@router.post("/targets", status_code=201)
async def create_target(body: TargetCreate, db: AsyncSession = Depends(get_db)):
    target = InstallTarget(
        name=body.name,
        description=body.description,
        modes=[m.model_dump() for m in body.modes],
    )
    db.add(target)
    await db.commit()
    await db.refresh(target)
    return _serialize(target)


@router.put("/targets/{target_id}")
async def update_target(target_id: uuid.UUID, body: TargetUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InstallTarget).where(InstallTarget.id == target_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    if body.name is not None:
        target.name = body.name
    if body.description is not None:
        target.description = body.description
    if body.modes is not None:
        target.modes = [m.model_dump() for m in body.modes]
    await db.commit()
    await db.refresh(target)
    return _serialize(target)
