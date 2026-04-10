"""Create languages table, seed 12 languages, add FK on culture columns."""

from alembic import op
import sqlalchemy as sa

revision = "20260411_languages"
down_revision = None
branch_labels = None
depends_on = None


_SEED = [
    ("en", "English", True, 10),
    ("fr", "Français", True, 20),
    ("de", "Deutsch", False, 30),
    ("es", "Español", False, 40),
    ("pt", "Português", False, 50),
    ("it", "Italiano", False, 60),
    ("ru", "Русский", False, 70),
    ("ar", "العربية", False, 80),
    ("zh", "中文", False, 90),
    ("ja", "日本語", False, 100),
    ("ko", "한국어", False, 110),
    ("hi", "हिन्दी", False, 120),
]


def upgrade():
    op.create_table(
        "languages",
        sa.Column("code", sa.String(length=5), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    languages = sa.table(
        "languages",
        sa.column("code", sa.String),
        sa.column("name", sa.Text),
        sa.column("is_active", sa.Boolean),
        sa.column("display_order", sa.Integer),
    )
    op.bulk_insert(
        languages,
        [
            {"code": c, "name": n, "is_active": a, "display_order": o}
            for (c, n, a, o) in _SEED
        ],
    )

    op.create_foreign_key(
        "fk_mcp_summaries_culture", "mcp_summaries", "languages",
        ["culture"], ["code"],
    )
    op.create_foreign_key(
        "fk_ss_translations_culture", "skill_sources_translations", "languages",
        ["culture"], ["code"],
    )
    op.create_foreign_key(
        "fk_s_translations_culture", "skills_translations", "languages",
        ["culture"], ["code"],
    )


def downgrade():
    op.drop_constraint("fk_s_translations_culture", "skills_translations", type_="foreignkey")
    op.drop_constraint("fk_ss_translations_culture", "skill_sources_translations", type_="foreignkey")
    op.drop_constraint("fk_mcp_summaries_culture", "mcp_summaries", type_="foreignkey")
    op.drop_table("languages")
