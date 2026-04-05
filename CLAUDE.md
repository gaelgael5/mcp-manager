# MCP Manager — Instructions Claude Code

## Projet

Referentiel unifie de serveurs MCP (Model Context Protocol) agregeant 5 sources (18k+ services).
Stack : FastAPI + PostgreSQL (pgvector) + React/TypeScript + Docker Compose, sur Proxmox LXC 113 (Ubuntu 24).

**Standard de qualite** : code propre et bien fait, jamais la rapidite au detriment de la rigueur. Pas de raccourcis. Chaque tache est faite correctement ou pas du tout.

## Commandes essentielles

```bash
# Deploy sur LXC 113 (192.168.10.99)
tar --exclude='.git' --exclude='node_modules' --exclude='.venv' --exclude='__pycache__' --exclude='dist' --exclude='.env' --exclude='.playwright-mcp' -czf /tmp/mcp-manager.tar.gz .
scp -i ~/.ssh/id_shellia /tmp/mcp-manager.tar.gz root@192.168.10.99:/tmp/
ssh -i ~/.ssh/id_shellia root@192.168.10.99 "cd /root/mcp-manager && tar xzf /tmp/mcp-manager.tar.gz && rm /tmp/mcp-manager.tar.gz && docker compose up -d --build mcp-backend mcp-frontend"

# Docker Compose
docker compose up -d                            # Lancer la stack (postgres + backend + frontend)
docker compose up -d --build mcp-backend        # Rebuild backend seul
docker compose up -d --build mcp-frontend       # Rebuild frontend seul
docker compose logs mcp-backend --tail 30       # Logs backend

# CLI (dans le container backend)
docker compose exec mcp-backend python -m mcp_manager.cli sync                    # Sync toutes les sources
docker compose exec mcp-backend python -m mcp_manager.cli sync --source glama     # Sync une source
docker compose exec mcp-backend python -m mcp_manager.cli enrich                  # Enrichissement (url-resolve, dedup, repo-check, categorize)
docker compose exec mcp-backend python -m mcp_manager.cli enrich --pass dedup     # Une passe specifique
docker compose exec mcp-backend python -m mcp_manager.cli index --limit 500       # Indexation (summary, embeddings, params, recettes)
docker compose exec mcp-backend python -m mcp_manager.cli export --target all     # Generer recettes pour toutes les targets
docker compose exec mcp-backend python scripts/seed_targets.py                    # Peupler les 34 targets

# Frontend
cd frontend && npm run build                    # Build React
cd frontend && npm run dev                      # Dev server (port 3001)

# Base de donnees
docker compose exec mcp-manager-postgres psql -U langgraph -d langgraph
```

## Navigation du code

```
backend/
  mcp_manager/
    api/                    # FastAPI (app.py + routers/)
      routers/
        services.py         # CRUD services + filtres
        search.py           # API publique de recherche (texte + semantique)
        summaries.py        # Syntheses IA (generate par service)
        installations.py    # Recettes d'installation
        targets.py          # Cibles d'installation (34 targets)
        parameters.py       # Parametres de configuration
        sync.py             # Declenchement sync
        stats.py            # Statistiques globales
        openapi_search.py   # Spec OpenAPI pour l'API search
    connectors/             # Un connecteur par source
      base.py               # AbstractConnector + RawMcpService
      registry.py           # Registre des connecteurs (@register_connector)
      docker_registry.py    # docker/mcp-registry (327 servers)
      mcp_registry.py       # registry.modelcontextprotocol.io (5k+ servers)
      mcp_servers_repo.py   # modelcontextprotocol/servers (7 reference servers)
      glama.py              # glama.ai API (14k+ servers)
      pulsemcp.py           # pulsemcp.com scraping (900+ servers)
    db/
      models.py             # SQLAlchemy: McpService, McpSummary, InstallTarget, McpInstallation, McpParameter, McpEmbedding
      session.py            # Engine + SessionLocal
    enrichment/             # Passes d'enrichissement
      url_resolver.py       # Passe 1: resolve source_url depuis noms reverse-DNS
      dedup.py              # Passe 2: fusion doublons cross-sources
      repo_checker.py       # Passe 3: verification accessibilite repos GitHub
      categorizer.py        # Passe 4: auto-categorisation via Ollama
    indexer/                # Pipeline d'indexation
      pipeline.py           # Orchestrateur (summary + embeddings + params + recettes)
      chunker.py            # Decoupe texte en chunks pour embedding
      embedder.py           # Appel Ollama mxbai-embed-large
    summarizer/
      summarizer.py         # Generation summary via Ollama
      cleaner.py            # Nettoyage markdown
      ollama_client.py      # Client HTTP Ollama
    exporters/
      engine.py             # Moteur de regles (modes des targets -> recettes)
    config.py               # Pydantic Settings
    cli.py                  # Typer CLI (sync, enrich, index, export)
  prompts/                  # Prompts externalises
    summarize_en.md
    summarize_fr.md
  scripts/
    seed_targets.py         # Peuplement des 34 targets
    init.sql                # Schema initial PostgreSQL

frontend/
  src/
    api/                    # Client API type (React Query hooks)
    components/
      ui/                   # Primitives reutilisables (Button, Badge, Card, etc.)
      domain/               # Composants metier (ServiceCard, SummaryView, etc.)
    pages/                  # DashboardPage, ServicesPage, ServiceDetailPage, etc.
    layouts/MainLayout.tsx
    types/index.ts
```

## Schema PostgreSQL

- **mcp_services** — referentiel principal (name, source_url, transport, category, repo_status, needs_reindex, package_info)
- **mcp_summaries** — syntheses IA par culture (en/fr)
- **mcp_parameters** — parametres requis (env vars, secrets)
- **mcp_installations** — recettes d'installation par target
- **install_targets** — 34 cibles avec modes JSONB (runtime, action_type, template)
- **mcp_embeddings** — vecteurs pgvector (1024 dim, mxbai-embed-large)

## Conventions

- **Python 3.11+**, async/await (FastAPI + SQLAlchemy async)
- **React 18 + TypeScript strict**, Vite, Tailwind CSS, TanStack Query
- **Connecteurs** : ajouter un connecteur = creer un fichier dans connectors/ + l'importer dans __init__.py
- **Prompts** : externalises dans backend/prompts/*.md, pas de prompt hardcode
- **Targets** : modes configurables via JSONB, pas de logique hardcodee dans engine.py
- **Deploy** : tar + scp vers LXC 113 (192.168.10.99), SSH via ~/.ssh/id_shellia
- **Commits** : en francais, format conventionnel

## Infra

- **PVE** : 192.168.10.41 (Proxmox)
- **LXC 113** : 192.168.10.99 (mcp-manager, Docker)
- **Ollama** : 192.168.10.80:11434 (llama3.1:8b, mxbai-embed-large)
- **Ports** : 8000 (backend API), 3001 (frontend), 5432 (PostgreSQL)
