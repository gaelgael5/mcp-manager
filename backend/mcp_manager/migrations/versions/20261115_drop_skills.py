"""Retrait complet des skills : le referentiel ne porte plus que les MCP.

Revision de fusion : la chaine comptait 5 tetes (20260407c, 20260409_quality,
20260409_rag_idx, 20260410_skill_trans_ctr, 20260411_languages), ce qui rendait
`alembic upgrade head` inutilisable. Les drops ci-dessous touchent des objets
crees sur plusieurs de ces branches, donc on les fusionne ici.

Les DDL utilisent IF EXISTS car une partie du schema skills a ete posee a la
main (cf. tmp/*.sql) et l'etat reel de la base peut diverger de l'historique.
"""

from alembic import op

revision = "20261115_drop_skills"
down_revision = (
    "20260407c",
    "20260409_quality",
    "20260409_rag_idx",
    "20260410_skill_trans_ctr",
    "20260411_languages",
)
branch_labels = None
depends_on = None


# Sequences autonomes (CREATE SEQUENCE), non liees aux tables par une identite :
# DROP TABLE ne les emporte pas.
_SEQUENCES = (
    "skill_sources__id_seq",
    "skill_sources_translations__id_seq",
    "skills__id_seq",
    "skills_translations__id_seq",
)


def upgrade():
    # mcp_embeddings est partage MCP/skills : on purge les vecteurs de skills
    # avant de retirer la colonne, sinon les lignes orphelines survivraient a
    # la perte de leur FK.
    op.execute("DELETE FROM mcp_embeddings WHERE skill_id IS NOT NULL")
    op.execute("ALTER TABLE mcp_embeddings DROP COLUMN IF EXISTS skill_id")

    op.execute("ALTER TABLE install_targets DROP COLUMN IF EXISTS skill_modes")

    # Tables de jonction d'abord : elles portent les FK vers skills/skill_sources.
    op.execute("DROP TABLE IF EXISTS preference_group_skills")
    op.execute("DROP TABLE IF EXISTS skill_source_skills")
    op.execute("DROP TABLE IF EXISTS skills_translations")
    op.execute("DROP TABLE IF EXISTS skill_sources_translations")
    op.execute("DROP TABLE IF EXISTS skills")
    op.execute("DROP TABLE IF EXISTS skill_sources")

    for seq in _SEQUENCES:
        op.execute(f"DROP SEQUENCE IF EXISTS {seq}")


def downgrade():
    raise NotImplementedError(
        "Retrait des skills irreversible par migration : les donnees ne sont pas "
        "reconstructibles depuis le schema. Restaurer depuis le pg_dump pris "
        "avant l'upgrade (cf. docs/migration-drop-skills.md)."
    )
