"""add stars column to mcp_services and skill_sources

Revision ID: 20260407a
Revises: 20260406b
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = "20260407a"
down_revision = "20260406b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mcp_services", sa.Column("stars", sa.Integer, nullable=True))
    op.add_column("skill_sources", sa.Column("stars", sa.Integer, nullable=True))


def downgrade() -> None:
    op.drop_column("skill_sources", "stars")
    op.drop_column("mcp_services", "stars")
