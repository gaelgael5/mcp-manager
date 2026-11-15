# Retrait des skills — procedure de migration

Le referentiel ne porte plus que les serveurs MCP. Les skills (sources et skills
individuels) sont retires du code et de la base.

Revision Alembic : `20261115_drop_skills`.

**Appliquee le 2026-11-15 sur le LXC 113.** Resultat constate : plus aucune
table, colonne ni sequence `%skill%`, et 89 962 vecteurs MCP conserves dans
`mcp_embeddings`.

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

## Aucune sauvegarde n'a ete prise

Decision explicite du proprietaire du projet : les donnees skills n'avaient pas
de valeur a conserver, le `pg_dump` prealable a donc ete ecarte.

Consequence : **la suppression est definitive**. `downgrade()` leve
`NotImplementedError` — le schema seul ne permet pas de reconstruire les
donnees, et il n'existe aucun dump vers lequel se retourner. Le message de
`downgrade()` mentionne un dump « pris avant l'upgrade » : il n'y en a pas eu.
Ce fichier de migration n'est pas retouche, une revision appliquee etant
immuable.

## Pre-requis : reparer `alembic_version`

C'est la vraie difficulte de cette migration, et elle l'a fait echouer deux
fois avant d'etre comprise.

L'historique Alembic compte **cinq racines independantes** (cinq fichiers avec
`down_revision = None`) :

- la chaine `20260406b` → `20260407a` → `20260407b` → `20260407c`
- `20260409_quality`
- `20260409_rag_idx`
- `20260410_skill_trans_exp` → `20260410_skill_trans_ctr`
- `20260411_languages`

`20261115_drop_skills` est une revision de fusion : son `down_revision` est le
tuple des cinq tetes. Elle n'est donc applicable que si les cinq sont
enregistrees dans `alembic_version`.

Or la base de production ne contenait que `20260407c`. Les quatre autres
branches avaient bien ete appliquees, mais **a la main** (cf. `tmp/*.sql` et
`backend/scripts/init.sql`), sans jamais etre tracees. `alembic upgrade head`
tentait donc de les rejouer et echouait sur le premier `CREATE TABLE` :

```
asyncpg.exceptions.DuplicateTableError: relation "languages" already exists
```

### 1. Verifier que le DDL est bien en place

Ne jamais enregistrer une revision a l'aveugle : si elle n'etait que
partiellement posee, on masquerait un trou de schema. Seuls les objets
concernant les MCP importent ici, le reste ne touchant que les tables skills.

```bash
docker compose exec -T mcp-manager-postgres psql -U langgraph -d langgraph -c "
  SELECT column_name FROM information_schema.columns
  WHERE table_name='mcp_summaries'
    AND column_name IN ('heuristic_quality','llm_quality','rag_indexed_at');
  SELECT conname FROM pg_constraint WHERE conname='fk_mcp_summaries_culture';
  SELECT version_num FROM alembic_version;"
```

Attendu : 3 colonnes, 1 contrainte, et `20260407c` seul.

### 2. Enregistrer les quatre revisions manquantes

`alembic_version` admet plusieurs lignes, une par tete.

```bash
docker compose exec -T mcp-manager-postgres psql -U langgraph -d langgraph -c "
  INSERT INTO alembic_version (version_num) VALUES
    ('20260409_quality'),
    ('20260409_rag_idx'),
    ('20260410_skill_trans_ctr'),
    ('20260411_languages');"
```

Ecriture directe plutot que `alembic stamp` : `stamp` raisonne sur un chemin
entre deux revisions, et ces branches n'en ont aucun entre elles. Il faut que
les cinq tetes coexistent pour que la fusion devienne applicable.

## Procedure

Sur le LXC 113 (`192.168.10.99`), depuis `/root/mcp-manager`.

### 1. Deploiement du code

**Utiliser le deploy git, pas le `tar`** :

```bash
/root/deploy-mcp.sh && tail -20 /root/deploy.log
```

Son `git reset --hard origin/master` supprime les fichiers retires du depot.
Le `tar xzf` de CLAUDE.md, lui, n'efface rien : les 4 pages `Skill*Page.tsx`
survivraient dans `frontend/src/`, et comme `tsconfig.app.json` declare
`"include": ["src"]`, `tsc -b` les typechecke meme si plus rien ne les importe.
Le build de `mcp-frontend` echoue alors sur des `TS2305` / `TS2307`.

Attendre `Deploy OK`, puis verifier que le conteneur a bien ete recree (et non
laisse en place, auquel cas le healthcheck a interroge l'ancien) :

```bash
docker ps --format '{{.Names}}\t{{.Status}}\t{{.CreatedAt}}' | grep mcp-
docker compose logs mcp-backend --tail 40
```

C'est le demarrage du nouveau conteneur qui valide reellement les modeles : le
hook de startup interroge `McpService`, ce qui force la configuration des
mappers SQLAlchemy. Ni `ImportError` ni erreur de mapper dans les logs = les
modeles amputes des skills tiennent.

### 2. Reparer `alembic_version`

Cf. section precedente.

### 3. Migration

```bash
docker compose exec mcp-backend alembic upgrade head
docker compose exec mcp-backend alembic current
```

`current` doit renvoyer `20261115_drop_skills (head) (mergepoint)` : la fusion
remplace les cinq lignes d'`alembic_version` par une seule.

### 4. Verification

```bash
docker compose exec -T mcp-manager-postgres psql -U langgraph -d langgraph -c "
  SELECT table_name FROM information_schema.tables
  WHERE table_schema='public' AND table_name LIKE '%skill%';
  SELECT column_name FROM information_schema.columns
  WHERE (table_name='mcp_embeddings' AND column_name='skill_id')
     OR (table_name='install_targets' AND column_name='skill_modes');
  SELECT sequence_name FROM information_schema.sequences
  WHERE sequence_name LIKE '%skill%';"
```

Zero ligne aux trois.

### 5. Reseed des targets

`install_targets.skill_modes` ayant disparu, rejouer le seed pour aligner les
cibles :

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
