"""Add heuristic_quality and llm_quality columns to mcp_summaries, skill_sources, skills."""

from alembic import op
import sqlalchemy as sa

revision = "20260409_quality"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("mcp_summaries", sa.Column("heuristic_quality", sa.Integer, nullable=True))
    op.add_column("mcp_summaries", sa.Column("llm_quality", sa.Integer, nullable=True))
    op.add_column("skill_sources", sa.Column("heuristic_quality", sa.Integer, nullable=True))
    op.add_column("skill_sources", sa.Column("llm_quality", sa.Integer, nullable=True))
    op.add_column("skills", sa.Column("heuristic_quality", sa.Integer, nullable=True))
    op.add_column("skills", sa.Column("llm_quality", sa.Integer, nullable=True))


def downgrade():
    op.drop_column("skills", "llm_quality")
    op.drop_column("skills", "heuristic_quality")
    op.drop_column("skill_sources", "llm_quality")
    op.drop_column("skill_sources", "heuristic_quality")
    op.drop_column("mcp_summaries", "llm_quality")
    op.drop_column("mcp_summaries", "heuristic_quality")
