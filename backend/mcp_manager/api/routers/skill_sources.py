"""Skill sources management — admin only for write, public for read."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_manager.api.deps import get_db
from mcp_manager.api.routers.auth import require_admin
from mcp_manager.db.models import SkillSource, Skill

router = APIRouter(tags=["skills"])


class SkillSourceCreate(BaseModel):
    name: str
    url: str
    type: str  # claude, copilot, gemini, cursor


class SkillSourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    type: str | None = None
    is_active: bool | None = None


@router.get("/skill-sources")
async def list_skill_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SkillSource).order_by(SkillSource.name))
    sources = result.scalars().all()
    return [_serialize_source(s) for s in sources]


@router.post("/skill-sources", status_code=201)
async def create_skill_source(
    body: SkillSourceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    source = SkillSource(
        name=body.name,
        url=body.url.rstrip("/"),
        type=body.type,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return _serialize_source(source)


@router.put("/skill-sources/{source_id}")
async def update_skill_source(
    source_id: uuid.UUID,
    body: SkillSourceUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(SkillSource).where(SkillSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Skill source not found")
    if body.name is not None:
        source.name = body.name
    if body.url is not None:
        source.url = body.url.rstrip("/")
    if body.type is not None:
        source.type = body.type
    if body.is_active is not None:
        source.is_active = body.is_active
    await db.commit()
    await db.refresh(source)
    return _serialize_source(source)


@router.delete("/skill-sources/{source_id}")
async def delete_skill_source(
    source_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(select(SkillSource).where(SkillSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Skill source not found")
    await db.delete(source)
    await db.commit()
    return {"status": "deleted"}


@router.get("/skills")
async def list_skills(
    source_id: uuid.UUID | None = None,
    target_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Skill)
    if source_id:
        query = query.where(Skill.skill_source_id == source_id)
    if target_type:
        query = query.where(Skill.target_type == target_type)
    query = query.order_by(Skill.name)
    result = await db.execute(query)
    skills = result.scalars().all()
    return [_serialize_skill(s) for s in skills]


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return _serialize_skill(skill)


def _serialize_source(s: SkillSource) -> dict:
    return {
        "id": str(s.id),
        "name": s.name,
        "url": s.url,
        "type": s.type,
        "branch_hash": s.branch_hash,
        "is_active": s.is_active,
        "last_sync": s.last_sync.isoformat() if s.last_sync else None,
        "last_sync_count": s.last_sync_count,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _serialize_skill(s: Skill) -> dict:
    return {
        "id": str(s.id),
        "skill_source_id": str(s.skill_source_id),
        "name": s.name,
        "description": s.description,
        "content": s.content,
        "target_type": s.target_type,
        "licence": s.licence,
        "source_url": s.source_url,
        "category": s.category,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
