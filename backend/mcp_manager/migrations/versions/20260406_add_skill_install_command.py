"""add install_command and weekly_installs to skills

Revision ID: 20260406b
Revises:
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = "20260406b"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("skills", sa.Column("install_command", sa.Text, nullable=True))
    op.add_column("skills", sa.Column("weekly_installs", sa.Integer, server_default=sa.text("0")))


def downgrade() -> None:
    op.drop_column("skills", "weekly_installs")
    op.drop_column("skills", "install_command")
