# MCP Manager

A unified registry of **18,000+ MCP servers** aggregated from 5 sources into one searchable, self-hosted platform.

**Live demo:** [mcp.yoops.org](https://mcp.yoops.org)

## Features

- **5 sources** — Glama, MCP Registry, Docker MCP Registry, PulseMCP, modelcontextprotocol/servers
- **Semantic search** — RAG-powered search with pgvector embeddings (mxbai-embed-large)
- **AI summaries** — EN/FR summaries generated via Ollama (llama3.1)
- **Skills catalog** — Browse and manage Claude/Copilot/Gemini/Cursor skills
- **Install recipes** — Auto-generated installation configs for 34+ targets (Claude Desktop, VS Code, Cursor, etc.)

## Quick Start

```bash
git clone https://github.com/gaelgael5/mcp-manager
cd mcp-manager
cp .env.example .env   # Edit with your settings
./build.sh             # Build Docker images
./launch.sh            # Start services, clean old containers & images
```

The app will be available at `http://localhost:3001`.

## Scripts

| Script | Description |
|--------|-------------|
| `./build.sh` | Build all Docker images (does not start services) |
| `./build.sh backend` | Build backend image only |
| `./build.sh frontend` | Build frontend image only |
| `./launch.sh` | Start services (recreates containers if image changed), cleans stopped containers >24h and dangling images |
| `./launch.sh backend` | Start backend only |

## Requirements

- Docker & Docker Compose
- Ollama instance (for summaries and embeddings)
- GitHub token (optional, increases API rate limits)
- Google OAuth credentials (optional, for admin login)

## Stack

- **Backend:** FastAPI + SQLAlchemy (async) + PostgreSQL (pgvector)
- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS
- **Search:** pgvector (1024 dim) + TanStack Query
- **LLM:** Ollama (llama3.1 + mxbai-embed-large)

## Usage

```bash
# Sync all sources
docker compose exec mcp-backend python -m mcp_manager.cli sync

# Enrichment (url-resolve, dedup, repo-check, categorize)
docker compose exec mcp-backend python -m mcp_manager.cli enrich

# Indexation (summaries, embeddings, params, install recipes)
docker compose exec mcp-backend python -m mcp_manager.cli index --limit 500

# Rebuild and restart a single service
./build.sh backend && ./launch.sh backend
./build.sh frontend && ./launch.sh frontend
```

## License

MIT
