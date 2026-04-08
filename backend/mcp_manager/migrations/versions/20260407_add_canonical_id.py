"""add canonical_id to mcp_services and skills

Revision ID: 20260407c
Revises: 20260407b
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = "20260407c"
down_revision = "20260407b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mcp_services", sa.Column("canonical_id", sa.String(500), nullable=True))
    op.create_index("idx_services_canonical_id", "mcp_services", ["canonical_id"])

    # Backfill: GitHub URLs -> github:owner/repo, else raw:source_type:name
    op.execute("""
        UPDATE mcp_services
        SET canonical_id = CASE
            WHEN source_url ~ '^https?://github\\.com/[^/]+/[^/]+'
            THEN 'github:' || lower(
                regexp_replace(
                    regexp_replace(
                        regexp_replace(source_url, '^https?://github\\.com/', ''),
                        '\\.git$', ''
                    ),
                    '/tree/[^/]+', ''
                )
            )
            WHEN package_info->>'registry_type' = 'npm'
                 AND package_info->>'package_identifier' IS NOT NULL
            THEN 'npm:' || (package_info->>'package_identifier')
            WHEN package_info->>'registry_type' = 'pypi'
                 AND package_info->>'package_identifier' IS NOT NULL
            THEN 'pypi:' || lower(package_info->>'package_identifier')
            ELSE 'raw:' || source_type || ':' || name
        END
        WHERE canonical_id IS NULL
    """)

    # Skills: canonical_id = github:owner/repo:skill_name
    op.add_column("skills", sa.Column("canonical_id", sa.String(500), nullable=True))
    op.create_index("idx_skills_canonical_id", "skills", ["canonical_id"])

    op.execute("""
        UPDATE skills
        SET canonical_id = CASE
            WHEN source_url ~ '^https?://github\\.com/[^/]+/[^/]+'
            THEN 'github:' || lower(
                regexp_replace(
                    regexp_replace(source_url, '^https?://github\\.com/', ''),
                    '\\.git$', ''
                )
            ) || ':' || lower(name)
            ELSE 'raw:skill:' || lower(name)
        END
        WHERE canonical_id IS NULL
    """)


def downgrade() -> None:
    op.drop_index("idx_skills_canonical_id", table_name="skills")
    op.drop_column("skills", "canonical_id")
    op.drop_index("idx_services_canonical_id", table_name="mcp_services")
    op.drop_column("mcp_services", "canonical_id")
