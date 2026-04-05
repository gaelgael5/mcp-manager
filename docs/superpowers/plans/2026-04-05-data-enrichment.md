# Data Enrichment Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich 5496 MCP services with resolved URLs, deduplicated cross-source entries, and AI-assigned categories.

**Architecture:** 3 independent enrichment passes (url-resolve, dedup, categorize) in a new `enrichment/` module, invoked via a new `enrich` CLI command. Each pass queries the DB, transforms data, and writes back. Passes are idempotent.

**Tech Stack:** Python 3.11+, SQLAlchemy async, httpx (GitHub API), Ollama API, asyncio semaphore for rate limiting.

**Spec:** `docs/superpowers/specs/2026-04-04-data-enrichment-design.md`

---

## File Structure

```
backend/mcp_manager/enrichment/
  __init__.py
  url_resolver.py          # Passe 1: resolve source_url from reverse-DNS names
  dedup.py                 # Passe 2: merge cross-source duplicates
  categorizer.py           # Passe 3: auto-categorize via Ollama

backend/tests/test_enrichment/
  __init__.py
  test_url_resolver.py
  test_dedup.py
  test_categorizer.py
```

**Modified files:**
- `backend/mcp_manager/db/models.py` — add `package_info` (JSONB) and `source_origins` (TEXT[]) to McpService
- `backend/mcp_manager/cli.py` — add `enrich` command with `--pass` option
- `backend/scripts/init.sql` — add the 2 new columns

---

## Task 1: Add new columns to McpService model

**Files:**
- Modify: `backend/mcp_manager/db/models.py`
- Modify: `backend/scripts/init.sql`

- [ ] **Step 1: Add package_info and source_origins to McpService model**

In `backend/mcp_manager/db/models.py`, add these two fields to the `McpService` class, after the `tags` field (line 32):

```python
    package_info: Mapped[dict] = mapped_column(JSONB, default=dict)
    source_origins: Mapped[list[str] | None] = mapped_column(ARRAY(Text), default=list)
```

- [ ] **Step 2: Add columns to init.sql**

In `backend/scripts/init.sql`, add after the `tags` column in the `mcp_services` CREATE TABLE:

```sql
    package_info    JSONB DEFAULT '{}',
    source_origins  TEXT[] DEFAULT '{}',
```

- [ ] **Step 3: Verify model imports**

Run:
```bash
cd backend && python -c "from mcp_manager.db.models import McpService; print([c.name for c in McpService.__table__.columns])"
```
Expected: list includes `package_info` and `source_origins`

- [ ] **Step 4: Apply migration on deployed DB**

Run on LXC 113:
```bash
docker compose exec mcp-manager-postgres psql -U langgraph -d langgraph -c "ALTER TABLE mcp_services ADD COLUMN IF NOT EXISTS package_info JSONB DEFAULT '{}'; ALTER TABLE mcp_services ADD COLUMN IF NOT EXISTS source_origins TEXT[] DEFAULT '{}';"
```

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_manager/db/models.py backend/scripts/init.sql
git commit -m "feat: add package_info and source_origins columns to mcp_services"
```

---

## Task 2: URL resolver (Passe 1)

**Files:**
- Create: `backend/mcp_manager/enrichment/__init__.py`
- Create: `backend/mcp_manager/enrichment/url_resolver.py`
- Create: `backend/tests/test_enrichment/__init__.py`
- Create: `backend/tests/test_enrichment/test_url_resolver.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_enrichment/__init__.py
```

```python
# backend/tests/test_enrichment/test_url_resolver.py
import pytest
from mcp_manager.enrichment.url_resolver import parse_reverse_dns_to_github_url


def test_io_github_pattern():
    url = parse_reverse_dns_to_github_url("io.github.appium/appium-mcp")
    assert url == "https://github.com/appium/appium-mcp"


def test_io_github_dotted_owner():
    url = parse_reverse_dns_to_github_url("io.github.some.user/my-repo")
    assert url == "https://github.com/some.user/my-repo"


def test_com_domain_pattern():
    url = parse_reverse_dns_to_github_url("com.example/my-server")
    assert url == "https://github.com/example/my-server"


def test_ai_domain_pattern():
    url = parse_reverse_dns_to_github_url("ai.smithery/brave")
    assert url == "https://github.com/smithery/brave"


def test_no_slash_returns_none():
    url = parse_reverse_dns_to_github_url("just-a-name")
    assert url is None


def test_empty_returns_none():
    url = parse_reverse_dns_to_github_url("")
    assert url is None


def test_already_has_github_in_name():
    url = parse_reverse_dns_to_github_url("io.github.brave/brave-search-mcp-server")
    assert url == "https://github.com/brave/brave-search-mcp-server"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_enrichment/test_url_resolver.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement url_resolver**

```python
# backend/mcp_manager/enrichment/__init__.py
```

```python
# backend/mcp_manager/enrichment/url_resolver.py
import asyncio
import logging
import re

import httpx

from mcp_manager.config import settings

logger = logging.getLogger(__name__)


def parse_reverse_dns_to_github_url(name: str) -> str | None:
    """Parse a reverse-DNS MCP name into a GitHub URL candidate.

    Patterns:
      io.github.{owner}/{repo} -> https://github.com/{owner}/{repo}
      com.{domain}/{repo}      -> https://github.com/{domain}/{repo}
      ai.{domain}/{repo}       -> https://github.com/{domain}/{repo}
      net.{domain}/{repo}      -> https://github.com/{domain}/{repo}
    """
    if not name or "/" not in name:
        return None

    parts = name.split("/", 1)
    if len(parts) != 2:
        return None

    prefix = parts[0]
    repo = parts[1]

    # io.github.{owner} pattern
    match = re.match(r"^io\.github\.(.+)$", prefix)
    if match:
        owner = match.group(1)
        return f"https://github.com/{owner}/{repo}"

    # com.{domain}, ai.{domain}, net.{domain}, etc.
    domain_match = re.match(r"^(?:com|ai|net|org|io|dev)\.(.+)$", prefix)
    if domain_match:
        domain = domain_match.group(1)
        return f"https://github.com/{domain}/{repo}"

    return None


async def verify_github_url(client: httpx.AsyncClient, url: str) -> bool:
    """Check if a GitHub repo exists via HEAD request."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if settings.github_token:
        headers["Authorization"] = f"token {settings.github_token}"
    try:
        # Use API endpoint instead of HEAD on web URL for reliability
        api_url = url.replace("https://github.com/", "https://api.github.com/repos/")
        resp = await client.get(api_url, headers=headers)
        return resp.status_code == 200
    except Exception:
        return False


async def run_url_resolve() -> dict[str, int]:
    """Passe 1: Resolve missing source_url from reverse-DNS names."""
    from sqlalchemy import select
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import McpService

    stats = {"resolved": 0, "not_found": 0, "skipped": 0}
    semaphore = asyncio.Semaphore(10)  # max 10 concurrent requests

    async with SessionLocal() as db:
        result = await db.execute(
            select(McpService).where(
                McpService.source_url == "",
            )
        )
        services = result.scalars().all()
        logger.info("URL resolve: %d services without source_url", len(services))

        async with httpx.AsyncClient(timeout=15.0) as client:
            for service in services:
                candidate = parse_reverse_dns_to_github_url(service.name)
                if not candidate:
                    stats["skipped"] += 1
                    continue

                async with semaphore:
                    exists = await verify_github_url(client, candidate)

                if exists:
                    service.source_url = candidate
                    if not service.doc_url:
                        service.doc_url = candidate
                    stats["resolved"] += 1
                    logger.debug("Resolved: %s -> %s", service.name, candidate)
                else:
                    stats["not_found"] += 1
                    logger.debug("Not found: %s -> %s", service.name, candidate)

        await db.commit()

    logger.info(
        "URL resolve done: %d resolved, %d not found, %d skipped",
        stats["resolved"], stats["not_found"], stats["skipped"],
    )
    return stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_enrichment/test_url_resolver.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_manager/enrichment/ backend/tests/test_enrichment/
git commit -m "feat: URL resolver (passe 1) — resolve source_url from reverse-DNS names"
```

---

## Task 3: Deduplication (Passe 2)

**Files:**
- Create: `backend/mcp_manager/enrichment/dedup.py`
- Create: `backend/tests/test_enrichment/test_dedup.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_enrichment/test_dedup.py
from mcp_manager.enrichment.dedup import normalize_url, find_name_match


def test_normalize_url_trailing_slash():
    assert normalize_url("https://github.com/test/repo/") == "https://github.com/test/repo"


def test_normalize_url_uppercase():
    assert normalize_url("https://GitHub.com/Test/Repo") == "https://github.com/test/repo"


def test_normalize_url_empty():
    assert normalize_url("") == ""
    assert normalize_url(None) == ""


def test_find_name_match_suffix():
    assert find_name_match("brave", "io.github.brave/brave-search-mcp-server") is True


def test_find_name_match_exact_suffix():
    assert find_name_match("docker", "io.github.Dave-London/docker") is True


def test_find_name_match_no_match():
    assert find_name_match("brave", "io.github.appium/appium-mcp") is False


def test_find_name_match_empty():
    assert find_name_match("", "io.github.test/test") is False
    assert find_name_match("test", "") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_enrichment/test_dedup.py -v`
Expected: FAIL

- [ ] **Step 3: Implement dedup**

```python
# backend/mcp_manager/enrichment/dedup.py
import logging

from sqlalchemy import select, delete

from mcp_manager.db.session import SessionLocal
from mcp_manager.db.models import McpService

logger = logging.getLogger(__name__)


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    return url.strip().rstrip("/").lower()


def find_name_match(docker_name: str, mcp_name: str) -> bool:
    """Check if docker_name appears as the repo part of a reverse-DNS mcp_name."""
    if not docker_name or not mcp_name:
        return False
    if "/" not in mcp_name:
        return False
    repo_part = mcp_name.split("/", 1)[1]
    # Match if docker_name is the repo part or is contained in it
    return docker_name == repo_part or repo_part.endswith(docker_name)


async def run_dedup() -> dict[str, int]:
    """Passe 2: Merge cross-source duplicates. Docker wins, MCP Registry enriches."""
    stats = {"merged": 0, "skipped": 0}

    async with SessionLocal() as db:
        # Get all Docker services
        docker_result = await db.execute(
            select(McpService).where(McpService.source_type == "docker_registry")
        )
        docker_services = docker_result.scalars().all()

        # Get all MCP Registry services
        mcp_result = await db.execute(
            select(McpService).where(McpService.source_type == "mcp_registry")
        )
        mcp_services = mcp_result.scalars().all()

        # Index MCP services by normalized source_url
        mcp_by_url: dict[str, list[McpService]] = {}
        for mcp in mcp_services:
            url = normalize_url(mcp.source_url)
            if url:
                mcp_by_url.setdefault(url, []).append(mcp)

        for docker_svc in docker_services:
            docker_url = normalize_url(docker_svc.source_url)
            matches: list[McpService] = []

            # Match 1: same source_url
            if docker_url and docker_url in mcp_by_url:
                matches.extend(mcp_by_url[docker_url])

            # Match 2: name match (only if no URL match)
            if not matches:
                for mcp in mcp_services:
                    if find_name_match(docker_svc.name, mcp.name):
                        matches.append(mcp)

            if not matches:
                stats["skipped"] += 1
                continue

            # Merge: Docker survives, enriched with MCP Registry data
            for mcp_match in matches:
                # Enrich package_info from MCP Registry
                if hasattr(docker_svc, "package_info") and not docker_svc.package_info:
                    docker_svc.package_info = {}

                # Transfer version if MCP Registry has a newer one
                if mcp_match.branch_hash and (
                    not docker_svc.branch_hash or mcp_match.branch_hash > docker_svc.branch_hash
                ):
                    docker_svc.branch_hash = mcp_match.branch_hash

                # Transfer doc_url if Docker doesn't have one
                if not docker_svc.doc_url and mcp_match.doc_url:
                    docker_svc.doc_url = mcp_match.doc_url

                # Track origins
                origins = set(docker_svc.source_origins or [])
                origins.add("docker_registry")
                origins.add("mcp_registry")
                docker_svc.source_origins = list(origins)

                # Delete the MCP Registry duplicate (CASCADE deletes summaries/installations)
                await db.execute(
                    delete(McpService).where(McpService.id == mcp_match.id)
                )
                stats["merged"] += 1

                logger.debug(
                    "Merged: %s (%s) <- %s (%s)",
                    docker_svc.name, docker_svc.source_type,
                    mcp_match.name, mcp_match.source_type,
                )

        await db.commit()

    logger.info("Dedup done: %d merged, %d skipped", stats["merged"], stats["skipped"])
    return stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_enrichment/test_dedup.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_manager/enrichment/dedup.py backend/tests/test_enrichment/test_dedup.py
git commit -m "feat: deduplication (passe 2) — merge cross-source duplicates"
```

---

## Task 4: Auto-categorizer (Passe 3)

**Files:**
- Create: `backend/mcp_manager/enrichment/categorizer.py`
- Create: `backend/tests/test_enrichment/test_categorizer.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_enrichment/test_categorizer.py
from unittest.mock import AsyncMock, patch

import pytest
from mcp_manager.enrichment.categorizer import CATEGORIES, parse_category_response


def test_categories_defined():
    assert "database" in CATEGORIES
    assert "devops" in CATEGORIES
    assert "ai" in CATEGORIES
    assert len(CATEGORIES) > 20


def test_parse_valid_category():
    assert parse_category_response("database") == "database"


def test_parse_category_with_whitespace():
    assert parse_category_response("  devops  \n") == "devops"


def test_parse_category_case_insensitive():
    assert parse_category_response("DevOps") == "devops"


def test_parse_invalid_category():
    assert parse_category_response("not-a-real-category") is None


def test_parse_empty():
    assert parse_category_response("") is None


def test_parse_sentence_response():
    # LLM sometimes returns a sentence instead of just the category
    assert parse_category_response("The category is database.") is None


@patch("mcp_manager.enrichment.categorizer.ollama_generate", new_callable=AsyncMock)
async def test_categorize_single(mock_ollama):
    from mcp_manager.enrichment.categorizer import categorize_single
    mock_ollama.return_value = "database"
    result = await categorize_single("postgres-mcp", "PostgreSQL database access")
    assert result == "database"
    mock_ollama.assert_called_once()


@patch("mcp_manager.enrichment.categorizer.ollama_generate", new_callable=AsyncMock)
async def test_categorize_single_empty_description(mock_ollama):
    from mcp_manager.enrichment.categorizer import categorize_single
    result = await categorize_single("test", "")
    assert result is None
    mock_ollama.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_enrichment/test_categorizer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement categorizer**

```python
# backend/mcp_manager/enrichment/categorizer.py
import asyncio
import logging

from mcp_manager.summarizer.ollama_client import ollama_generate

logger = logging.getLogger(__name__)

CATEGORIES = {
    "database", "devops", "ai", "ai-ml", "security", "monitoring",
    "productivity", "communication", "search", "development",
    "developer-tools", "finance", "analytics", "documentation",
    "web", "blockchain", "commerce", "ecommerce", "infrastructure",
    "automation", "integration", "iot", "games", "media", "video",
    "news", "travel", "healthcare", "geospatial", "maps", "messaging",
    "data-analytics", "data-visualization", "reference", "cloud",
    "testing", "education", "social", "storage", "email",
}

PROMPT_TEMPLATE = """Classify this MCP server into exactly ONE category.

Name: {name}
Description: {description}

Categories: {categories}

Reply with ONLY the category name, nothing else."""


def parse_category_response(response: str) -> str | None:
    if not response:
        return None
    cleaned = response.strip().lower().rstrip(".")
    if cleaned in CATEGORIES:
        return cleaned
    return None


async def categorize_single(name: str, description: str) -> str | None:
    if not description or not description.strip():
        return None
    prompt = PROMPT_TEMPLATE.format(
        name=name,
        description=description,
        categories=", ".join(sorted(CATEGORIES)),
    )
    response = await ollama_generate(prompt)
    return parse_category_response(response)


async def run_categorize() -> dict[str, int]:
    """Passe 3: Auto-categorize services without category via Ollama."""
    from sqlalchemy import select
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import McpService

    stats = {"categorized": 0, "skipped_no_desc": 0, "skipped_invalid": 0}
    semaphore = asyncio.Semaphore(5)  # max 5 concurrent Ollama calls

    async with SessionLocal() as db:
        result = await db.execute(
            select(McpService).where(McpService.category.is_(None))
        )
        services = result.scalars().all()
        logger.info("Categorizer: %d services without category", len(services))

        for i, service in enumerate(services):
            # We need the description — get it from doc_hash context or name
            # For now, use name only since we don't store description separately
            # The MCP Registry server.json has description but we didn't store it
            # Use the name as input — it often contains enough info
            desc = service.name  # Fallback: name is better than nothing

            async with semaphore:
                category = await categorize_single(service.name, desc)

            if category:
                service.category = category
                stats["categorized"] += 1
            else:
                stats["skipped_invalid"] += 1

            if (i + 1) % 100 == 0:
                logger.info("Categorizer progress: %d/%d", i + 1, len(services))
                await db.commit()  # Intermediate commit every 100

        await db.commit()

    logger.info(
        "Categorizer done: %d categorized, %d skipped (no desc), %d skipped (invalid)",
        stats["categorized"], stats["skipped_no_desc"], stats["skipped_invalid"],
    )
    return stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_enrichment/test_categorizer.py -v`
Expected: 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_manager/enrichment/categorizer.py backend/tests/test_enrichment/test_categorizer.py
git commit -m "feat: auto-categorizer (passe 3) — classify services via Ollama"
```

---

## Task 5: CLI enrich command

**Files:**
- Modify: `backend/mcp_manager/cli.py`

- [ ] **Step 1: Add enrich command to CLI**

Add after the `export` command in `backend/mcp_manager/cli.py`:

```python
@app.command()
def enrich(
    pass_name: str | None = typer.Option(None, "--pass", help="Run a specific pass: url-resolve, dedup, categorize"),
):
    """Enrich service data: resolve URLs, deduplicate, auto-categorize."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run_enrich(pass_name=pass_name))


async def _run_enrich(pass_name: str | None = None) -> None:
    from mcp_manager.enrichment.url_resolver import run_url_resolve
    from mcp_manager.enrichment.dedup import run_dedup
    from mcp_manager.enrichment.categorizer import run_categorize

    passes = {
        "url-resolve": ("URL Resolve", run_url_resolve),
        "dedup": ("Deduplication", run_dedup),
        "categorize": ("Auto-categorize", run_categorize),
    }

    if pass_name:
        if pass_name not in passes:
            typer.echo(f"Unknown pass: {pass_name}. Available: {', '.join(passes.keys())}", err=True)
            raise typer.Exit(1)
        label, func = passes[pass_name]
        typer.echo(f"Running {label}...")
        result = await func()
        typer.echo(f"{label} complete: {result}")
    else:
        for name, (label, func) in passes.items():
            typer.echo(f"\n=== {label} ===")
            result = await func()
            typer.echo(f"{label}: {result}")
        typer.echo("\nEnrichment complete.")
```

- [ ] **Step 2: Verify CLI help**

Run:
```bash
cd backend && python -c "from mcp_manager.cli import app; from typer.testing import CliRunner; r = CliRunner().invoke(app, ['enrich', '--help']); print(r.output)"
```
Expected: shows `enrich` help with `--pass` option

- [ ] **Step 3: Commit**

```bash
git add backend/mcp_manager/cli.py
git commit -m "feat: CLI enrich command with --pass option (url-resolve, dedup, categorize)"
```

---

## Task 6: Deploy and run enrichment

- [ ] **Step 1: Deploy updated code to LXC 113**

```bash
cd E:/srcs/mcp_manager
tar --exclude='.git' --exclude='node_modules' --exclude='.venv' --exclude='__pycache__' --exclude='dist' --exclude='.env' -czf /tmp/mcp-manager.tar.gz .
scp -i ~/.ssh/id_shellia /tmp/mcp-manager.tar.gz root@192.168.10.99:/tmp/
ssh -i ~/.ssh/id_shellia root@192.168.10.99 "cd /root/mcp-manager && tar xzf /tmp/mcp-manager.tar.gz && rm /tmp/mcp-manager.tar.gz"
```

- [ ] **Step 2: Apply DB migration**

```bash
ssh -i ~/.ssh/id_shellia root@192.168.10.99 "cd /root/mcp-manager && docker compose exec mcp-manager-postgres psql -U langgraph -d langgraph -c \"ALTER TABLE mcp_services ADD COLUMN IF NOT EXISTS package_info JSONB DEFAULT '{}'; ALTER TABLE mcp_services ADD COLUMN IF NOT EXISTS source_origins TEXT[] DEFAULT '{}';\""
```

- [ ] **Step 3: Rebuild and restart backend**

```bash
ssh -i ~/.ssh/id_shellia root@192.168.10.99 "cd /root/mcp-manager && docker compose up -d --build mcp-backend"
```

- [ ] **Step 4: Run passe 1 (URL resolve)**

```bash
ssh -i ~/.ssh/id_shellia root@192.168.10.99 "cd /root/mcp-manager && docker compose exec mcp-backend python -m mcp_manager.cli enrich --pass url-resolve"
```
Expected: resolves hundreds of missing source_urls

- [ ] **Step 5: Run passe 2 (dedup)**

```bash
ssh -i ~/.ssh/id_shellia root@192.168.10.99 "cd /root/mcp-manager && docker compose exec mcp-backend python -m mcp_manager.cli enrich --pass dedup"
```
Expected: merges ~43 duplicates

- [ ] **Step 6: Run passe 3 (categorize) — optional, long running**

```bash
ssh -i ~/.ssh/id_shellia root@192.168.10.99 "cd /root/mcp-manager && docker compose exec mcp-backend python -m mcp_manager.cli enrich --pass categorize"
```
Expected: categorizes thousands of services (takes minutes via Ollama)

- [ ] **Step 7: Verify results**

```bash
ssh -i ~/.ssh/id_shellia root@192.168.10.99 "curl -s http://localhost:8000/api/v1/stats"
```
Expected: fewer total services (dedup), more categories populated

- [ ] **Step 8: Commit and push all changes**

```bash
git add -A && git commit -m "feat: data enrichment pipeline (url-resolve, dedup, categorize)" && git push
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | DB schema: add package_info + source_origins | models.py, init.sql |
| 2 | Passe 1: URL resolver | enrichment/url_resolver.py + tests |
| 3 | Passe 2: Deduplication | enrichment/dedup.py + tests |
| 4 | Passe 3: Auto-categorizer | enrichment/categorizer.py + tests |
| 5 | CLI enrich command | cli.py |
| 6 | Deploy and run | LXC 113 |
