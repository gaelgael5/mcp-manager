import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from mcp_manager.api.deps import get_db
from mcp_manager.db.models import InstallTarget

router = APIRouter(tags=["targets"])

class TargetCreate(BaseModel):
    name: str
    description: str | None = None

class TargetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

@router.get("/targets")
async def list_targets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InstallTarget).order_by(InstallTarget.name))
    targets = result.scalars().all()
    return [{"id": str(t.id), "name": t.name, "description": t.description,
             "created_at": t.created_at.isoformat() if t.created_at else None}
            for t in targets]

@router.post("/targets", status_code=201)
async def create_target(body: TargetCreate, db: AsyncSession = Depends(get_db)):
    target = InstallTarget(name=body.name, description=body.description)
    db.add(target)
    await db.commit()
    await db.refresh(target)
    return {"id": str(target.id), "name": target.name, "description": target.description,
            "created_at": target.created_at.isoformat() if target.created_at else None}

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
    await db.commit()
    return {"id": str(target.id), "name": target.name, "description": target.description,
            "created_at": target.created_at.isoformat() if target.created_at else None}
