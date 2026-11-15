# Retrait des skills — procedure de migration

Le referentiel ne porte plus que les serveurs MCP. Les skills (sources et skills
individuels) sont retires du code et de la base.

Revision Alembic : `20261115_drop_skills`.

## Ce que la migration detruit

| Objet | Type | Volume indicatif |
|---|---|---|
| `skills` | table | ~925k lignes |
| `skills_translations` | table | ~95k lignes |
| `skill_sources` | table | ~10k lignes |
| `skill_sources_translations` | table | ~11k lignes |
| `skill_source_skills` | table de jonction | — |
| `preference_group_skills` | table de jonction | — |
| `skill_sources__id_seq`, `skills__id_seq`, `skill_sources_translations__id_seq`, `skills_translations__id_seq` | sequences | — |
| `mcp_embeddings.skill_id` | colonne (+ lignes `skill_id IS NOT NULL`) | — |
| `install_targets.skill_modes` | colonne | — |

Les groupes de preference survivent : ils ne perdent que leur moitie skills,
leurs services sont intacts.

**La migration est irreversible.** `downgrade()` leve `NotImplementedError` :
le schema seul ne permet pas de reconstruire les donnees. Le seul chemin de
retour est le dump pris a l'etape 1.

## Procedure

Sur le LXC 113 (`192.168.10.99`), depuis `/root/mcp-manager`.

### 1. Dump prealable (obligatoire)

```bash
mkdir -p /opt/mcp-manager-data/backups
docker compose exec -T mcp-manager-postgres pg_dump -U langgraph -d langgraph \
  -t skill_sources -t skill_sources_translations \
  -t skills -t skills_translations \
  -t skill_source_skills -t preference_group_skills \
  | gzip > /opt/mcp-manager-data/backups/skills-$(date +%Y%m%d).sql.gz
```

Verifier que le dump est non vide avant d'aller plus loin :

```bash
ls -lh /opt/mcp-manager-data/backups/skills-*.sql.gz
gzip -t /opt/mcp-manager-data/backups/skills-*.sql.gz && echo "archive valide"
```

`skills` approche le million de lignes : prevoir la place disque et quelques
minutes.

### 2. Deploiement du code

Depuis le poste de dev, la commande de deploy habituelle (cf. CLAUDE.md).

### 3. Migration

La chaine Alembic comptait 5 tetes, que cette revision fusionne. `upgrade head`
redevient donc utilisable — il etait en echec avant.

```bash
docker compose exec mcp-backend alembic upgrade head
docker compose exec mcp-backend alembic current   # -> 20261115_drop_skills (head)
```

### 4. Verification

```bash
docker compose exec -T mcp-manager-postgres psql -U langgraph -d langgraph -c "
  SELECT table_name FROM information_schema.tables
  WHERE table_schema='public' AND table_name LIKE '%skill%';"
# attendu : 0 ligne

docker compose exec -T mcp-manager-postgres psql -U langgraph -d langgraph -c "
  SELECT column_name FROM information_schema.columns
  WHERE (table_name='mcp_embeddings' AND column_name='skill_id')
     OR (table_name='install_targets' AND column_name='skill_modes');"
# attendu : 0 ligne
```

### 5. Reseed des targets

`install_targets.skill_modes` ayant disparu, rejouer le seed pour aligner les
34 cibles :

```bash
docker compose exec mcp-backend python scripts/seed_targets.py
```

## Contrats publics rompus

Suppression franche, sans route de transition. Les consommateurs externes
recoivent une erreur et non une liste vide.

| Appel | Avant | Apres |
|---|---|---|
| `GET /api/v1/search_skills` | 200 | 404 |
| `GET /api/v1/search_skill_sources` | 200 | 404 |
| `POST /api/v1/community/sync` avec `table` = `skills`, `skills_translations`, `skill_sources`, `skill_sources_translations` | 200 | 400 `Unknown table` |
| `POST`/`DELETE /api/v1/preference-groups/{id}/skills/{skill_id}` | 200 | 404 |
| `GET /api/v1/skills/{id}/groups` | 200 | 404 |

La spec `GET /api/v1/openapi-search.json` ne declare plus ces chemins ni les
schemas `SkillResult`, `SkillSourceResult` et `Translation`. La whitelist de
`/community/sync` passe de 8 a 4 tables (`mcp_services`, `mcp_summaries`,
`mcp_parameters`, `mcp_installations`).

Les noeuds communautaires qui repliquaient le catalogue doivent retirer les 4
tables skills de leur boucle de sync, sans quoi chaque cycle logge un 400.
