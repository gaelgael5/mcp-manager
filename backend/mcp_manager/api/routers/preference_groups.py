import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_manager.api.deps import get_db
from mcp_manager.api.routers.auth import require_authenticated
from mcp_manager.db.models import (
    McpService,
    PreferenceGroup,
    Skill,
    preference_group_services,
    preference_group_skills,
)

router = APIRouter(tags=["preference-groups"])
logger = logging.getLogger(__name__)


class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


async def _require_user_id(user: dict) -> str:
    uid = user.get("user_id")
    if uid:
        return uid
    email = user.get("email")
    if not email or email == "api_key":
        raise HTTPException(status_code=403, detail="Preference groups require Google login (API keys not supported)")
    from mcp_manager.api.routers.auth import _upsert_user
    return await _upsert_user(email, user.get("name", ""), user.get("picture", ""))


async def _get_user_group(
    db: AsyncSession, group_id: uuid.UUID, user_id: str
) -> PreferenceGroup:
    """Fetch a preference group and verify ownership. Raises 404 if not found or not owned."""
    result = await db.execute(
        select(PreferenceGroup).where(PreferenceGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    if not group or str(group.user_id) != user_id:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


@router.get("/preference-groups")
async def list_groups(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_authenticated),
):
    user_id = await _require_user_id(user)

    service_count_sq = (
        select(func.count())
        .select_from(preference_group_services)
        .where(preference_group_services.c.group_id == PreferenceGroup.id)
        .correlate(PreferenceGroup)
        .scalar_subquery()
    )
    skill_count_sq = (
        select(func.count())
        .select_from(preference_group_skills)
        .where(preference_group_skills.c.group_id == PreferenceGroup.id)
        .correlate(PreferenceGroup)
        .scalar_subquery()
    )

    result = await db.execute(
        select(
            PreferenceGroup.id,
            PreferenceGroup.name,
            PreferenceGroup.description,
            PreferenceGroup.created_at,
            service_count_sq.label("service_count"),
            skill_count_sq.label("skill_count"),
        )
        .where(PreferenceGroup.user_id == user_id)
        .order_by(PreferenceGroup.created_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "description": r.description,
            "service_count": r.service_count or 0,
            "skill_count": r.skill_count or 0,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/preference-groups")
async def create_group(
    body: GroupCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_authenticated),
):
    user_id = await _require_user_id(user)
    group = PreferenceGroup(
        user_id=user_id,
        name=body.name,
        description=body.description,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return {
        "id": str(group.id),
        "name": group.name,
        "description": group.description,
    }


@router.get("/preference-groups/{group_id}")
async def get_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_authenticated),
):
    user_id = await _require_user_id(user)
    group = await _get_user_group(db, group_id, user_id)

    # Eagerly load services and skills
    svc_result = await db.execute(
        select(McpService.id, McpService.name, McpService.source_type, McpService.category)
        .join(preference_group_services, preference_group_services.c.mcp_service_id == McpService.id)
        .where(preference_group_services.c.group_id == group_id)
    )
    services = [
        {"id": str(r.id), "name": r.name, "source_type": r.source_type, "category": r.category}
        for r in svc_result.all()
    ]

    skill_result = await db.execute(
        select(Skill.id, Skill.name, Skill.target_type, Skill.category)
        .join(preference_group_skills, preference_group_skills.c.skill_id == Skill.id)
        .where(preference_group_skills.c.group_id == group_id)
    )
    skills = [
        {"id": str(r.id), "name": r.name, "target_type": r.target_type, "category": r.category}
        for r in skill_result.all()
    ]

    return {
        "id": str(group.id),
        "name": group.name,
        "description": group.description,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "updated_at": group.updated_at.isoformat() if group.updated_at else None,
        "services": services,
        "skills": skills,
    }


@router.put("/preference-groups/{group_id}")
async def update_group(
    group_id: uuid.UUID,
    body: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_authenticated),
):
    user_id = await _require_user_id(user)
    group = await _get_user_group(db, group_id, user_id)

    if body.name is not None:
        group.name = body.name
    if body.description is not None:
        group.description = body.description

    await db.commit()
    await db.refresh(group)
    return {
        "id": str(group.id),
        "name": group.name,
        "description": group.description,
    }


@router.delete("/preference-groups/{group_id}")
async def delete_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_authenticated),
):
    user_id = await _require_user_id(user)
    group = await _get_user_group(db, group_id, user_id)
    await db.delete(group)
    await db.commit()
    return {"status": "deleted"}


@router.post("/preference-groups/{group_id}/services/{service_id}")
async def add_service_to_group(
    group_id: uuid.UUID,
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_authenticated),
):
    user_id = await _require_user_id(user)
    await _get_user_group(db, group_id, user_id)

    stmt = pg_insert(preference_group_services).values(
        group_id=group_id, mcp_service_id=service_id
    ).on_conflict_do_nothing()
    await db.execute(stmt)
    await db.commit()
    return {"status": "added"}


@router.delete("/preference-groups/{group_id}/services/{service_id}")
async def remove_service_from_group(
    group_id: uuid.UUID,
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_authenticated),
):
    user_id = await _require_user_id(user)
    await _get_user_group(db, group_id, user_id)

    await db.execute(
        delete(preference_group_services).where(
            preference_group_services.c.group_id == group_id,
            preference_group_services.c.mcp_service_id == service_id,
        )
    )
    await db.commit()
    return {"status": "removed"}


@router.post("/preference-groups/{group_id}/skills/{skill_id}")
async def add_skill_to_group(
    group_id: uuid.UUID,
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_authenticated),
):
    user_id = await _require_user_id(user)
    await _get_user_group(db, group_id, user_id)

    stmt = pg_insert(preference_group_skills).values(
        group_id=group_id, skill_id=skill_id
    ).on_conflict_do_nothing()
    await db.execute(stmt)
    await db.commit()
    return {"status": "added"}


@router.delete("/preference-groups/{group_id}/skills/{skill_id}")
async def remove_skill_from_group(
    group_id: uuid.UUID,
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_authenticated),
):
    user_id = await _require_user_id(user)
    await _get_user_group(db, group_id, user_id)

    await db.execute(
        delete(preference_group_skills).where(
            preference_group_skills.c.group_id == group_id,
            preference_group_skills.c.skill_id == skill_id,
        )
    )
    await db.commit()
    return {"status": "removed"}


@router.get("/services/{service_id}/groups")
async def list_groups_for_service(
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_authenticated),
):
    user_id = await _require_user_id(user)
    result = await db.execute(
        select(PreferenceGroup.id, PreferenceGroup.name)
        .join(preference_group_services, preference_group_services.c.group_id == PreferenceGroup.id)
        .where(
            preference_group_services.c.mcp_service_id == service_id,
            PreferenceGroup.user_id == user_id,
        )
    )
    return [{"id": str(r.id), "name": r.name} for r in result.all()]


@router.get("/skills/{skill_id}/groups")
async def list_groups_for_skill(
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_authenticated),
):
    user_id = await _require_user_id(user)
    result = await db.execute(
        select(PreferenceGroup.id, PreferenceGroup.name)
        .join(preference_group_skills, preference_group_skills.c.group_id == PreferenceGroup.id)
        .where(
            preference_group_skills.c.skill_id == skill_id,
            PreferenceGroup.user_id == user_id,
        )
    )
    return [{"id": str(r.id), "name": r.name} for r in result.all()]
