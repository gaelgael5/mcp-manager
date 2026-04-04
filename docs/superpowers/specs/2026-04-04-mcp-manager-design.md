# MCP Manager — Design Spec

## Contexte

Les serveurs MCP (Model Context Protocol) sont disperses dans plusieurs sources :
- **Official MCP Registry** (`registry.modelcontextprotocol.io` / `github.com/mcp`) — annuaire de pointeurs avec server.json, renvoyant vers les vrais repos
- **Docker MCP Registry** (`docker/mcp-registry`) — ~327 serveurs containerises avec server.yaml + tools.json

Chaque source utilise un format different, les metadonnees sont heterogenes, et il n'existe pas de referentiel unifie permettant de :
1. Decouvrir automatiquement les nouveaux serveurs MCP
2. Comprendre ce qu'ils font (syntheses lisibles en/fr)
3. Les installer dans differents contextes (Claude Code, LangGraph, Docker stdio)

## Objectif

Construire une plateforme qui :
- **Collecte automatiquement** les serveurs MCP depuis des sources extensibles
- **Normalise** les metadonnees dans un referentiel PostgreSQL
- **Genere des syntheses IA** en anglais et francais via Ollama
- **Produit des recettes d'installation** par cible (Claude Code, LangGraph, Docker stdio, etc.)
- **Expose une API REST** et un **dashboard React/TypeScript** pour consulter et gerer le referentiel

---

## 1. Architecture globale

```
mcp-manager/
  backend/                      # Python 3.11+ / FastAPI
    mcp_manager/
      connectors/               # Un connecteur par source (extensible)
        base.py                 # Interface abstraite AbstractConnector
        mcp_registry.py         # modelcontextprotocol/registry
        docker_registry.py      # docker/mcp-registry
      db/
        models.py               # SQLAlchemy (4 tables)
        session.py              # Engine + session factory
        migrations/             # Alembic
      summarizer/               # Appel Ollama, generation en/fr
      exporters/                # Generateurs de config par cible
      api/                      # FastAPI routes (REST)
        routers/
          services.py
          summaries.py
          installations.py
          targets.py
          sync.py
        app.py
      cli.py                    # Typer CLI (sync, summarize, export)
    scripts/init.sql            # Schema initial PostgreSQL
    pyproject.toml
    tests/
  frontend/                     # React / TypeScript
    src/
      components/
        ui/                     # Primitives reutilisables
        domain/                 # Composants metier
      pages/
      api/                      # Client API type
      types/
    package.json
    tsconfig.json
  docker-compose.yml            # PostgreSQL + backend + frontend
  scripts/Infra/                # Provisioning LXC (existant)
  .github/workflows/            # Cron sync automatique
```

### Flux principal

1. GitHub Actions (cron 6h) -> `python -m mcp_manager sync` -> poll les sources, detecte les deltas via hash
2. Si nouveau service ou doc modifiee -> `python -m mcp_manager summarize` -> Ollama genere les syntheses en/fr
3. `python -m mcp_manager export --all` -> genere les recettes d'installation
4. API FastAPI expose le referentiel au frontend React
5. Dashboard : consulter les MCP, lire les syntheses, installer vers une cible

---

## 2. Schema PostgreSQL

```sql
-- Table 1 : Referentiel des services MCP
CREATE TABLE mcp_services (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    source_url      TEXT NOT NULL,
    doc_url         TEXT,
    doc_hash        VARCHAR(64),
    branch_hash     VARCHAR(64),
    source_type     VARCHAR(50) NOT NULL,
    transport       VARCHAR(20),
    category        VARCHAR(100),
    tags            TEXT[],
    is_deprecated   BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(source_type, name)
);

-- Table 2 : Syntheses IA par culture
CREATE TABLE mcp_summaries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mcp_service_id  UUID NOT NULL REFERENCES mcp_services(id) ON DELETE CASCADE,
    culture         VARCHAR(5) NOT NULL,
    summary         TEXT NOT NULL,
    source_hash     VARCHAR(64),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(mcp_service_id, culture)
);

-- Table 3 : Referentiel des cibles d'installation
CREATE TABLE install_targets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Table 4 : Recettes d'installation
CREATE TABLE mcp_installations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mcp_service_id  UUID NOT NULL REFERENCES mcp_services(id) ON DELETE CASCADE,
    install_target_id UUID NOT NULL REFERENCES install_targets(id) ON DELETE CASCADE,
    action_type     VARCHAR(50) NOT NULL,
    data            TEXT NOT NULL,
    env_vars        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(mcp_service_id, install_target_id)
);

CREATE INDEX idx_services_source_type ON mcp_services(source_type);
CREATE INDEX idx_summaries_culture ON mcp_summaries(culture);
CREATE INDEX idx_installations_target ON mcp_installations(install_target_id);
```

### Points cles

- UUID partout (compatible distributed)
- `UNIQUE(source_type, name)` pour le dedoublonnage cross-sources
- `source_hash` dans summaries compare au `doc_hash` de mcp_services pour detecter les syntheses perimees
- `env_vars` en JSONB pour flexibilite
- `ON DELETE CASCADE` : suppression d'un service entraine ses syntheses et installations

---

## 3. Connecteurs (import automatise)

### Interface abstraite

```python
class AbstractConnector(ABC):
    @abstractmethod
    async def fetch_services(self) -> list[RawMcpService]: ...

    @abstractmethod
    async def fetch_doc_content(self, service: RawMcpService) -> str | None: ...

    @abstractmethod
    def source_type(self) -> str: ...
```

### Connecteur Docker Registry (`docker/mcp-registry`)

- Clone/pull le repo Git ou fetch via GitHub API
- Parse chaque `mcp-servers/{name}/server.yaml` : name, description, image, transport, category, tags, secrets, volumes
- Parse `tools.json` si present
- `branch_hash` = SHA du dernier commit
- `doc_hash` = SHA-256 du contenu server.yaml + tools.json

### Connecteur Official MCP Registry (`registry.modelcontextprotocol.io`)

- API REST `GET /v0.1/servers?version=latest&limit=96` avec pagination par cursor
- **Suivi des liens** : la page `github.com/mcp/{vendor}/{name}` est un annuaire de pointeurs. Le connecteur :
  1. Recupere le `repository.url` + `repository.subfolder` depuis le server.json
  2. Suit le lien vers le vrai repo (ex: `github.com/microsoft/markitdown`)
  3. Resout le sous-dossier MCP (ex: `packages/markitdown-mcp`)
  4. C'est la que se trouve la vraie doc (README.md)
- `branch_hash` = SHA du dernier commit du repo cible
- `doc_hash` = SHA-256 du README.md du sous-dossier MCP (fallback sur README racine)

### Pipeline de sync

```
1. connector.fetch_services() -> liste de RawMcpService
2. Pour chaque service :
   a. Lookup en DB par (source_type, name)
   b. Si inexistant -> INSERT
   c. Si existant ET hash different -> UPDATE
   d. Si existant ET hash identique -> SKIP
3. Services en DB mais absents de la source -> is_deprecated = TRUE
4. Log : X nouveaux, Y mis a jour, Z inchanges
```

### Extensibilite

- Ajouter une source = creer un fichier dans `connectors/` heritant de `AbstractConnector`
- Enregistrement automatique par discovery de module

---

## 4. Synthese IA (Ollama)

### Declenchement

Apres chaque sync, comparaison `mcp_services.doc_hash` vs `mcp_summaries.source_hash`. Si different ou absent -> a synthetiser.

### Pipeline par service

1. Recuperer le README.md du repo cible (subfolder d'abord, racine en fallback)
2. Nettoyer : retirer badges, images cassees, sections non pertinentes (contributing, license)
3. Pour chaque culture configuree (en, fr) :
   - Prompt Ollama : synthetiser en max 300 mots, inclure fonctionnalites, tools, prerequis, cas d'usage
   - Stocker dans `mcp_summaries`, mettre a jour `source_hash`

### Configuration

- Instance Ollama : `192.168.10.80:11434`
- Modele configurable via `.env` (`OLLAMA_SUMMARY_MODEL`, defaut : `llama3.1`)
- Rate limiting configurable pour ne pas surcharger Ollama

---

## 5. Exporteurs (configs d'installation)

### Moteur de regles

Mappe `registryType + transport` -> recette d'installation par cible :

| registryType | transport | Claude Code | LangGraph | Docker stdio |
|-------------|-----------|-------------|-----------|--------------|
| npm | stdio | `claude mcp add {name} -- npx {id}` | JSON `{command: "npx", args: [...]}` | `docker run -i mcp/{name}` |
| pypi | stdio | `claude mcp add {name} -- uvx {id}` | JSON `{command: "uvx", args: [...]}` | `docker run -i mcp/{name}` |
| oci | stdio | `claude mcp add {name} -- docker run -i {image}` | JSON `{command: "docker", args: ["run", "-i", ...]}` | `docker run -i {image}` |

### Cibles pre-peuplees

| name | description |
|------|-------------|
| claude_code | Claude Code CLI |
| langgraph | LangGraph mcp_servers.json |
| docker_stdio | Docker container avec transport stdio |
| claude_desktop | Claude Desktop app config |

### Recettes

- Generees automatiquement lors du sync
- Modifiables manuellement via API/dashboard
- `env_vars` JSONB stocke les variables d'environnement requises

---

## 6. API REST (FastAPI)

Base : `http://localhost:8000/api/v1`

```
GET    /services                    # Liste paginee, filtres: source_type, category, search, is_deprecated
GET    /services/{id}               # Detail + syntheses + installations
POST   /services/sync               # Declencher un sync manuellement
GET    /services/sync/status        # Statut du dernier sync

GET    /summaries                   # Liste, filtres: culture, mcp_service_id
POST   /summaries/generate          # Generer pour les services outdated
GET    /summaries/stats             # Nb a jour / outdated par culture

GET    /installations               # Liste, filtres: install_target_id, mcp_service_id
GET    /installations/{id}          # Detail
PUT    /installations/{id}          # Modifier manuellement
POST   /installations/generate      # Regenerer les recettes auto

GET    /targets                     # Liste des install_targets
POST   /targets                     # Ajouter une cible
PUT    /targets/{id}                # Modifier

GET    /stats                       # Vue globale
```

- Pagination : `?page=1&per_page=50`
- Recherche full-text : `ILIKE` sur name, description, summary
- CORS configure pour le frontend React (origin via `.env`)

---

## 7. Frontend React/TypeScript

### Stack

- React 18+ / TypeScript strict
- Vite (build)
- React Router (navigation)
- TanStack Query (appels API + cache)
- Tailwind CSS (styling)

### Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Stats globales, derniers services, syntheses outdated, statut sync |
| `/services` | Liste services | Tableau pagine, filtres, tri, recherche |
| `/services/:id` | Detail service | Fiche complete, syntheses en/fr, installations par cible |
| `/targets` | Cibles | Liste des targets, CRUD |
| `/sync` | Sync | Declenchement, historique, logs |

### Composants reutilisables

```
components/
  ui/                       # Primitives
    Button.tsx
    Badge.tsx
    Card.tsx
    DataTable.tsx            # Tableau pagine generique
    SearchInput.tsx
    Modal.tsx
    Tabs.tsx
    StatusBadge.tsx
  domain/                   # Metier
    ServiceCard.tsx
    SummaryView.tsx          # Affichage synthese avec switch culture
    InstallCommand.tsx       # Bloc copiable avec commande d'install
    SyncStatusBar.tsx
    FilterPanel.tsx
```

### Client API type

Module `api/client.ts` avec fonctions typees par endpoint. Types dans `types/` en miroir des modeles backend.

---

## 8. Automatisation

### GitHub Actions — Cron sync

```yaml
# .github/workflows/sync.yml
on:
  schedule:
    - cron: "0 */6 * * *"
  workflow_dispatch:
```

1. Checkout repo
2. Connexion DB (ou docker compose up postgres)
3. `python -m mcp_manager sync`
4. `python -m mcp_manager summarize`
5. `python -m mcp_manager export --all`

### Docker Compose

```yaml
services:
  langgraph-postgres:           # Existant — pgvector:pg16
    ...

  mcp-backend:
    build: ./backend
    ports: ["127.0.0.1:8000:8000"]
    depends_on:
      langgraph-postgres: { condition: service_healthy }
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@langgraph-postgres:5432/${POSTGRES_DB}
      OLLAMA_BASE_URL: http://192.168.10.80:11434
      OLLAMA_SUMMARY_MODEL: ${OLLAMA_SUMMARY_MODEL:-llama3.1}

  mcp-frontend:
    build: ./frontend
    ports: ["127.0.0.1:3001:80"]
    depends_on: [mcp-backend]
```

### CLI (Typer)

```bash
python -m mcp_manager sync                     # Sync toutes les sources
python -m mcp_manager sync --source docker     # Sync une source
python -m mcp_manager summarize                # Syntheses outdated
python -m mcp_manager summarize --force        # Tout regenerer
python -m mcp_manager export --target langgraph --output mcp_servers.json
```

### Migrations

Alembic pour les evolutions de schema. `scripts/init.sql` pour le schema initial.

---

## 9. Verification & Tests

### Backend

- **Unitaires** : connecteurs (mock GitHub API), summarizer (mock Ollama), exporteurs
- **Integration** : pipeline sync complet avec PostgreSQL reel (testcontainers)
- **API** : endpoints FastAPI via `httpx.AsyncClient`

### Frontend

- **Composants** : Vitest + React Testing Library
- **Pages** : rendu avec donnees mockees, navigation

### End-to-end

1. `docker compose up -d` -> les 3 services demarrent
2. `python -m mcp_manager sync` -> services en DB
3. `GET /api/v1/stats` -> compteurs > 0
4. `python -m mcp_manager summarize` -> syntheses generees
5. Dashboard `:3001` -> services affiches, filtres fonctionnels
6. `python -m mcp_manager export --target claude_code` -> commandes valides

### Qualite

- Backend : `ruff` (lint + format), `mypy` (types)
- Frontend : `eslint`, `prettier`, TypeScript strict
