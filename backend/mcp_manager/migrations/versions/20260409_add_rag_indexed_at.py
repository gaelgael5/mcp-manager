"""Add rag_indexed_at to mcp_summaries, skill_sources, skills."""

from alembic import op
import sqlalchemy as sa

revision = "20260409_rag_idx"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("mcp_summaries", sa.Column("rag_indexed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("skill_sources", sa.Column("rag_indexed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("skills", sa.Column("rag_indexed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("skills", "rag_indexed_at")
    op.drop_column("skill_sources", "rag_indexed_at")
    op.drop_column("mcp_summaries", "rag_indexed_at")
