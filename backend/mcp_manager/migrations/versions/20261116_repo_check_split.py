"""Separer l'accessibilite du depot du resultat de l'indexation, et dater les controles.

`repo_status` portait deux informations sans rapport : l'accessibilite du depot
('ok', '404') ecrite par repo_checker, et le resultat de l'indexation
('index_failed', 'no_doc') ecrit par indexer/pipeline.py — qui ecrasait donc le
verdict du depot. Chacune prend sa colonne.

La remise a zero des '404' est volontaire : un sondage de 200 de ces services
le 2026-11-15 a montre que 87% avaient un depot GitHub vivant, l'ancien
vericateur assimilant tout code != 200 a une disparition. Ces verdicts etaient
faux, ils sont effaces pour etre reconstruits. Cf. docs/repo-check.md.

Les DDL utilisent IF EXISTS / IF NOT EXISTS car une partie du schema a ete
posee a la main et l'etat reel de la base peut diverger de l'historique.
"""

from alembic import op

revision = "20261116_repo_check_split"
down_revision = "20261115_drop_skills"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE mcp_services ADD COLUMN IF NOT EXISTS repo_checked_at TIMESTAMPTZ")
    op.execute("ALTER TABLE mcp_services ADD COLUMN IF NOT EXISTS index_status VARCHAR(20)")

    # Deplacer le resultat d'indexation vers sa colonne.
    op.execute("""
        UPDATE mcp_services
           SET index_status = repo_status,
               repo_status = NULL
         WHERE repo_status IN ('index_failed', 'no_doc')
    """)

    # Effacer les verdicts d'accessibilite non fiables.
    op.execute("UPDATE mcp_services SET repo_status = NULL WHERE repo_status = '404'")

    # repo_checker balaye les lignes sans date de controle par curseur sur _id.
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_services_repo_unchecked
            ON mcp_services (_id)
         WHERE repo_checked_at IS NULL
    """)


def downgrade():
    # Les verdicts '404' effaces a l'upgrade ne sont pas reconstructibles : la
    # colonne ne les contenait plus. Seule la fusion des deux statuts est
    # annulee.
    op.execute("DROP INDEX IF EXISTS idx_services_repo_unchecked")
    op.execute("""
        UPDATE mcp_services
           SET repo_status = index_status
         WHERE index_status IS NOT NULL
           AND repo_status IS NULL
    """)
    op.execute("ALTER TABLE mcp_services DROP COLUMN IF EXISTS index_status")
    op.execute("ALTER TABLE mcp_services DROP COLUMN IF EXISTS repo_checked_at")
