"""Drop legacy summary_en/summary_fr and quality/rag columns from skill_sources and skills."""

from alembic import op

revision = "20260410_skill_trans_ctr"
down_revision = "20260410_skill_trans_exp"
branch_labels = None
depends_on = None


_COLUMNS = ("summary_en", "summary_fr", "heuristic_quality", "llm_quality", "rag_indexed_at")


def upgrade():
    with op.batch_alter_table("skill_sources") as batch:
        for col in _COLUMNS:
            batch.drop_column(col)
    with op.batch_alter_table("skills") as batch:
        for col in _COLUMNS:
            batch.drop_column(col)


def downgrade():
    raise RuntimeError(
        "contract migration is not automatically reversible; restore from backup instead"
    )
