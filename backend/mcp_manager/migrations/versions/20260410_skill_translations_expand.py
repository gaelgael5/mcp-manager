"""Create skill_sources_translations and skills_translations, backfill from summary_en/summary_fr."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260410_skill_trans_exp"
down_revision = None
branch_labels = None
depends_on = None


_TABLES = [
    ("skill_sources_translations", "skill_source_id", "skill_sources.id", "uq_skill_source_culture"),
    ("skills_translations", "skill_id", "skills.id", "uq_skill_culture"),
]


def _create_translations(table: str, fk_col: str, fk_target: str, uq_name: str) -> None:
    op.create_table(
        table,
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(fk_col, UUID(as_uuid=True), sa.ForeignKey(fk_target, ondelete="CASCADE"), nullable=False),
        sa.Column("culture", sa.String(length=5), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=True),
        sa.Column("heuristic_quality", sa.Integer(), nullable=True),
        sa.Column("llm_quality", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("rag_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(fk_col, "culture", name=uq_name),
    )
    op.create_index(f"idx_{table}_culture", table, ["culture"])


def upgrade():
    for table, fk_col, fk_target, uq_name in _TABLES:
        _create_translations(table, fk_col, fk_target, uq_name)

    op.execute("""
        INSERT INTO skill_sources_translations
            (skill_source_id, culture, summary, source_hash,
             heuristic_quality, llm_quality,
             created_at, updated_at, rag_indexed_at)
        SELECT id, 'en', summary_en, NULL,
               heuristic_quality, llm_quality,
               created_at, created_at, rag_indexed_at
        FROM skill_sources
        WHERE summary_en IS NOT NULL AND length(summary_en) > 0
    """)
    op.execute("""
        INSERT INTO skill_sources_translations
            (skill_source_id, culture, summary, source_hash,
             heuristic_quality, llm_quality,
             created_at, updated_at, rag_indexed_at)
        SELECT id, 'fr', summary_fr, NULL,
               NULL, NULL,
               created_at, created_at, NULL
        FROM skill_sources
        WHERE summary_fr IS NOT NULL AND length(summary_fr) > 0
    """)

    op.execute("""
        INSERT INTO skills_translations
            (skill_id, culture, summary, source_hash,
             heuristic_quality, llm_quality,
             created_at, updated_at, rag_indexed_at)
        SELECT id, 'en', summary_en, NULL,
               heuristic_quality, llm_quality,
               created_at, updated_at, rag_indexed_at
        FROM skills
        WHERE summary_en IS NOT NULL AND length(summary_en) > 0
    """)
    op.execute("""
        INSERT INTO skills_translations
            (skill_id, culture, summary, source_hash,
             heuristic_quality, llm_quality,
             created_at, updated_at, rag_indexed_at)
        SELECT id, 'fr', summary_fr, NULL,
               NULL, NULL,
               created_at, updated_at, NULL
        FROM skills
        WHERE summary_fr IS NOT NULL AND length(summary_fr) > 0
    """)


def downgrade():
    op.drop_index("idx_skills_translations_culture", table_name="skills_translations")
    op.drop_table("skills_translations")
    op.drop_index("idx_skill_sources_translations_culture", table_name="skill_sources_translations")
    op.drop_table("skill_sources_translations")
