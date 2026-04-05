# Data Enrichment Pipeline — Design Spec

## Contexte

Le referentiel MCP Manager contient 5496 services importes depuis 3 sources. La qualite des donnees est heterogene :
- 736 services MCP Registry sans `source_url` (14%)
- 532 sans `doc_url` (10%)
- 5162 sans `category` (tout le MCP Registry)
- ~43 doublons cross-sources (meme serveur dans Docker ET MCP Registry)

## Objectif

Un pipeline d'enrichissement en 3 passes independantes qui :
1. Resout les URLs manquantes depuis les noms reverse-DNS
2. Fusionne les doublons cross-sources
3. Auto-categorise les services sans categorie via Ollama

---

## Passe 1 : Resolution d'URLs

**Module :** `backend/mcp_manager/enrichment/url_resolver.py`

**Logique :**
Pour chaque service sans `source_url` :
1. Parser le nom reverse-DNS :
   - `io.github.{owner}/{repo}` → `https://github.com/{owner}/{repo}`
   - `com.{domain}/{repo}` → tenter `https://github.com/{domain}/{repo}`
   - `ai.{domain}/{repo}` → tenter `https://github.com/{domain}/{repo}`
2. HEAD request sur l'URL candidate (avec GitHub token si disponible)
   - 200 → adopter comme `source_url`
   - 404 → skip (service remote-only)
3. Si `source_url` trouvee et `doc_url` manquant → `doc_url = source_url`

**Rate limiting :** max 10 requetes/seconde vers GitHub API.

**CLI :** `python -m mcp_manager.cli enrich --pass url-resolve`

---

## Passe 2 : Fusion cross-sources

**Module :** `backend/mcp_manager/enrichment/dedup.py`

**Matching (par ordre de fiabilite) :**
1. `source_url` identique (apres normalisation : trim trailing slash, lowercase)
2. Nom Docker contenu dans le nom MCP Registry (`brave` match `io.github.brave/brave-search-mcp-server`)

**Regles de fusion :**
- L'entree Docker est la **survivante** (categorie, tags, image Docker)
- On enrichit la survivante avec les donnees MCP Registry :
  - `registry_type`, `package_identifier`, `runtime_hint`, `env_vars` → stockes dans `package_info` (JSONB)
  - `branch_hash` (version) si plus recent
- L'entree MCP Registry fusionnee est **supprimee** (CASCADE)
- Champ `source_origins` (TEXT[]) trace les sources d'origine : `["docker_registry", "mcp_registry"]`

**Schema DB — 2 nouveaux champs sur `mcp_services` :**
```sql
ALTER TABLE mcp_services ADD COLUMN package_info JSONB DEFAULT '{}';
ALTER TABLE mcp_services ADD COLUMN source_origins TEXT[] DEFAULT '{}';
```

`package_info` stocke :
```json
{
  "registry_type": "npm",
  "package_identifier": "@playwright/mcp",
  "runtime_hint": "npx",
  "env_vars": {"PLAYWRIGHT_HEADLESS": "Run headless"}
}
```

**CLI :** `python -m mcp_manager.cli enrich --pass dedup`

---

## Passe 3 : Auto-categorisation IA

**Module :** `backend/mcp_manager/enrichment/categorizer.py`

**Categories de reference :**
```
database, devops, ai, ai-ml, security, monitoring, productivity,
communication, search, development, developer-tools, finance,
analytics, documentation, web, blockchain, commerce, ecommerce,
infrastructure, automation, integration, iot, games, media,
video, news, travel, healthcare, geospatial, maps, messaging,
data-analytics, data-visualization, reference
```

**Pipeline :**
Pour chaque service sans categorie ET avec description non vide :
1. Prompt Ollama contraint : nom + description → une seule categorie
2. Valider la reponse contre la liste connue
   - Match → UPDATE category
   - Pas match → skip (garder null)

**Optimisation :**
- Batch par lots de 50
- Rate limiting : 5 appels/seconde max vers Ollama
- Services sans description → skip
- Log : nombre categorises / skipped

**CLI :** `python -m mcp_manager.cli enrich --pass categorize`

---

## Commande globale

`python -m mcp_manager.cli enrich` — lance les 3 passes dans l'ordre :
1. url-resolve
2. dedup
3. categorize

Chaque passe est idempotente : relancer ne cree pas de doublons ni de corruption.

---

## Fichiers a creer/modifier

**Creer :**
- `backend/mcp_manager/enrichment/__init__.py`
- `backend/mcp_manager/enrichment/url_resolver.py`
- `backend/mcp_manager/enrichment/dedup.py`
- `backend/mcp_manager/enrichment/categorizer.py`
- `backend/tests/test_enrichment/__init__.py`
- `backend/tests/test_enrichment/test_url_resolver.py`
- `backend/tests/test_enrichment/test_dedup.py`
- `backend/tests/test_enrichment/test_categorizer.py`

**Modifier :**
- `backend/mcp_manager/db/models.py` — ajouter `package_info` et `source_origins` sur `McpService`
- `backend/mcp_manager/cli.py` — ajouter la commande `enrich`
- `backend/scripts/init.sql` — ajouter les colonnes
- Alembic migration pour les 2 nouveaux champs

---

## Verification

1. Avant enrichissement : `SELECT COUNT(*) FROM mcp_services WHERE source_url = ''` → ~736
2. Apres passe 1 : ce nombre diminue significativement
3. Apres passe 2 : `SELECT COUNT(*) FROM mcp_services` diminue (~43 doublons supprimes)
4. Apres passe 3 : `SELECT COUNT(*) FROM mcp_services WHERE category IS NULL` diminue significativement
