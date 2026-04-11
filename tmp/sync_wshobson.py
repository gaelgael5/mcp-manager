"""Manual sync script for a single skill source — bypasses HTTP auth.

Fetches the source, runs scan_repo_skills, and persists new skills + updates
source metadata. Commits once at the end.
"""
import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from mcp_manager.connectors.skillssh_scanner import scan_repo_skills
from mcp_manager.db.models import Skill, SkillSource, skill_source_skills
from mcp_manager.db.session import SessionLocal

SOURCE_ID = uuid.UUID("246b68bc-b39b-4306-8904-dcc83c255ae4")


async def main():
    async with SessionLocal() as db:
        result = await db.execute(select(SkillSource).where(SkillSource.id == SOURCE_ID))
        source = result.scalar_one_or_none()
        if not source:
            print(f"Source {SOURCE_ID} not found")
            return

        print(f"Source: {source.name}")
        print(f"Repo: {source.repo_url}")
        print(f"Current repo_format={source.repo_format}, status={source.repo_status}")

        scan_result = await scan_repo_skills(source.repo_url, source.repo_format)
        print(f"Scan: status={scan_result['status']}, detected_format={scan_result.get('repo_format')}, skills={len(scan_result['skills'])}")

        source.repo_status = scan_result["status"]
        if scan_result.get("repo_format"):
            source.repo_format = scan_result["repo_format"]

        raw_skills = scan_result["skills"]
        added = 0
        updated = 0

        for raw in raw_skills:
            existing_q = await db.execute(
                select(Skill)
                .join(skill_source_skills, skill_source_skills.c.skill_id == Skill.id)
                .where(
                    skill_source_skills.c.skill_source_id == source.id,
                    Skill.name == raw["name"],
                )
            )
            skill = existing_q.scalar_one_or_none()
            if skill:
                skill.description = raw["description"]
                skill.source_url = raw.get("source_url")
                skill.licence = raw.get("licence")
                skill.category = raw.get("category")
                skill.needs_summary = True
                updated += 1
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

        await db.commit()
        print(f"Done: added={added}, updated={updated}, total={len(raw_skills)}")


asyncio.run(main())
