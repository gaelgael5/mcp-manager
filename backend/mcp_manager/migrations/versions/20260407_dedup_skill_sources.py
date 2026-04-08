"""dedup skill_sources: add junction table, merge duplicates, unique repo_url

Revision ID: 20260407b
Revises: 20260407a
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260407b"
down_revision = "20260407a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create junction table
    op.create_table(
        "skill_source_skills",
        sa.Column("skill_source_id", UUID(as_uuid=True), sa.ForeignKey("skill_sources.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("skill_id", UUID(as_uuid=True), sa.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
    )

    # 2. Populate from existing FK
    op.execute("""
        INSERT INTO skill_source_skills (skill_source_id, skill_id)
        SELECT skill_source_id, id FROM skills
    """)

    # 2b. Backfill repo_url for seed sources (url = GitHub, repo_url = NULL)
    op.execute("""
        UPDATE skill_sources SET repo_url = url
        WHERE repo_url IS NULL AND url LIKE 'https://github.com/%'
    """)

    # 2c. Clean up skills_path corrupted by scraper (stored install_cmd instead of path)
    op.execute("""
        UPDATE skill_sources SET skills_path = ''
        WHERE skills_path LIKE 'npx skills add%'
    """)

    # 3. For duplicate repo_urls, pick the best source and re-point links
    op.execute("""
        WITH best AS (
            SELECT DISTINCT ON (repo_url) id, repo_url
            FROM skill_sources
            WHERE repo_url IS NOT NULL
            ORDER BY repo_url,
                     (summary_en IS NOT NULL)::int DESC,
                     stars DESC NULLS LAST,
                     created_at ASC
        ),
        dupes AS (
            SELECT ss.id AS dupe_id, b.id AS best_id
            FROM skill_sources ss
            JOIN best b ON b.repo_url = ss.repo_url
            WHERE ss.id != b.id
        )
        UPDATE skill_source_skills SET skill_source_id = d.best_id
        FROM dupes d WHERE skill_source_skills.skill_source_id = d.dupe_id
    """)

    # 4. Remove duplicate links that now collide on (source_id, skill_id)
    op.execute("""
        DELETE FROM skill_source_skills a
        USING skill_source_skills b
        WHERE a.ctid < b.ctid
          AND a.skill_source_id = b.skill_source_id
          AND a.skill_id = b.skill_id
    """)

    # 5. Delete duplicate skill_sources
    op.execute("""
        DELETE FROM skill_sources WHERE id IN (
            SELECT ss.id FROM skill_sources ss
            JOIN (
                SELECT DISTINCT ON (repo_url) id, repo_url
                FROM skill_sources WHERE repo_url IS NOT NULL
                ORDER BY repo_url, (summary_en IS NOT NULL)::int DESC, stars DESC NULLS LAST, created_at ASC
            ) best ON best.repo_url = ss.repo_url
            WHERE ss.id != best.id
        )
    """)

    # 6. Drop old FK column
    op.drop_column("skills", "skill_source_id")

    # 7. Unique index on repo_url
    op.create_index("uq_skill_sources_repo_url", "skill_sources", ["repo_url"], unique=True, postgresql_where=sa.text("repo_url IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("uq_skill_sources_repo_url", table_name="skill_sources")
    op.add_column("skills", sa.Column("skill_source_id", UUID(as_uuid=True), nullable=True))
    # Restore FK from junction table (pick first source)
    op.execute("""
        UPDATE skills SET skill_source_id = sss.skill_source_id
        FROM skill_source_skills sss WHERE sss.skill_id = skills.id
    """)
    op.drop_table("skill_source_skills")
