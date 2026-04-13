"""Public search API — designed for external consumers (agents, scripts, dashboards)."""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, exists, text, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_manager.api.deps import get_db
from mcp_manager.db.models import (
    McpService, McpSummary, McpInstallation, McpParameter,
    InstallTarget, McpEmbedding, SkillSource, Skill,
    SkillSourceTranslation, SkillTranslation, skill_source_skills,
)

router = APIRouter(tags=["search"])


@router.get("/search_mcp")
async def search_mcp(
    q: str | None = Query(None, description="Full-text search in name and summaries"),
    canonical_id: str | None = Query(None, description="Exact match on canonical_id (e.g. github:owner/repo)"),
    semantic: bool = Query(False, description="Enable semantic search via embeddings (requires q)"),
    transport: str | None = Query(None, description="Filter by transport: stdio, sse, streamable-http"),
    category: str | None = Query(None, description="Filter by category"),
    source_type: str | None = Query(None, description="Filter by source"),
    repo_status: str | None = Query(None, description="Filter by repo status: ok, 404"),
    has_summaries: bool | None = Query(None, description="Filter by summary availability"),
    targets: str | None = Query(None, description="Comma-separated target names to include recipes for"),
    group_id: str | None = Query(None, description="Filter by preference group ID"),
    updated_since: str | None = Query(None, description="ISO timestamp — only services updated after this date (e.g. 2026-04-01T00:00:00Z)"),
    page: int = Query(1, ge=1, le=1000),
    per_page: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    # Parse updated_since
    since_dt = None
    if updated_since:
        from datetime import datetime as dt, timezone as tz
        try:
            since_dt = dt.fromisoformat(updated_since.replace("Z", "+00:00"))
        except ValueError:
            pass

    # Semantic search path — uses pgvector similarity
    if q and semantic:
        return await _semantic_search(
            q=q, transport=transport, category=category, source_type=source_type,
            repo_status=repo_status, has_summaries=has_summaries, targets=targets,
            updated_since=since_dt, page=page, per_page=per_page, db=db,
        )

    # Exact lookup by canonical_id
    if canonical_id:
        query = select(McpService).where(McpService.canonical_id == canonical_id)
        result = await db.execute(query)
        services = result.scalars().all()
        items = await _build_response_items(db, services, targets)
        return {"items": items, "total": len(items), "page": 1, "per_page": len(items) or per_page}

    # Standard text search — tsvector rank OR ILIKE fallback
    query = select(McpService)

    if q:
        from sqlalchemy import exists as sa_exists
        from mcp_manager.db.models import PreferenceGroup, preference_group_services as pgs_filter
        ts_query = func.plainto_tsquery("english", q)
        pattern = f"%{q}%"
        group_match = sa_exists(
            select(pgs_filter.c.mcp_service_id).where(
                pgs_filter.c.mcp_service_id == McpService.id,
                pgs_filter.c.group_id.in_(
                    select(PreferenceGroup.id).where(
                        PreferenceGroup.is_public == True,
                        PreferenceGroup.name.ilike(pattern),
                    )
                ),
            )
        )
        query = query.where(
            McpService.search_vector.op("@@")(ts_query)
            | McpService.name.ilike(pattern)
            | McpService.source_url.ilike(pattern)
            | group_match
        )

    query = _apply_filters(query, transport, category, source_type, repo_status, has_summaries)
    if group_id:
        from mcp_manager.db.models import preference_group_services
        query = query.join(
            preference_group_services,
            preference_group_services.c.mcp_service_id == McpService.id,
        ).where(preference_group_services.c.group_id == group_id)
    if since_dt:
        query = query.where(McpService.updated_at >= since_dt)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    if q:
        ts_query = func.plainto_tsquery("english", q)
        rank = func.ts_rank(McpService.search_vector, ts_query)
        query = query.order_by(rank.desc()).offset((page - 1) * per_page).limit(per_page)
    else:
        query = query.order_by(McpService.name).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    services = result.scalars().all()

    items = await _build_response_items(db, services, targets)

    return {"items": items, "total": total, "page": page, "per_page": per_page}


async def _semantic_search(
    q: str, transport, category, source_type, repo_status, has_summaries,
    targets, updated_since, page, per_page, db: AsyncSession,
):
    """Search using vector similarity in pgvector."""
    from mcp_manager.indexer.embedder import embed_text

    # Embed the query
    query_vec = await embed_text(q)
    if not query_vec:
        # Fallback to text search if embedding fails
        return {"items": [], "total": 0, "page": page, "per_page": per_page}

    vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"

    # Build WHERE clauses dynamically
    where_parts = []
    params: dict = {"limit": per_page, "offset": (page - 1) * per_page}

    if transport:
        where_parts.append("s.transport = :transport")
        params["transport"] = transport
    if category:
        where_parts.append("s.category = :category")
        params["category"] = category
    if source_type:
        where_parts.append("s.source_type = :source_type")
        params["source_type"] = source_type
    if repo_status:
        where_parts.append("s.repo_status = :repo_status")
        params["repo_status"] = repo_status
    if updated_since:
        where_parts.append("s.updated_at >= :updated_since")
        params["updated_since"] = updated_since

    where_clause = (" AND " + " AND ".join(where_parts)) if where_parts else ""

    wrapped = text(f"""
        SELECT sub.mcp_service_id, sub.similarity
        FROM (
            SELECT DISTINCT ON (e.mcp_service_id)
                e.mcp_service_id,
                1 - (e.embedding <=> '{vec_str}'::vector) as similarity
            FROM mcp_embeddings e
            JOIN mcp_services s ON s.id = e.mcp_service_id
            WHERE 1=1 {where_clause}
            ORDER BY e.mcp_service_id, similarity DESC
        ) sub
        ORDER BY sub.similarity DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await db.execute(wrapped, params)
    rows = result.all()

    if not rows:
        return {"items": [], "total": 0, "page": page, "per_page": per_page}

    count_query = text(f"""
        SELECT COUNT(DISTINCT e.mcp_service_id)
        FROM mcp_embeddings e
        JOIN mcp_services s ON s.id = e.mcp_service_id
        WHERE 1=1 {where_clause}
    """)
    total = (await db.execute(count_query, params)).scalar() or 0

    # Load services in order
    service_ids = [row[0] for row in rows]
    similarity_scores = {row[0]: float(row[1]) for row in rows}

    services_result = await db.execute(
        select(McpService).where(McpService.id.in_(service_ids))
    )
    services_map = {s.id: s for s in services_result.scalars().all()}
    services = [services_map[sid] for sid in service_ids if sid in services_map]

    items = await _build_response_items(db, services, targets)

    # Add similarity score to each item
    _id_to_similarity = {s._id: similarity_scores.get(s.id, 0) for s in services}
    for item in items:
        item["similarity"] = round(_id_to_similarity.get(item["id"], 0), 4)

    return {"items": items, "total": total, "page": page, "per_page": per_page}


def _apply_filters(query, transport, category, source_type, repo_status, has_summaries):
    if transport:
        query = query.where(McpService.transport == transport)
    if category:
        query = query.where(McpService.category == category)
    if source_type:
        query = query.where(McpService.source_type == source_type)
    if repo_status:
        query = query.where(McpService.repo_status == repo_status)
    if has_summaries is not None:
        sub = select(McpSummary.id).where(McpSummary.parent_id == McpService._id)
        if has_summaries:
            query = query.where(exists(sub))
        else:
            query = query.where(~exists(sub))
    return query


async def _build_response_items(
    db: AsyncSession, services: list[McpService], targets: str | None,
) -> list[dict]:
    """Build enriched response items for a list of services."""
    if not services:
        return []

    target_names: list[str] | None = None
    if targets:
        target_names = [t.strip() for t in targets.split(",") if t.strip()]

    targets_result = await db.execute(select(InstallTarget))
    all_targets = {t.id: t for t in targets_result.scalars().all()}
    target_name_to_id = {t.name: t.id for t in all_targets.values()}

    service_ids = [s._id for s in services]

    # Summaries (EN)
    summaries_result = await db.execute(
        select(McpSummary).where(
            McpSummary.parent_id.in_(service_ids),
            McpSummary.culture == "en",
        )
    )
    summaries_map = {s.parent_id: s.summary for s in summaries_result.scalars().all()}

    # Parameters
    params_result = await db.execute(
        select(McpParameter).where(McpParameter.parent_id.in_(service_ids))
    )
    params_map: dict[int, list] = {}
    for p in params_result.scalars().all():
        params_map.setdefault(p.parent_id, []).append({
            "name": p.name,
            "description": p.description,
            "is_required": p.is_required,
            "is_secret": p.is_secret,
        })

    # Installations
    install_query = select(McpInstallation).where(
        McpInstallation.parent_id.in_(service_ids)
    )
    if target_names:
        target_ids = [target_name_to_id[n] for n in target_names if n in target_name_to_id]
        if target_ids:
            install_query = install_query.where(McpInstallation.install_target_id.in_(target_ids))

    installs_result = await db.execute(install_query)
    installs_map: dict[int, dict] = {}
    for inst in installs_result.scalars().all():
        target = all_targets.get(inst.install_target_id)
        if not target:
            continue
        installs_map.setdefault(inst.parent_id, {})[target.name] = {
            "action_type": inst.action_type,
            "data": inst.data,
        }

    # Public groups
    from mcp_manager.db.models import PreferenceGroup, preference_group_services as pgs
    svc_uuids = [s.id for s in services]
    groups_map: dict[str, list] = {}
    if svc_uuids:
        grp_result = await db.execute(
            select(pgs.c.mcp_service_id, PreferenceGroup.id, PreferenceGroup.name)
            .join(PreferenceGroup, pgs.c.group_id == PreferenceGroup.id)
            .where(pgs.c.mcp_service_id.in_(svc_uuids), PreferenceGroup.is_public == True)
        )
        for svc_uuid, grp_id, grp_name in grp_result.all():
            groups_map.setdefault(str(svc_uuid), []).append({"id": str(grp_id), "name": grp_name})

    items = []
    for svc in services:
        items.append({
            "id": svc._id,
            "name": svc.name,
            "description": summaries_map.get(svc._id),
            "source_url": svc.source_url or None,
            "doc_url": svc.doc_url,
            "transport": svc.transport,
            "category": svc.category,
            "repo_status": svc.repo_status,
            "stars": svc.stars,
            "canonical_id": svc.canonical_id,
            "parameters": params_map.get(svc._id, []),
            "recipes": installs_map.get(svc._id, {}),
            "groups": groups_map.get(str(svc.id), []),
        })

    return items


@router.get("/search_skill_sources")
async def search_skill_sources(
    q: str | None = Query(None, description="Search in name, description, and summaries"),
    type: str | None = Query(None, description="Filter by type: claude, copilot, gemini, cursor"),
    repo_status: str | None = Query(None, description="Filter by repo status: ok, repo_404, no_skills_dir"),
    has_summary: bool | None = Query(None, description="Filter by summary availability"),
    page: int = Query(1, ge=1, le=1000),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Search skill sources with text filters and pagination."""
    query = select(SkillSource).where(SkillSource.is_active == True)

    if q:
        pattern = f"%{q}%"
        translation_match = (
            select(SkillSourceTranslation.parent_id)
            .where(
                SkillSourceTranslation.parent_id == SkillSource._id,
                SkillSourceTranslation.summary.ilike(pattern),
            )
        )
        query = query.where(
            SkillSource.name.ilike(pattern)
            | SkillSource.description.ilike(pattern)
            | exists(translation_match)
            | SkillSource.repo_url.ilike(pattern)
        )
    if type:
        query = query.where(SkillSource.type == type)
    if repo_status:
        query = query.where(SkillSource.repo_status == repo_status)
    if has_summary is not None:
        has_en = (
            select(SkillSourceTranslation.parent_id)
            .where(
                SkillSourceTranslation.parent_id == SkillSource._id,
                SkillSourceTranslation.culture == "en",
            )
        )
        if has_summary:
            query = query.where(exists(has_en))
        else:
            query = query.where(~exists(has_en))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(SkillSource.stars.desc().nullslast(), SkillSource.name)
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    sources = result.scalars().all()

    # Count skills per source
    source_pids = [s._id for s in sources]
    skills_count_map: dict[int, int] = {}
    if source_pids:
        count_result = await db.execute(
            select(
                skill_source_skills.c.source_pid,
                func.count(skill_source_skills.c.skill_pid),
            )
            .where(skill_source_skills.c.source_pid.in_(source_pids))
            .group_by(skill_source_skills.c.source_pid)
        )
        skills_count_map = {row[0]: row[1] for row in count_result}

    items = []
    for s in sources:
        translations = [
            {"culture": t.culture, "summary": t.summary}
            for t in sorted(s.translations, key=lambda t: t.culture)
        ]
        has_en = any(t["culture"] == "en" for t in translations)
        items.append({
            "id": s._id,
            "name": s.name,
            "url": s.url,
            "repo_url": s.repo_url,
            "type": s.type,
            "description": s.description,
            "translations": translations,
            "has_summary": has_en,
            "repo_status": s.repo_status,
            "stars": s.stars,
            "skills_count": skills_count_map.get(s._id, 0),
            "last_sync": s.last_sync.isoformat() if s.last_sync else None,
        })

    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/search_skills")
async def search_skills(
    q: str | None = Query(None, description="Search in name, description, and summaries"),
    canonical_id: str | None = Query(None, description="Exact match on canonical_id (e.g. github:owner/repo:skill-name)"),
    target_type: str | None = Query(None, description="Filter by target type: claude, copilot, gemini, cursor"),
    category: str | None = Query(None, description="Filter by category"),
    has_summary: bool | None = Query(None, description="Filter by summary availability"),
    source_id: uuid.UUID | None = Query(None, description="Filter by skill source ID"),
    page: int = Query(1, ge=1, le=1000),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Search skills with text filters and pagination."""
    def _serialize_skill_item(s: Skill) -> dict:
        translations = [
            {"culture": t.culture, "summary": t.summary}
            for t in sorted(s.translations, key=lambda t: t.culture)
        ]
        return {
            "id": s._id,
            "name": s.name,
            "description": s.description,
            "translations": translations,
            "target_type": s.target_type,
            "has_summary": any(t["culture"] == "en" for t in translations),
            "category": s.category,
            "licence": s.licence,
            "source_url": s.source_url,
            "canonical_id": s.canonical_id,
            "install_command": s.install_command,
            "weekly_installs": s.weekly_installs,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }

    # Exact lookup by canonical_id
    if canonical_id:
        result = await db.execute(select(Skill).where(Skill.canonical_id == canonical_id))
        skills = result.scalars().all()
        items = [_serialize_skill_item(s) for s in skills]
        return {"items": items, "total": len(items), "page": 1, "per_page": len(items) or per_page}

    query = select(Skill)

    if q:
        pattern = f"%{q}%"
        translation_match = (
            select(SkillTranslation.parent_id)
            .where(
                SkillTranslation.parent_id == Skill._id,
                SkillTranslation.summary.ilike(pattern),
            )
        )
        query = query.where(
            Skill.name.ilike(pattern)
            | Skill.description.ilike(pattern)
            | exists(translation_match)
        )
    if target_type:
        query = query.where(Skill.target_type == target_type)
    if category:
        query = query.where(Skill.category == category)
    if has_summary is not None:
        has_en = (
            select(SkillTranslation.parent_id)
            .where(
                SkillTranslation.parent_id == Skill._id,
                SkillTranslation.culture == "en",
            )
        )
        if has_summary:
            query = query.where(exists(has_en))
        else:
            query = query.where(~exists(has_en))
    if source_id:
        source_pid_sq = select(SkillSource._id).where(SkillSource.id == source_id).scalar_subquery()
        query = query.join(skill_source_skills, skill_source_skills.c.skill_pid == Skill._id).where(
            skill_source_skills.c.source_pid == source_pid_sq
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Skill.weekly_installs.desc(), Skill.name)
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    skills = result.scalars().all()

    items = [_serialize_skill_item(s) for s in skills]

    return {"items": items, "total": total, "page": page, "per_page": per_page}
