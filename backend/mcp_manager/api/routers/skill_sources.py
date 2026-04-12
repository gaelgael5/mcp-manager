"""Skill sources management — admin only for write, public for read."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from mcp_manager.api.deps import get_db
from mcp_manager.api.routers.auth import require_admin
from mcp_manager.db.models import (
    Skill,
    SkillSource,
    SkillSourceTranslation,
    SkillTranslation,
    skill_source_skills,
)
from mcp_manager.prompts import (
    PromptNotFound,
    get_active_language_codes,
    load_prompt,
    render_prompt,
)

router = APIRouter(tags=["skills"])


async def _upsert_source_translation(
    db: AsyncSession,
    source_pid: int,
    culture: str,
    summary: str,
) -> None:
    stmt = (
        pg_insert(SkillSourceTranslation)
        .values(
            parent_id=source_pid,
            culture=culture,
            summary=summary,
        )
        .on_conflict_do_update(
            index_elements=["parent_id", "culture"],
            set_={"summary": summary, "updated_at": func.now()},
        )
    )
    await db.execute(stmt)


async def _upsert_skill_translation(
    db: AsyncSession,
    skill_pid: int,
    culture: str,
    summary: str,
) -> None:
    stmt = (
        pg_insert(SkillTranslation)
        .values(
            parent_id=skill_pid,
            culture=culture,
            summary=summary,
        )
        .on_conflict_do_update(
            index_elements=["parent_id", "culture"],
            set_={"summary": summary, "updated_at": func.now()},
        )
    )
    await db.execute(stmt)


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


@router.get("/skill-sources/{source_id}")
async def get_skill_source(source_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SkillSource).where(SkillSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Skill source not found")
    return _serialize_source(source)


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
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(Skill)
    if source_id:
        source_pid_sq = select(SkillSource._id).where(SkillSource.id == source_id).scalar_subquery()
        query = query.join(skill_source_skills, skill_source_skills.c.skill_pid == Skill._id).where(
            skill_source_skills.c.source_pid == source_pid_sq
        )
    if target_type:
        query = query.where(Skill.target_type == target_type)
    query = query.order_by(Skill.name).offset(offset).limit(limit)
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
    from mcp_manager.connectors.github_readme import fetch_github_readme

    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    # Get the source for repo_url (via junction table)
    src_result = await db.execute(
        select(SkillSource)
        .join(skill_source_skills, skill_source_skills.c.source_pid == SkillSource._id)
        .where(skill_source_skills.c.skill_pid == skill._id)
        .limit(1)
    )
    source = src_result.scalar_one_or_none()

    # Try to fetch content: from skill source_url (GitHub tree link) or repo README
    raw_content = None

    # If the skill has a GitHub source_url (from sync), try to fetch SKILL.md there
    if skill.source_url and "github.com" in skill.source_url:
        raw_content = await fetch_github_readme(skill.source_url)

    # Fallback: try repo README
    if not raw_content and source and source.repo_url:
        raw_content = await fetch_github_readme(source.repo_url)

    # Fallback: use skill description/name
    if not raw_content:
        raw_content = skill.description or skill.name

    from mcp_manager.summarizer.cleaner import clean_markdown
    cleaned = clean_markdown(raw_content)
    if len(cleaned) > 8000:
        cleaned = cleaned[:8000]

    import logging
    gen_logger = logging.getLogger(__name__)

    cultures = await get_active_language_codes(db)
    generated: dict[str, bool] = {}
    for culture in cultures:
        try:
            template = load_prompt("skill_summary", culture)
        except PromptNotFound:
            gen_logger.warning("skill_summary prompt missing for %s", culture)
            generated[culture] = False
            continue
        prompt = render_prompt(template, cleaned)
        summary = await ollama_generate(prompt)
        if not summary:
            gen_logger.warning("%s summary empty, retrying...", culture)
            summary = await ollama_generate(prompt)
        if summary:
            await _upsert_skill_translation(db, skill._id, culture, summary)
            gen_logger.info("Skill %s %s summary: %d chars", skill.name, culture, len(summary))
            generated[culture] = True
        else:
            generated[culture] = False

    skill.needs_summary = False
    await db.commit()

    return {"status": "done", "generated": generated}


def _derive_repo_url(skills_sh_url: str) -> str | None:
    """Derive GitHub repo URL from skills.sh URL.

    https://skills.sh/kirorab/12306-skill/12306 → https://github.com/kirorab/12306-skill
    """
    if not skills_sh_url or "skills.sh" not in skills_sh_url:
        return None
    parts = skills_sh_url.rstrip("/").split("/")
    # URL: https://skills.sh/{owner}/{repo}/{skill}
    # parts: ['https:', '', 'skills.sh', owner, repo, skill]
    if len(parts) >= 5:
        owner = parts[3]
        repo = parts[4]
        return f"https://github.com/{owner}/{repo}"
    return None


@router.post("/skill-sources/{source_id}/generate-summary")
async def generate_source_summary(
    source_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Generate summaries (one per active language) for a skill source and index in RAG.

    Derives the GitHub repo URL from the skills.sh URL, fetches the README,
    and uses it as context for summary generation.
    """
    import logging
    from mcp_manager.summarizer.ollama_client import ollama_generate
    from mcp_manager.summarizer.cleaner import clean_markdown
    from mcp_manager.connectors.github_readme import fetch_github_readme

    gen_logger = logging.getLogger(__name__)

    result = await db.execute(select(SkillSource).where(SkillSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Skill source not found")

    # Derive and store repo_url if missing
    if not source.repo_url:
        source.repo_url = _derive_repo_url(source.url)

    # Fetch README from GitHub repo for context
    context = ""
    if source.repo_url:
        readme = await fetch_github_readme(source.repo_url)
        if readme:
            context = clean_markdown(readme)
            if len(context) > 6000:
                context = context[:6000]

    # Fallback: use source metadata
    if not context:
        context = f"Skill source: {source.name}\nURL: {source.url}\nType: {source.type}"

    cultures = await get_active_language_codes(db)
    generated: dict[str, bool] = {}
    for culture in cultures:
        try:
            template = load_prompt("source_summary", culture)
        except PromptNotFound:
            gen_logger.warning("source_summary prompt missing for %s", culture)
            generated[culture] = False
            continue
        prompt = render_prompt(template, context)
        summary = await ollama_generate(prompt)
        if not summary:
            summary = await ollama_generate(prompt)
        if summary:
            await _upsert_source_translation(db, source._id, culture, summary)
            generated[culture] = True
        else:
            generated[culture] = False

    await db.commit()
    return {
        "status": "done",
        "repo_url": source.repo_url,
        "generated": generated,
    }


@router.post("/skill-sources/{source_id}/sync")
async def sync_skill_source(
    source_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Sync skills from a source repo.

    For skills.sh sources (with repo_url): scans the GitHub repo for a skills/ directory
    containing SKILL.md files. Marks source as no_skills_dir/repo_404 if not found.
    """
    from datetime import datetime, timezone

    result = await db.execute(select(SkillSource).where(SkillSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Skill source not found")

    # Derive repo_url if missing
    if not source.repo_url and "skills.sh" in (source.url or ""):
        parts = source.url.rstrip("/").split("/")
        if len(parts) >= 5:
            source.repo_url = f"https://github.com/{parts[3]}/{parts[4]}"

    if source.repo_url:
        # Skills.sh source → scan GitHub repo for skills/ or plugins/*/skills/*
        from mcp_manager.connectors.skillssh_scanner import scan_repo_skills

        scan_result = await scan_repo_skills(source.repo_url, source.repo_format)
        source.repo_status = scan_result["status"]
        if scan_result.get("repo_format"):
            source.repo_format = scan_result["repo_format"]
        raw_skills = scan_result["skills"]

        # Fetch GitHub stars
        import httpx
        from mcp_manager.config import settings as _settings
        try:
            parts = source.repo_url.rstrip("/").split("/")
            owner, repo = parts[-2], parts[-1]
            from mcp_manager.connectors.github_pool import get_github_headers
            headers = get_github_headers()
            async with httpx.AsyncClient(timeout=10.0) as gh:
                resp = await gh.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
                if resp.status_code == 200:
                    source.stars = resp.json().get("stargazers_count")
        except Exception:
            pass  # stars update is best-effort

        if not raw_skills:
            source.last_sync = datetime.now(timezone.utc)
            source.last_sync_count = 0
            await db.commit()
            return {"status": scan_result["status"], "added": 0, "updated": 0}
    else:
        # Legacy source → use original scanner
        from mcp_manager.connectors.skill_scanner import scan_skill_source, get_repo_branch_hash

        new_hash = await get_repo_branch_hash(source.url)
        if new_hash and new_hash == source.branch_hash:
            return {"status": "unchanged", "message": "Branch hash unchanged, skipping"}

        raw_skills = await scan_skill_source(source.url, source.skills_path, source.type)
        source.branch_hash = new_hash

    # Upsert skills via junction table
    added = 0
    updated = 0
    for raw in raw_skills:
        # Find existing skill linked to this source by name
        existing = await db.execute(
            select(Skill)
            .join(skill_source_skills, skill_source_skills.c.skill_pid == Skill._id)
            .where(
                skill_source_skills.c.source_pid == source._id,
                Skill.name == raw["name"],
            )
        )
        skill = existing.scalar_one_or_none()
        if skill:
            skill.description = raw["description"]
            skill.licence = raw.get("licence")
            skill.licence_url = raw.get("licence_url")
            skill.source_url = raw.get("source_url")
            skill.needs_summary = True
            updated += 1
        else:
            new_skill = Skill(
                name=raw["name"],
                description=raw["description"],
                target_type=source.type,
                licence=raw.get("licence"),
                licence_url=raw.get("licence_url"),
                source_url=raw.get("source_url"),
                category=raw.get("category"),
                needs_summary=True,
            )
            db.add(new_skill)
            await db.flush()  # get new_skill._id
            await db.execute(
                skill_source_skills.insert().values(
                    source_pid=source._id, skill_pid=new_skill._id
                )
            )
            added += 1

    source.repo_status = "ok"
    source.last_sync = datetime.now(timezone.utc)
    source.last_sync_count = added + updated
    await db.commit()

    return {"status": "done", "added": added, "updated": updated}


async def _generate_skill_summaries(db: AsyncSession, source_pid: int, raw_skills: list[dict]) -> int:
    """Generate summaries for skills that need it."""
    from mcp_manager.summarizer.ollama_client import ollama_generate
    from mcp_manager.summarizer.cleaner import clean_markdown
    count = 0

    cultures = await get_active_language_codes(db)

    # Build raw content map by name
    content_map = {r["name"]: r.get("raw_content", "") for r in raw_skills}

    result = await db.execute(
        select(Skill)
        .join(skill_source_skills, skill_source_skills.c.skill_pid == Skill._id)
        .where(skill_source_skills.c.source_pid == source_pid, Skill.needs_summary == True)
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

        for culture in cultures:
            try:
                template = load_prompt("skill_summary", culture)
            except PromptNotFound:
                continue
            try:
                prompt = render_prompt(template, cleaned)
                summary = await ollama_generate(prompt)
                if summary:
                    await _upsert_skill_translation(db, skill._id, culture, summary)
            except Exception:
                pass

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
                select(Skill)
                .join(skill_source_skills, skill_source_skills.c.skill_pid == Skill._id)
                .where(
                    skill_source_skills.c.source_pid == source._id,
                    Skill.name == raw["name"],
                )
            )
            skill = existing.scalar_one_or_none()
            if skill:
                skill.description = raw["description"]
                skill.licence = raw.get("licence")
                skill.source_url = raw.get("source_url")
                total_updated += 1
            else:
                new_skill = Skill(
                    name=raw["name"],
                    description=raw["description"],
                    target_type=source.type,
                    licence=raw.get("licence"),
                    source_url=raw.get("source_url"),
                )
                db.add(new_skill)
                await db.flush()
                await db.execute(
                    skill_source_skills.insert().values(
                        source_pid=source._id, skill_pid=new_skill._id
                    )
                )
                total_added += 1

        source.branch_hash = new_hash
        source.last_sync = datetime.now(timezone.utc)
        source.last_sync_count = len(raw_skills)

    await db.commit()
    return {"status": "done", "added": total_added, "updated": total_updated}


async def _enrich_repo_url(source: SkillSource) -> bool:
    """Fill repo_url by scraping skills.sh page. Returns True if updated."""
    import re
    import httpx

    if source.repo_url:
        return False
    if not source.url or "skills.sh" not in source.url:
        derived = _derive_repo_url(source.url)
        if derived:
            source.repo_url = derived
            return True
        return False

    try:
        async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "MCPManager/1.0"}, follow_redirects=True) as client:
            resp = await client.get(source.url)
            if resp.status_code == 200:
                text = re.sub(r"<[^>]+>", " ", resp.text)
                m = re.search(r"npx\s+skills\s+add\s+(https?://[^\s\"'<]+)", text)
                if m:
                    source.repo_url = m.group(1)
                    return True
    except Exception:
        pass
    return False


async def _enrich_summaries(source: SkillSource, db: AsyncSession) -> bool:
    """Generate summaries (one per active language) if missing. Returns True if generated."""
    from mcp_manager.summarizer.ollama_client import ollama_generate
    from mcp_manager.summarizer.cleaner import clean_markdown
    from mcp_manager.connectors.github_readme import fetch_github_readme

    cultures = await get_active_language_codes(db)
    present = {t.culture for t in source.translations}
    missing = [c for c in cultures if c not in present]
    if not missing:
        return False

    if not source.repo_url:
        source.repo_url = _derive_repo_url(source.url)

    context = ""
    if source.repo_url:
        readme = await fetch_github_readme(source.repo_url)
        if readme:
            context = clean_markdown(readme)
            if len(context) > 6000:
                context = context[:6000]

    if not context:
        context = f"Skill source: {source.name}\nURL: {source.url}\nType: {source.type}"

    generated = False
    for culture in missing:
        try:
            template = load_prompt("source_summary", culture)
        except PromptNotFound:
            continue
        prompt = render_prompt(template, context)
        summary = await ollama_generate(prompt)
        if not summary:
            summary = await ollama_generate(prompt)
        if summary:
            await _upsert_source_translation(db, source._id, culture, summary)
            generated = True

    return generated


async def _enrich_sync_skills(source: SkillSource, db: AsyncSession) -> int:
    """Sync skills from GitHub repo. Returns count of skills added."""
    from datetime import datetime, timezone

    if not source.repo_url:
        source.repo_url = _derive_repo_url(source.url)

    if not source.repo_url:
        return 0

    from mcp_manager.connectors.skillssh_scanner import scan_repo_skills
    scan_result = await scan_repo_skills(source.repo_url, source.repo_format)
    source.repo_status = scan_result["status"]
    if scan_result.get("repo_format"):
        source.repo_format = scan_result["repo_format"]
    raw_skills = scan_result["skills"]

    import httpx
    from mcp_manager.config import settings as _settings
    try:
        parts = source.repo_url.rstrip("/").split("/")
        owner, repo = parts[-2], parts[-1]
        from mcp_manager.connectors.github_pool import get_github_headers
        headers = get_github_headers()
        async with httpx.AsyncClient(timeout=10.0) as gh:
            resp = await gh.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
            if resp.status_code == 200:
                source.stars = resp.json().get("stargazers_count")
    except Exception:
        pass

    added = 0
    for raw in raw_skills:
        existing = await db.execute(
            select(Skill)
            .join(skill_source_skills, skill_source_skills.c.skill_pid == Skill._id)
            .where(
                skill_source_skills.c.source_pid == source._id,
                Skill.name == raw["name"],
            )
        )
        skill = existing.scalar_one_or_none()
        if skill:
            skill.description = raw["description"]
            skill.source_url = raw.get("source_url")
            skill.needs_summary = True
        else:
            new_skill = Skill(
                name=raw["name"],
                description=raw["description"],
                target_type=source.type,
                source_url=raw.get("source_url"),
                licence=raw.get("licence"),
                category=raw.get("category"),
                needs_summary=True,
            )
            db.add(new_skill)
            await db.flush()
            await db.execute(
                skill_source_skills.insert().values(
                    source_pid=source._id, skill_pid=new_skill._id
                )
            )
            added += 1

    source.last_sync = datetime.now(timezone.utc)
    source.last_sync_count = len(raw_skills)
    return added


async def _enrich_one_skill(skill: Skill, db: AsyncSession) -> bool:
    """Enrich a single skill: generate summaries if missing or if source branch changed.
    Returns True if the skill was updated."""
    from mcp_manager.summarizer.ollama_client import ollama_generate
    from mcp_manager.summarizer.cleaner import clean_markdown
    from mcp_manager.connectors.github_readme import fetch_github_readme
    from mcp_manager.connectors.skill_scanner import get_repo_branch_hash
    # Get the parent source for repo_url and branch_hash
    src_result = await db.execute(
        select(SkillSource)
        .join(skill_source_skills, skill_source_skills.c.source_pid == SkillSource._id)
        .where(skill_source_skills.c.skill_pid == skill._id)
        .limit(1)
    )
    source = src_result.scalar_one_or_none()

    cultures = await get_active_language_codes(db)
    present = {t.culture for t in skill.translations}
    needs_regen = not set(cultures).issubset(present)

    # Check if source branch has changed
    if not needs_regen and source and source.repo_url:
        new_hash = await get_repo_branch_hash(source.repo_url)
        if new_hash and new_hash != source.branch_hash:
            source.branch_hash = new_hash
            needs_regen = True

    if not needs_regen:
        return False

    # Fetch content for summary generation
    raw_content = None
    if skill.source_url and "github.com" in skill.source_url:
        raw_content = await fetch_github_readme(skill.source_url)
    if not raw_content and source and source.repo_url:
        raw_content = await fetch_github_readme(source.repo_url)
    if not raw_content:
        raw_content = skill.description or skill.name

    cleaned = clean_markdown(raw_content)
    if len(cleaned) > 8000:
        cleaned = cleaned[:8000]

    for culture in cultures:
        try:
            template = load_prompt("skill_summary", culture)
        except PromptNotFound:
            continue
        prompt = render_prompt(template, cleaned)
        summary = await ollama_generate(prompt)
        if not summary:
            summary = await ollama_generate(prompt)
        if summary:
            await _upsert_skill_translation(db, skill._id, culture, summary)

    return True


def _serialize_translation(t) -> dict:
    return {
        "culture": t.culture,
        "summary": t.summary,
        "source_hash": t.source_hash,
        "heuristic_quality": t.heuristic_quality,
        "llm_quality": t.llm_quality,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "rag_indexed_at": t.rag_indexed_at.isoformat() if t.rag_indexed_at else None,
    }


def _serialize_source(s: SkillSource) -> dict:
    translations = sorted(s.translations, key=lambda t: t.culture)
    has_en = any(t.culture == "en" and t.summary for t in translations)
    return {
        "id": s._id,
        "name": s.name,
        "url": s.url,
        "repo_url": s.repo_url,
        "skills_path": s.skills_path,
        "type": s.type,
        "description": s.description,
        "translations": [_serialize_translation(t) for t in translations],
        "has_summary": has_en,
        "repo_status": s.repo_status,
        "branch_hash": s.branch_hash,
        "is_active": s.is_active,
        "stars": s.stars,
        "enrichment_status": s.enrichment_status,
        "last_sync": s.last_sync.isoformat() if s.last_sync else None,
        "last_sync_count": s.last_sync_count,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _serialize_skill(s: Skill) -> dict:
    translations = sorted(s.translations, key=lambda t: t.culture)
    has_en = any(t.culture == "en" and t.summary for t in translations)
    return {
        "id": s._id,
        "name": s.name,
        "description": s.description,
        "translations": [_serialize_translation(t) for t in translations],
        "target_type": s.target_type,
        "licence": s.licence,
        "licence_url": s.licence_url,
        "source_url": s.source_url,
        "category": s.category,
        "install_command": s.install_command,
        "weekly_installs": s.weekly_installs,
        "has_summary": has_en,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
