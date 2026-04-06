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
    skills_path: str = "skills"
    type: str  # claude, copilot, gemini, cursor


class SkillSourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    skills_path: str | None = None
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
        skills_path=body.skills_path,
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
    if body.skills_path is not None:
        source.skills_path = body.skills_path
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


@router.post("/skills/{skill_id}/generate-summary")
async def generate_skill_summary(
    skill_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Generate summary for a single skill."""
    import os
    from mcp_manager.summarizer.ollama_client import ollama_generate
    from mcp_manager.indexer.embedder import embed_text
    from mcp_manager.db.models import McpEmbedding
    from mcp_manager.connectors.skill_scanner import scan_skill_source
    from sqlalchemy import delete

    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    # Get the source to re-fetch the raw content
    src_result = await db.execute(select(SkillSource).where(SkillSource.id == skill.skill_source_id))
    source = src_result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=400, detail="Skill source not found")

    # Re-scan to get raw content for this skill
    raw_skills = await scan_skill_source(source.url, source.skills_path, source.type)
    raw_content = None
    for raw in raw_skills:
        if raw["name"] == skill.name:
            raw_content = raw.get("raw_content", "")
            break

    if not raw_content:
        raise HTTPException(status_code=404, detail="Could not fetch skill content")

    from mcp_manager.summarizer.cleaner import clean_markdown
    cleaned = clean_markdown(raw_content)
    if len(cleaned) > 8000:
        cleaned = cleaned[:8000]

    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompts")

    # EN
    with open(os.path.join(prompts_dir, "skill_summary_en.md"), encoding="utf-8") as f:
        prompt_en = f.read().replace("{content}", cleaned)
    skill.summary_en = await ollama_generate(prompt_en)

    # FR
    with open(os.path.join(prompts_dir, "skill_summary_fr.md"), encoding="utf-8") as f:
        prompt_fr = f.read().replace("{content}", cleaned)
    skill.summary_fr = await ollama_generate(prompt_fr)

    # Embedding
    await db.execute(delete(McpEmbedding).where(
        McpEmbedding.mcp_service_id == skill.id,
        McpEmbedding.chunk_type == "skill_summary",
    ))
    if skill.summary_en:
        vec = await embed_text(skill.summary_en)
        if vec:
            db.add(McpEmbedding(
                mcp_service_id=skill.id,
                chunk_type="skill_summary",
                chunk_index=0,
                content=skill.summary_en,
                embedding=vec,
            ))

    skill.needs_summary = False
    await db.commit()

    return {"status": "done", "summary_en": bool(skill.summary_en), "summary_fr": bool(skill.summary_fr)}


@router.post("/skill-sources/{source_id}/sync")
async def sync_skill_source(
    source_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Sync skills from a source repo."""
    from datetime import datetime, timezone
    from mcp_manager.connectors.skill_scanner import scan_skill_source, get_repo_branch_hash

    result = await db.execute(select(SkillSource).where(SkillSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Skill source not found")

    # Check if repo changed
    new_hash = await get_repo_branch_hash(source.url)
    if new_hash and new_hash == source.branch_hash:
        return {"status": "unchanged", "message": "Branch hash unchanged, skipping"}

    # Scan the repo
    raw_skills = await scan_skill_source(source.url, source.skills_path, source.type)

    # Upsert skills
    added = 0
    updated = 0
    for raw in raw_skills:
        existing = await db.execute(
            select(Skill).where(
                Skill.skill_source_id == source_id,
                Skill.name == raw["name"],
            )
        )
        skill = existing.scalar_one_or_none()
        if skill:
            skill.description = raw["description"]
            skill.licence = raw["licence"]
            skill.licence_url = raw.get("licence_url")
            skill.source_url = raw["source_url"]
            skill.needs_summary = True
            updated += 1
        else:
            db.add(Skill(
                skill_source_id=source_id,
                name=raw["name"],
                description=raw["description"],
                target_type=source.type,
                licence=raw["licence"],
                licence_url=raw.get("licence_url"),
                source_url=raw["source_url"],
                category=raw.get("category"),
                needs_summary=True,
            ))
            added += 1

    source.branch_hash = new_hash
    source.last_sync = datetime.now(timezone.utc)
    source.last_sync_count = added + updated
    await db.commit()

    # Generate summaries for new/updated skills
    summaries_generated = await _generate_skill_summaries(db, source_id, raw_skills)

    return {"status": "done", "added": added, "updated": updated, "summaries": summaries_generated}


async def _generate_skill_summaries(db: AsyncSession, source_id, raw_skills: list[dict]) -> int:
    """Generate summaries for skills that need it."""
    import os
    from mcp_manager.summarizer.ollama_client import ollama_generate
    from mcp_manager.summarizer.cleaner import clean_markdown
    from mcp_manager.indexer.embedder import embed_text
    from mcp_manager.db.models import McpEmbedding

    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompts")
    count = 0

    # Build raw content map by name
    content_map = {r["name"]: r.get("raw_content", "") for r in raw_skills}

    result = await db.execute(
        select(Skill).where(Skill.skill_source_id == source_id, Skill.needs_summary == True)
    )
    skills = result.scalars().all()

    for skill in skills:
        raw_content = content_map.get(skill.name, "")
        if not raw_content:
            continue

        cleaned = clean_markdown(raw_content)
        if not cleaned:
            continue

        if len(cleaned) > 8000:
            cleaned = cleaned[:8000]

        # Generate EN summary
        try:
            with open(os.path.join(prompts_dir, "skill_summary_en.md"), encoding="utf-8") as f:
                prompt_en = f.read().replace("{content}", cleaned)
            skill.summary_en = await ollama_generate(prompt_en)
        except Exception:
            pass

        # Generate FR summary
        try:
            with open(os.path.join(prompts_dir, "skill_summary_fr.md"), encoding="utf-8") as f:
                prompt_fr = f.read().replace("{content}", cleaned)
            skill.summary_fr = await ollama_generate(prompt_fr)
        except Exception:
            pass

        # Embed summary for RAG search
        if skill.summary_en:
            vec = await embed_text(skill.summary_en)
            if vec:
                db.add(McpEmbedding(
                    mcp_service_id=skill.id,  # Reuse embeddings table
                    chunk_type="skill_summary",
                    chunk_index=0,
                    content=skill.summary_en,
                    embedding=vec,
                ))

        skill.needs_summary = False
        count += 1
        await db.commit()

    return count


@router.post("/skill-sources/sync-all")
async def sync_all_skill_sources(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Sync all active skill sources."""
    from datetime import datetime, timezone
    from mcp_manager.connectors.skill_scanner import scan_skill_source, get_repo_branch_hash

    result = await db.execute(select(SkillSource).where(SkillSource.is_active == True))
    sources = result.scalars().all()

    total_added = 0
    total_updated = 0

    for source in sources:
        new_hash = await get_repo_branch_hash(source.url)
        if new_hash and new_hash == source.branch_hash:
            continue

        raw_skills = await scan_skill_source(source.url, source.skills_path, source.type)

        for raw in raw_skills:
            existing = await db.execute(
                select(Skill).where(
                    Skill.skill_source_id == source.id,
                    Skill.name == raw["name"],
                )
            )
            skill = existing.scalar_one_or_none()
            if skill:
                skill.description = raw["description"]
                skill.content = raw["content"]
                skill.licence = raw["licence"]
                skill.source_url = raw["source_url"]
                total_updated += 1
            else:
                db.add(Skill(
                    skill_source_id=source.id,
                    name=raw["name"],
                    description=raw["description"],
                    content=raw["content"],
                    target_type=source.type,
                    licence=raw["licence"],
                    source_url=raw["source_url"],
                ))
                total_added += 1

        source.branch_hash = new_hash
        source.last_sync = datetime.now(timezone.utc)
        source.last_sync_count = len(raw_skills)

    await db.commit()
    return {"status": "done", "added": total_added, "updated": total_updated}


def _serialize_source(s: SkillSource) -> dict:
    return {
        "id": str(s.id),
        "name": s.name,
        "url": s.url,
        "skills_path": s.skills_path,
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
        "summary_en": s.summary_en,
        "summary_fr": s.summary_fr,
        "target_type": s.target_type,
        "licence": s.licence,
        "licence_url": s.licence_url,
        "source_url": s.source_url,
        "category": s.category,
        "has_summary": bool(s.summary_en),
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
