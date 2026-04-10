import shutil
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, exists
from sqlalchemy.ext.asyncio import AsyncSession
from mcp_manager.api.deps import get_db
from mcp_manager.db.models import (
    McpService, McpSummary, McpEmbedding, McpInstallation, McpParameter,
    Skill, SkillSource, SkillSourceTranslation, SkillTranslation, Language,
)

router = APIRouter(tags=["stats"])


def _get_disk_usage() -> dict:
    usage = shutil.disk_usage("/")
    return {
        "total_gb": round(usage.total / (1024**3), 1),
        "used_gb": round(usage.used / (1024**3), 1),
        "free_gb": round(usage.free / (1024**3), 1),
        "percent": round(usage.used / usage.total * 100),
    }


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_services = (await db.execute(select(func.count()).select_from(McpService))).scalar() or 0

    by_source_result = await db.execute(
        select(McpService.source_type, func.count()).group_by(McpService.source_type)
    )
    by_source = {row[0]: row[1] for row in by_source_result}

    by_category_result = await db.execute(
        select(McpService.category, func.count())
        .where(McpService.category.isnot(None))
        .group_by(McpService.category)
        .order_by(func.count().desc())
        .limit(20)
    )
    by_category = {row[0]: row[1] for row in by_category_result}

    # Repo status
    repo_result = await db.execute(
        select(McpService.repo_status, func.count()).group_by(McpService.repo_status)
    )
    by_repo_status = {}
    for row in repo_result:
        key = row[0] or "unchecked"
        by_repo_status[key] = row[1]

    # Indexation stats
    with_summaries = (await db.execute(
        select(func.count(func.distinct(McpSummary.mcp_service_id)))
    )).scalar() or 0

    with_embeddings = (await db.execute(
        select(func.count(func.distinct(McpEmbedding.mcp_service_id)))
    )).scalar() or 0

    total_embeddings = (await db.execute(
        select(func.count()).select_from(McpEmbedding)
    )).scalar() or 0

    with_params = (await db.execute(
        select(func.count(func.distinct(McpParameter.mcp_service_id)))
    )).scalar() or 0

    with_installations = (await db.execute(
        select(func.count(func.distinct(McpInstallation.mcp_service_id)))
    )).scalar() or 0

    needs_reindex = (await db.execute(
        select(func.count()).select_from(McpService).where(McpService.needs_reindex == True)
    )).scalar() or 0

    outdated_query = (
        select(func.count()).select_from(McpSummary)
        .join(McpService, McpSummary.mcp_service_id == McpService.id)
        .where(McpSummary.source_hash != McpService.doc_hash)
    )
    outdated = (await db.execute(outdated_query)).scalar() or 0

    total_skills = (await db.execute(select(func.count()).select_from(Skill))).scalar() or 0
    total_skill_sources = (await db.execute(select(func.count()).select_from(SkillSource))).scalar() or 0

    # Skill Sources enrichment stats
    ss_with_repo = (await db.execute(
        select(func.count()).select_from(SkillSource).where(SkillSource.repo_url.isnot(None))
    )).scalar() or 0
    ss_with_summary_en = (await db.execute(
        select(func.count(func.distinct(SkillSourceTranslation.skill_source_id)))
        .where(SkillSourceTranslation.culture == "en")
    )).scalar() or 0
    ss_with_summary_fr = (await db.execute(
        select(func.count(func.distinct(SkillSourceTranslation.skill_source_id)))
        .where(SkillSourceTranslation.culture == "fr")
    )).scalar() or 0
    ss_synced = (await db.execute(
        select(func.count()).select_from(SkillSource).where(SkillSource.last_sync.isnot(None))
    )).scalar() or 0
    ss_enrichment_result = await db.execute(
        select(SkillSource.enrichment_status, func.count()).group_by(SkillSource.enrichment_status)
    )
    ss_by_enrichment = {(row[0] or "pending"): row[1] for row in ss_enrichment_result}
    ss_with_rag = (await db.execute(
        select(func.count(func.distinct(McpEmbedding.content)))
        .where(McpEmbedding.chunk_type == "source_summary")
    )).scalar() or 0

    # Skills indexation stats
    skills_with_summary = (await db.execute(
        select(func.count(func.distinct(SkillTranslation.skill_id)))
        .where(SkillTranslation.culture == "en")
    )).scalar() or 0
    skills_with_summary_fr = (await db.execute(
        select(func.count(func.distinct(SkillTranslation.skill_id)))
        .where(SkillTranslation.culture == "fr")
    )).scalar() or 0
    skills_needs_summary = (await db.execute(
        select(func.count()).select_from(Skill).where(Skill.needs_summary == True)
    )).scalar() or 0
    skills_with_rag = (await db.execute(
        select(func.count(func.distinct(McpEmbedding.skill_id)))
        .where(McpEmbedding.chunk_type == "skill_summary")
    )).scalar() or 0

    # RAG: count totals and pending
    from sqlalchemy import or_
    mcp_summaries_en = (await db.execute(
        select(func.count()).select_from(McpSummary).where(McpSummary.culture == "en")
    )).scalar() or 0
    rag_pending_mcp = (await db.execute(
        select(func.count()).select_from(McpSummary)
        .where(McpSummary.culture == "en", or_(
            McpSummary.rag_indexed_at.is_(None),
            McpSummary.rag_indexed_at < McpSummary.updated_at,
        ))
    )).scalar() or 0
    rag_pending_sources = (await db.execute(
        select(func.count()).select_from(SkillSourceTranslation)
        .where(SkillSourceTranslation.culture == "en", or_(
            SkillSourceTranslation.rag_indexed_at.is_(None),
            SkillSourceTranslation.rag_indexed_at < SkillSourceTranslation.updated_at,
        ))
    )).scalar() or 0
    rag_pending_skills = (await db.execute(
        select(func.count()).select_from(SkillTranslation)
        .where(SkillTranslation.culture == "en", or_(
            SkillTranslation.rag_indexed_at.is_(None),
            SkillTranslation.rag_indexed_at < SkillTranslation.updated_at,
        ))
    )).scalar() or 0

    # Translations progress (per active language, 'en' is the baseline)
    active_langs_result = await db.execute(
        select(Language).where(Language.is_active.is_(True)).order_by(Language.display_order)
    )
    active_languages = active_langs_result.scalars().all()

    async def _count_nonempty(model, culture: str) -> int:
        return (await db.execute(
            select(func.count()).select_from(model).where(
                model.culture == culture,
                model.summary.isnot(None),
                func.length(model.summary) > 0,
            )
        )).scalar() or 0

    translations_progress = {
        "languages": [
            {"code": l.code, "name": l.name, "is_baseline": l.code == "en"}
            for l in active_languages
        ],
        "mcp": {},
        "skill_sources": {},
        "skills": {},
    }
    for lang in active_languages:
        translations_progress["mcp"][lang.code] = await _count_nonempty(McpSummary, lang.code)
        translations_progress["skill_sources"][lang.code] = await _count_nonempty(
            SkillSourceTranslation, lang.code
        )
        translations_progress["skills"][lang.code] = await _count_nonempty(
            SkillTranslation, lang.code
        )

    return {
        "total_services": total_services,
        "total_skills": total_skills,
        "total_skill_sources": total_skill_sources,
        "by_source": by_source,
        "by_category": by_category,
        "by_repo_status": by_repo_status,
        "indexation": {
            "with_summaries": with_summaries,
            "with_embeddings": with_embeddings,
            "total_embeddings": total_embeddings,
            "with_params": with_params,
            "with_installations": with_installations,
            "needs_reindex": needs_reindex,
            "outdated_summaries": outdated,
        },
        "skill_sources": {
            "total": total_skill_sources,
            "with_repo": ss_with_repo,
            "with_summary_en": ss_with_summary_en,
            "with_summary_fr": ss_with_summary_fr,
            "synced": ss_synced,
            "with_rag": ss_with_rag,
            "by_enrichment": ss_by_enrichment,
        },
        "skills": {
            "total": total_skills,
            "with_summary": skills_with_summary,
            "with_summary_en": skills_with_summary,
            "with_summary_fr": skills_with_summary_fr,
            "needs_summary": skills_needs_summary,
            "with_rag": skills_with_rag,
        },
        "rag_pending": {
            "mcp": rag_pending_mcp,
            "mcp_total": mcp_summaries_en,
            "sources": rag_pending_sources,
            "sources_total": ss_with_summary_en,
            "skills": rag_pending_skills,
            "skills_total": skills_with_summary,
            "total": rag_pending_mcp + rag_pending_sources + rag_pending_skills,
        },
        "translations_progress": translations_progress,
        "disk": _get_disk_usage(),
    }
