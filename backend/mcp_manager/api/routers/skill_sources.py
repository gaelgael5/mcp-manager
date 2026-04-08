"""Skill sources management — admin only for write, public for read."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_manager.api.deps import get_db
from mcp_manager.api.routers.auth import require_admin
from mcp_manager.db.models import SkillSource, Skill, skill_source_skills

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
    db: AsyncSession = Depends(get_db),
):
    query = select(Skill)
    if source_id:
        query = query.join(skill_source_skills, skill_source_skills.c.skill_id == Skill.id).where(
            skill_source_skills.c.skill_source_id == source_id
        )
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
    from mcp_manager.connectors.github_readme import fetch_github_readme
    from sqlalchemy import delete

    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    # Get the source for repo_url (via junction table)
    src_result = await db.execute(
        select(SkillSource)
        .join(skill_source_skills, skill_source_skills.c.skill_source_id == SkillSource.id)
        .where(skill_source_skills.c.skill_id == skill.id)
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

    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompts")

    import logging
    gen_logger = logging.getLogger(__name__)

    # EN
    with open(os.path.join(prompts_dir, "skill_summary_en.md"), encoding="utf-8") as f:
        prompt_en = f.read().replace("{content}", cleaned)
    skill.summary_en = await ollama_generate(prompt_en)
    if not skill.summary_en:
        gen_logger.warning("EN summary empty, retrying...")
        skill.summary_en = await ollama_generate(prompt_en)
    skill.summary_en = skill.summary_en or None
    gen_logger.info("Skill %s EN summary: %d chars", skill.name, len(skill.summary_en or ""))

    # FR
    with open(os.path.join(prompts_dir, "skill_summary_fr.md"), encoding="utf-8") as f:
        prompt_fr = f.read().replace("{content}", cleaned)
    skill.summary_fr = await ollama_generate(prompt_fr)
    if not skill.summary_fr:
        gen_logger.warning("FR summary empty, retrying...")
        skill.summary_fr = await ollama_generate(prompt_fr)
    skill.summary_fr = skill.summary_fr or None

    # Embedding
    await db.execute(delete(McpEmbedding).where(
        McpEmbedding.skill_id == skill.id,
        McpEmbedding.chunk_type == "skill_summary",
    ))
    if skill.summary_en:
        vec = await embed_text(skill.summary_en)
        if vec:
            db.add(McpEmbedding(
                skill_id=skill.id,
                chunk_type="skill_summary",
                chunk_index=0,
                content=skill.summary_en,
                embedding=vec,
            ))

    skill.needs_summary = False
    await db.commit()

    return {"status": "done", "summary_en": bool(skill.summary_en), "summary_fr": bool(skill.summary_fr)}


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
    """Generate EN/FR summaries for a skill source and index in RAG.

    Derives the GitHub repo URL from the skills.sh URL, fetches the README,
    and uses it as context for summary generation.
    """
    import os
    from mcp_manager.summarizer.ollama_client import ollama_generate
    from mcp_manager.summarizer.cleaner import clean_markdown
    from mcp_manager.indexer.embedder import embed_text
    from mcp_manager.connectors.github_readme import fetch_github_readme
    from mcp_manager.db.models import McpEmbedding
    from sqlalchemy import delete

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

    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompts")

    # EN
    with open(os.path.join(prompts_dir, "source_summary_en.md"), encoding="utf-8") as f:
        prompt_en = f.read().replace("{content}", context)
    source.summary_en = await ollama_generate(prompt_en)
    if not source.summary_en:
        source.summary_en = await ollama_generate(prompt_en)
    source.summary_en = source.summary_en or None  # never store empty string

    # FR
    with open(os.path.join(prompts_dir, "source_summary_fr.md"), encoding="utf-8") as f:
        prompt_fr = f.read().replace("{content}", context)
    source.summary_fr = await ollama_generate(prompt_fr)
    if not source.summary_fr:
        source.summary_fr = await ollama_generate(prompt_fr)
    source.summary_fr = source.summary_fr or None  # never store empty string

    # Index in RAG
    await db.execute(delete(McpEmbedding).where(
        McpEmbedding.chunk_type == "source_summary",
        McpEmbedding.content.like(f"source:{source_id}%"),
    ))
    if source.summary_en:
        vec = await embed_text(source.summary_en)
        if vec:
            db.add(McpEmbedding(
                chunk_type="source_summary",
                chunk_index=0,
                content=f"source:{source_id} {source.summary_en}",
                embedding=vec,
            ))

    await db.commit()
    return {
        "status": "done",
        "repo_url": source.repo_url,
        "summary_en": bool(source.summary_en),
        "summary_fr": bool(source.summary_fr),
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
        # Skills.sh source → scan GitHub repo for skills/ directory
        from mcp_manager.connectors.skillssh_scanner import scan_repo_skills

        scan_result = await scan_repo_skills(source.repo_url)
        source.repo_status = scan_result["status"]
        raw_skills = scan_result["skills"]

        # Fetch GitHub stars
        import httpx
        from mcp_manager.config import settings as _settings
        try:
            parts = source.repo_url.rstrip("/").split("/")
            owner, repo = parts[-2], parts[-1]
            headers = {"Accept": "application/vnd.github.v3+json"}
            if _settings.github_token:
                headers["Authorization"] = f"token {_settings.github_token}"
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
            .join(skill_source_skills, skill_source_skills.c.skill_id == Skill.id)
            .where(
                skill_source_skills.c.skill_source_id == source_id,
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
            await db.flush()  # get new_skill.id
            await db.execute(
                skill_source_skills.insert().values(
                    skill_source_id=source_id, skill_id=new_skill.id
                )
            )
            added += 1

    source.repo_status = "ok"
    source.last_sync = datetime.now(timezone.utc)
    source.last_sync_count = added + updated
    await db.commit()

    return {"status": "done", "added": added, "updated": updated}


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
        select(Skill)
        .join(skill_source_skills, skill_source_skills.c.skill_id == Skill.id)
        .where(skill_source_skills.c.skill_source_id == source_id, Skill.needs_summary == True)
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
                    skill_id=skill.id,  # Reuse embeddings table
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
                select(Skill)
                .join(skill_source_skills, skill_source_skills.c.skill_id == Skill.id)
                .where(
                    skill_source_skills.c.skill_source_id == source.id,
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
                        skill_source_id=source.id, skill_id=new_skill.id
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
    """Generate EN/FR summaries if missing. Returns True if generated."""
    import os
    from mcp_manager.summarizer.ollama_client import ollama_generate
    from mcp_manager.summarizer.cleaner import clean_markdown
    from mcp_manager.connectors.github_readme import fetch_github_readme

    if source.summary_en and source.summary_fr:
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

    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompts")

    if not source.summary_en:
        with open(os.path.join(prompts_dir, "source_summary_en.md"), encoding="utf-8") as f:
            prompt_en = f.read().replace("{content}", context)
        source.summary_en = await ollama_generate(prompt_en)
        if not source.summary_en:
            source.summary_en = await ollama_generate(prompt_en)
        source.summary_en = source.summary_en or None

    if not source.summary_fr:
        with open(os.path.join(prompts_dir, "source_summary_fr.md"), encoding="utf-8") as f:
            prompt_fr = f.read().replace("{content}", context)
        source.summary_fr = await ollama_generate(prompt_fr)
        if not source.summary_fr:
            source.summary_fr = await ollama_generate(prompt_fr)
        source.summary_fr = source.summary_fr or None

    return bool(source.summary_en or source.summary_fr)


async def _enrich_sync_skills(source: SkillSource, db: AsyncSession) -> int:
    """Sync skills from GitHub repo if not yet synced. Returns count of skills added."""
    from datetime import datetime, timezone

    if source.last_sync:
        return 0

    if not source.repo_url:
        source.repo_url = _derive_repo_url(source.url)

    if not source.repo_url:
        return 0

    from mcp_manager.connectors.skillssh_scanner import scan_repo_skills
    scan_result = await scan_repo_skills(source.repo_url)
    source.repo_status = scan_result["status"]
    raw_skills = scan_result["skills"]

    import httpx
    from mcp_manager.config import settings as _settings
    try:
        parts = source.repo_url.rstrip("/").split("/")
        owner, repo = parts[-2], parts[-1]
        headers = {"Accept": "application/vnd.github.v3+json"}
        if _settings.github_token:
            headers["Authorization"] = f"token {_settings.github_token}"
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
            .join(skill_source_skills, skill_source_skills.c.skill_id == Skill.id)
            .where(
                skill_source_skills.c.skill_source_id == source.id,
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
                    skill_source_id=source.id, skill_id=new_skill.id
                )
            )
            added += 1

    source.last_sync = datetime.now(timezone.utc)
    source.last_sync_count = len(raw_skills)
    return added


def _serialize_source(s: SkillSource) -> dict:
    return {
        "id": str(s.id),
        "name": s.name,
        "url": s.url,
        "repo_url": s.repo_url,
        "skills_path": s.skills_path,
        "type": s.type,
        "description": s.description,
        "summary_en": s.summary_en,
        "summary_fr": s.summary_fr,
        "has_summary": bool(s.summary_en),
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
    return {
        "id": str(s.id),
        "name": s.name,
        "description": s.description,
        "summary_en": s.summary_en,
        "summary_fr": s.summary_fr,
        "target_type": s.target_type,
        "licence": s.licence,
        "licence_url": s.licence_url,
        "source_url": s.source_url,
        "category": s.category,
        "install_command": s.install_command,
        "weekly_installs": s.weekly_installs,
        "has_summary": bool(s.summary_en),
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
