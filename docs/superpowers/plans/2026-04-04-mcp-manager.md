# MCP Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a platform that automatically discovers MCP servers from multiple sources, normalizes them into a PostgreSQL referential, generates AI summaries in en/fr, and produces installation recipes for multiple targets — exposed via FastAPI + React dashboard.

**Architecture:** Python backend (FastAPI + Typer CLI) with extensible connectors for source ingestion, Ollama for AI summaries, SQLAlchemy/Alembic for PostgreSQL, and a separate React/TypeScript frontend. GitHub Actions cron triggers periodic sync.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, Typer, httpx, Ollama API, PostgreSQL 16 (pgvector image), React 18, TypeScript, Vite, TanStack Query, Tailwind CSS, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-04-04-mcp-manager-design.md`

---

## File Structure

### Backend (`backend/`)

```
backend/
  pyproject.toml
  alembic.ini
  mcp_manager/
    __init__.py
    config.py                         # Pydantic Settings (DATABASE_URL, OLLAMA_*, etc.)
    cli.py                            # Typer CLI entrypoint
    db/
      __init__.py
      session.py                      # Engine, SessionLocal, get_db dependency
      models.py                       # SQLAlchemy ORM models (4 tables)
    connectors/
      __init__.py
      base.py                         # AbstractConnector + RawMcpService dataclass
      mcp_registry.py                 # Official MCP Registry connector
      docker_registry.py              # Docker MCP Registry connector
      registry.py                     # Connector discovery/registry
    summarizer/
      __init__.py
      ollama_client.py                # Ollama HTTP client
      summarizer.py                   # Summarization pipeline
      cleaner.py                      # Markdown cleanup (badges, images, etc.)
    exporters/
      __init__.py
      base.py                         # AbstractExporter
      claude_code.py                  # Claude Code exporter
      langgraph.py                    # LangGraph mcp_servers.json exporter
      docker_stdio.py                 # Docker stdio exporter
      engine.py                       # Rule engine mapping registryType+transport -> recipe
    api/
      __init__.py
      app.py                          # FastAPI app factory
      deps.py                         # Shared dependencies (get_db, etc.)
      routers/
        __init__.py
        services.py                   # /services endpoints
        summaries.py                  # /summaries endpoints
        installations.py              # /installations endpoints
        targets.py                    # /targets endpoints
        sync.py                       # /sync endpoints
        stats.py                      # /stats endpoint
    migrations/
      env.py                          # Alembic env
      versions/                       # Migration files
  scripts/
    init.sql                          # Initial schema (mounted in Docker)
  tests/
    __init__.py
    conftest.py                       # Fixtures: test DB, test client, factories
    test_models.py
    test_connectors/
      __init__.py
      test_docker_registry.py
      test_mcp_registry.py
    test_summarizer/
      __init__.py
      test_cleaner.py
      test_summarizer.py
    test_exporters/
      __init__.py
      test_claude_code.py
      test_langgraph.py
      test_docker_stdio.py
      test_engine.py
    test_api/
      __init__.py
      test_services.py
      test_summaries.py
      test_installations.py
      test_targets.py
      test_sync.py
      test_stats.py
    test_cli.py
```

### Frontend (`frontend/`)

```
frontend/
  package.json
  tsconfig.json
  vite.config.ts
  tailwind.config.ts
  index.html
  src/
    main.tsx
    App.tsx
    types/
      index.ts                        # All API types
    api/
      client.ts                       # Typed fetch wrapper
      services.ts                     # Service API hooks
      summaries.ts                    # Summary API hooks
      installations.ts               # Installation API hooks
      targets.ts                     # Target API hooks
      sync.ts                        # Sync API hooks
      stats.ts                       # Stats API hooks
    components/
      ui/
        Button.tsx
        Badge.tsx
        Card.tsx
        DataTable.tsx
        SearchInput.tsx
        Modal.tsx
        Tabs.tsx
        StatusBadge.tsx
      domain/
        ServiceCard.tsx
        SummaryView.tsx
        InstallCommand.tsx
        SyncStatusBar.tsx
        FilterPanel.tsx
    pages/
      DashboardPage.tsx
      ServicesPage.tsx
      ServiceDetailPage.tsx
      TargetsPage.tsx
      SyncPage.tsx
    layouts/
      MainLayout.tsx
```

### Root

```
docker-compose.yml                    # PostgreSQL + backend + frontend
env.example                           # Updated with new vars
.github/workflows/sync.yml            # Cron sync
scripts/Infra/                        # Existing LXC scripts (untouched)
```

---

## Phase 1: Database Foundation

### Task 1: Backend project scaffold

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/mcp_manager/__init__.py`
- Create: `backend/mcp_manager/config.py`

- [ ] **Step 1: Create backend/pyproject.toml**

```toml
[project]
name = "mcp-manager"
version = "0.1.0"
description = "MCP Server Reference Manager"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic-settings>=2.6.0",
    "typer>=0.15.0",
    "httpx>=0.28.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.25.0",
    "httpx>=0.28.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.mypy]
python_version = "3.11"
strict = true
```

- [ ] **Step 2: Create config module**

```python
# backend/mcp_manager/__init__.py
```

```python
# backend/mcp_manager/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://langgraph:langgraph@localhost:5432/langgraph"
    ollama_base_url: str = "http://192.168.10.80:11434"
    ollama_summary_model: str = "llama3.1"
    cors_origins: list[str] = ["http://localhost:3001"]
    github_token: str = ""

    model_config = {"env_prefix": "", "env_file": ".env"}


settings = Settings()
```

- [ ] **Step 3: Install dependencies and verify**

Run:
```bash
cd backend && pip install -e ".[dev]"
python -c "from mcp_manager.config import settings; print(settings.database_url)"
```
Expected: prints the default DATABASE_URL

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/mcp_manager/__init__.py backend/mcp_manager/config.py
git commit -m "feat: backend project scaffold with config"
```

---

### Task 2: SQLAlchemy models

**Files:**
- Create: `backend/mcp_manager/db/__init__.py`
- Create: `backend/mcp_manager/db/session.py`
- Create: `backend/mcp_manager/db/models.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: Write the test for models**

```python
# backend/tests/__init__.py
```

```python
# backend/tests/conftest.py
import asyncio
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mcp_manager.config import settings
from mcp_manager.db.models import Base


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db(engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
```

```python
# backend/tests/test_models.py
import uuid

from sqlalchemy import select

from mcp_manager.db.models import InstallTarget, McpInstallation, McpService, McpSummary


async def test_create_mcp_service(db):
    service = McpService(
        name="test-server",
        source_url="https://github.com/test/test-mcp",
        source_type="docker_registry",
        transport="stdio",
    )
    db.add(service)
    await db.flush()

    result = await db.execute(select(McpService).where(McpService.name == "test-server"))
    row = result.scalar_one()
    assert row.name == "test-server"
    assert row.source_type == "docker_registry"
    assert row.is_deprecated is False
    assert isinstance(row.id, uuid.UUID)


async def test_create_summary_linked_to_service(db):
    service = McpService(
        name="summary-test",
        source_url="https://github.com/test/test",
        source_type="mcp_registry",
    )
    db.add(service)
    await db.flush()

    summary = McpSummary(
        mcp_service_id=service.id,
        culture="fr",
        summary="Un serveur MCP de test.",
        source_hash="abc123",
    )
    db.add(summary)
    await db.flush()

    result = await db.execute(
        select(McpSummary).where(McpSummary.mcp_service_id == service.id)
    )
    row = result.scalar_one()
    assert row.culture == "fr"
    assert row.summary == "Un serveur MCP de test."


async def test_create_installation_with_target(db):
    service = McpService(
        name="install-test",
        source_url="https://github.com/test/test",
        source_type="docker_registry",
    )
    target = InstallTarget(name="claude_code_test", description="Test target")
    db.add_all([service, target])
    await db.flush()

    install = McpInstallation(
        mcp_service_id=service.id,
        install_target_id=target.id,
        action_type="cmd",
        data="claude mcp add test -- npx @test/mcp@latest",
        env_vars={"TEST_KEY": "test_value"},
    )
    db.add(install)
    await db.flush()

    result = await db.execute(
        select(McpInstallation).where(McpInstallation.mcp_service_id == service.id)
    )
    row = result.scalar_one()
    assert row.action_type == "cmd"
    assert row.env_vars == {"TEST_KEY": "test_value"}


async def test_unique_constraint_source_type_name(db):
    import sqlalchemy

    s1 = McpService(name="dup-test", source_url="https://a.com", source_type="docker_registry")
    s2 = McpService(name="dup-test", source_url="https://b.com", source_type="docker_registry")
    db.add(s1)
    await db.flush()
    db.add(s2)
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await db.flush()


import pytest
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_manager.db'`

- [ ] **Step 3: Implement models and session**

```python
# backend/mcp_manager/db/__init__.py
```

```python
# backend/mcp_manager/db/session.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mcp_manager.config import settings

engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
```

```python
# backend/mcp_manager/db/models.py
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class McpService(Base):
    __tablename__ = "mcp_services"
    __table_args__ = (
        UniqueConstraint("source_type", "name", name="uq_source_type_name"),
        Index("idx_services_source_type", "source_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    doc_url: Mapped[str | None] = mapped_column(Text)
    doc_hash: Mapped[str | None] = mapped_column(String(64))
    branch_hash: Mapped[str | None] = mapped_column(String(64))
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    transport: Mapped[str | None] = mapped_column(String(20))
    category: Mapped[str | None] = mapped_column(String(100))
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    summaries: Mapped[list["McpSummary"]] = relationship(back_populates="service", cascade="all, delete-orphan")
    installations: Mapped[list["McpInstallation"]] = relationship(back_populates="service", cascade="all, delete-orphan")


class McpSummary(Base):
    __tablename__ = "mcp_summaries"
    __table_args__ = (
        UniqueConstraint("mcp_service_id", "culture", name="uq_service_culture"),
        Index("idx_summaries_culture", "culture"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mcp_service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mcp_services.id", ondelete="CASCADE"), nullable=False
    )
    culture: Mapped[str] = mapped_column(String(5), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    service: Mapped["McpService"] = relationship(back_populates="summaries")


class InstallTarget(Base):
    __tablename__ = "install_targets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    installations: Mapped[list["McpInstallation"]] = relationship(back_populates="target", cascade="all, delete-orphan")


class McpInstallation(Base):
    __tablename__ = "mcp_installations"
    __table_args__ = (
        UniqueConstraint("mcp_service_id", "install_target_id", name="uq_service_target"),
        Index("idx_installations_target", "install_target_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mcp_service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mcp_services.id", ondelete="CASCADE"), nullable=False
    )
    install_target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("install_targets.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[str] = mapped_column(Text, nullable=False)
    env_vars: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    service: Mapped["McpService"] = relationship(back_populates="installations")
    target: Mapped["InstallTarget"] = relationship(back_populates="installations")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_manager/db/ backend/tests/
git commit -m "feat: SQLAlchemy models for 4 tables (services, summaries, targets, installations)"
```

---

### Task 3: Alembic migrations + init.sql

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/mcp_manager/migrations/env.py`
- Create: `backend/scripts/init.sql`

- [ ] **Step 1: Initialize Alembic**

Run:
```bash
cd backend && alembic init mcp_manager/migrations
```

- [ ] **Step 2: Configure alembic.ini**

Replace the generated `alembic.ini` content:

```ini
[alembic]
script_location = mcp_manager/migrations
sqlalchemy.url = postgresql+asyncpg://langgraph:langgraph@localhost:5432/langgraph

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3: Update migrations/env.py for async**

```python
# backend/mcp_manager/migrations/env.py
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from mcp_manager.config import settings
from mcp_manager.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.database_url
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 4: Generate initial migration**

Run:
```bash
cd backend && alembic revision --autogenerate -m "initial schema"
```
Expected: migration file created in `mcp_manager/migrations/versions/`

- [ ] **Step 5: Create init.sql for Docker entrypoint**

```sql
-- backend/scripts/init.sql
-- Initial schema for mcp-manager
-- Mounted in docker-entrypoint-initdb.d for fresh installs
-- For existing DBs, use Alembic migrations instead

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS mcp_services (
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
    CONSTRAINT uq_source_type_name UNIQUE (source_type, name)
);

CREATE TABLE IF NOT EXISTS mcp_summaries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mcp_service_id  UUID NOT NULL REFERENCES mcp_services(id) ON DELETE CASCADE,
    culture         VARCHAR(5) NOT NULL,
    summary         TEXT NOT NULL,
    source_hash     VARCHAR(64),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_service_culture UNIQUE (mcp_service_id, culture)
);

CREATE TABLE IF NOT EXISTS install_targets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mcp_installations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mcp_service_id  UUID NOT NULL REFERENCES mcp_services(id) ON DELETE CASCADE,
    install_target_id UUID NOT NULL REFERENCES install_targets(id) ON DELETE CASCADE,
    action_type     VARCHAR(50) NOT NULL,
    data            TEXT NOT NULL,
    env_vars        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_service_target UNIQUE (mcp_service_id, install_target_id)
);

CREATE INDEX IF NOT EXISTS idx_services_source_type ON mcp_services(source_type);
CREATE INDEX IF NOT EXISTS idx_summaries_culture ON mcp_summaries(culture);
CREATE INDEX IF NOT EXISTS idx_installations_target ON mcp_installations(install_target_id);

-- Seed install targets
INSERT INTO install_targets (name, description) VALUES
    ('claude_code', 'Claude Code CLI')
ON CONFLICT (name) DO NOTHING;

INSERT INTO install_targets (name, description) VALUES
    ('langgraph', 'LangGraph mcp_servers.json')
ON CONFLICT (name) DO NOTHING;

INSERT INTO install_targets (name, description) VALUES
    ('docker_stdio', 'Docker container avec transport stdio')
ON CONFLICT (name) DO NOTHING;

INSERT INTO install_targets (name, description) VALUES
    ('claude_desktop', 'Claude Desktop app config')
ON CONFLICT (name) DO NOTHING;
```

- [ ] **Step 6: Commit**

```bash
git add backend/alembic.ini backend/mcp_manager/migrations/ backend/scripts/init.sql
git commit -m "feat: Alembic migrations + init.sql with seed data"
```

---

## Phase 2: Connectors

### Task 4: Connector base + RawMcpService dataclass

**Files:**
- Create: `backend/mcp_manager/connectors/__init__.py`
- Create: `backend/mcp_manager/connectors/base.py`
- Create: `backend/mcp_manager/connectors/registry.py`

- [ ] **Step 1: Write base connector interface**

```python
# backend/mcp_manager/connectors/__init__.py
```

```python
# backend/mcp_manager/connectors/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RawMcpService:
    name: str
    source_url: str
    source_type: str
    doc_url: str | None = None
    doc_hash: str | None = None
    branch_hash: str | None = None
    transport: str | None = None
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    is_deprecated: bool = False
    # Raw package info for exporters
    registry_type: str | None = None  # npm, pypi, oci
    package_identifier: str | None = None  # @playwright/mcp
    runtime_hint: str | None = None  # npx, uvx, docker
    env_vars: dict[str, str] = field(default_factory=dict)


class AbstractConnector(ABC):
    @abstractmethod
    async def fetch_services(self) -> list[RawMcpService]:
        """Fetch all MCP services from this source."""
        ...

    @abstractmethod
    async def fetch_doc_content(self, service: RawMcpService) -> str | None:
        """Fetch the documentation content (README.md) for a service."""
        ...

    @abstractmethod
    def source_type(self) -> str:
        """Unique identifier for this source type."""
        ...
```

```python
# backend/mcp_manager/connectors/registry.py
from mcp_manager.connectors.base import AbstractConnector

_connectors: dict[str, type[AbstractConnector]] = {}


def register_connector(cls: type[AbstractConnector]) -> type[AbstractConnector]:
    instance = cls.__new__(cls)
    _connectors[instance.source_type()] = cls
    return cls


def get_all_connectors() -> list[AbstractConnector]:
    return [cls() for cls in _connectors.values()]


def get_connector(source_type: str) -> AbstractConnector | None:
    cls = _connectors.get(source_type)
    return cls() if cls else None
```

- [ ] **Step 2: Commit**

```bash
git add backend/mcp_manager/connectors/
git commit -m "feat: connector base interface + registry"
```

---

### Task 5: Docker Registry connector

**Files:**
- Create: `backend/mcp_manager/connectors/docker_registry.py`
- Create: `backend/tests/test_connectors/__init__.py`
- Create: `backend/tests/test_connectors/test_docker_registry.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_connectors/__init__.py
```

```python
# backend/tests/test_connectors/test_docker_registry.py
import pytest

from mcp_manager.connectors.docker_registry import DockerRegistryConnector


@pytest.fixture
def connector():
    return DockerRegistryConnector()


def test_source_type(connector):
    assert connector.source_type() == "docker_registry"


async def test_parse_server_yaml(connector):
    yaml_content = """
name: playwright
type: server
title: Playwright MCP Server
description: Browser automation and web scraping
image: mcp/playwright:latest
meta:
  category: Development
  tags:
    - browser
    - testing
source:
  project: https://github.com/playwright/playwright-mcp
  commit: abc123
"""
    service = connector._parse_server_yaml("playwright", yaml_content)
    assert service.name == "playwright"
    assert service.source_type == "docker_registry"
    assert service.category == "Development"
    assert "browser" in service.tags
    assert "testing" in service.tags
    assert service.source_url == "https://github.com/playwright/playwright-mcp"


async def test_parse_server_yaml_remote_type(connector):
    yaml_content = """
name: cloudflare-docs
type: remote
title: Cloudflare Docs
description: Access Cloudflare documentation
remote:
  transport_type: sse
  url: https://docs.mcp.cloudflare.com/sse
"""
    service = connector._parse_server_yaml("cloudflare-docs", yaml_content)
    assert service.name == "cloudflare-docs"
    assert service.transport == "sse"


async def test_parse_server_yaml_missing_source(connector):
    yaml_content = """
name: minimal
type: server
title: Minimal Server
description: A minimal server
"""
    service = connector._parse_server_yaml("minimal", yaml_content)
    assert service.name == "minimal"
    assert service.source_url == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_connectors/test_docker_registry.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Docker Registry connector**

```python
# backend/mcp_manager/connectors/docker_registry.py
import hashlib
import logging

import httpx
import yaml

from mcp_manager.connectors.base import AbstractConnector, RawMcpService
from mcp_manager.connectors.registry import register_connector
from mcp_manager.config import settings

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
REPO_OWNER = "docker"
REPO_NAME = "mcp-registry"
SERVERS_PATH = "mcp-servers"


@register_connector
class DockerRegistryConnector(AbstractConnector):
    def source_type(self) -> str:
        return "docker_registry"

    def _github_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if settings.github_token:
            headers["Authorization"] = f"token {settings.github_token}"
        return headers

    async def fetch_services(self) -> list[RawMcpService]:
        services: list[RawMcpService] = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            # List all directories under mcp-servers/
            url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{SERVERS_PATH}"
            resp = await client.get(url, headers=self._github_headers())
            resp.raise_for_status()
            entries = resp.json()

            for entry in entries:
                if entry.get("type") != "dir":
                    continue
                server_name = entry["name"]
                try:
                    service = await self._fetch_server(client, server_name)
                    if service:
                        services.append(service)
                except Exception:
                    logger.exception("Failed to fetch server %s", server_name)

        logger.info("Docker registry: fetched %d services", len(services))
        return services

    async def _fetch_server(
        self, client: httpx.AsyncClient, server_name: str
    ) -> RawMcpService | None:
        url = (
            f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}"
            f"/main/{SERVERS_PATH}/{server_name}/server.yaml"
        )
        resp = await client.get(url, headers=self._github_headers())
        if resp.status_code != 200:
            return None
        yaml_content = resp.text
        service = self._parse_server_yaml(server_name, yaml_content)
        service.doc_hash = hashlib.sha256(yaml_content.encode()).hexdigest()
        return service

    def _parse_server_yaml(self, server_name: str, yaml_content: str) -> RawMcpService:
        data = yaml.safe_load(yaml_content) or {}
        meta = data.get("meta", {})
        source = data.get("source", {})
        remote = data.get("remote", {})

        transport = "stdio"
        if data.get("type") == "remote":
            transport = remote.get("transport_type", "sse")

        return RawMcpService(
            name=data.get("name", server_name),
            source_url=source.get("project", ""),
            source_type="docker_registry",
            doc_url=data.get("readme") or data.get("upstream") or source.get("project"),
            transport=transport,
            category=meta.get("category"),
            tags=meta.get("tags", []),
            branch_hash=source.get("commit"),
        )

    async def fetch_doc_content(self, service: RawMcpService) -> str | None:
        if not service.doc_url:
            return None
        readme_url = service.doc_url.replace(
            "github.com", "raw.githubusercontent.com"
        ).replace("/tree/", "/") + "/README.md"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(readme_url, headers=self._github_headers())
            if resp.status_code == 200:
                return resp.text

        # Fallback: try root README
        if "/tree/" in (service.doc_url or ""):
            root_url = service.doc_url.rsplit("/tree/", 1)[0]
            root_readme = root_url.replace(
                "github.com", "raw.githubusercontent.com"
            ) + "/main/README.md"
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(root_readme, headers=self._github_headers())
                if resp.status_code == 200:
                    return resp.text

        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_connectors/test_docker_registry.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_manager/connectors/docker_registry.py backend/tests/test_connectors/
git commit -m "feat: Docker Registry connector with YAML parsing"
```

---

### Task 6: Official MCP Registry connector

**Files:**
- Create: `backend/mcp_manager/connectors/mcp_registry.py`
- Create: `backend/tests/test_connectors/test_mcp_registry.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_connectors/test_mcp_registry.py
import pytest

from mcp_manager.connectors.mcp_registry import McpRegistryConnector


@pytest.fixture
def connector():
    return McpRegistryConnector()


def test_source_type(connector):
    assert connector.source_type() == "mcp_registry"


async def test_parse_server_json(connector):
    server_data = {
        "name": "io.github.domdomegg/airtable-mcp-server",
        "description": "Read and write access to Airtable",
        "version": "1.7.2",
        "websiteUrl": "https://github.com/domdomegg/airtable-mcp-server",
        "repository": {
            "url": "https://github.com/domdomegg/airtable-mcp-server",
            "source": "github",
            "subfolder": "packages/server",
        },
        "packages": [
            {
                "registryType": "npm",
                "identifier": "@domdomegg/airtable-mcp-server",
                "version": "1.7.2",
                "runtimeHint": "npx",
                "transport": {"type": "stdio"},
                "environmentVariables": [
                    {"name": "AIRTABLE_API_KEY", "isRequired": True, "isSecret": True}
                ],
            }
        ],
    }
    service = connector._parse_server_json(server_data)
    assert service.name == "io.github.domdomegg/airtable-mcp-server"
    assert service.transport == "stdio"
    assert service.registry_type == "npm"
    assert service.package_identifier == "@domdomegg/airtable-mcp-server"
    assert service.runtime_hint == "npx"
    assert "AIRTABLE_API_KEY" in service.env_vars


async def test_resolve_doc_url_with_subfolder(connector):
    service_data = {
        "name": "test",
        "description": "test",
        "version": "1.0.0",
        "repository": {
            "url": "https://github.com/microsoft/markitdown",
            "source": "github",
            "subfolder": "packages/markitdown-mcp",
        },
        "packages": [],
    }
    service = connector._parse_server_json(service_data)
    assert service.doc_url == "https://github.com/microsoft/markitdown/tree/main/packages/markitdown-mcp"


async def test_parse_remote_server(connector):
    server_data = {
        "name": "com.cloudflare/docs",
        "description": "Cloudflare documentation",
        "version": "1.0.0",
        "remotes": [
            {"type": "sse", "url": "https://docs.mcp.cloudflare.com/sse"}
        ],
    }
    service = connector._parse_server_json(server_data)
    assert service.transport == "sse"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_connectors/test_mcp_registry.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement MCP Registry connector**

```python
# backend/mcp_manager/connectors/mcp_registry.py
import hashlib
import json
import logging

import httpx

from mcp_manager.connectors.base import AbstractConnector, RawMcpService
from mcp_manager.connectors.registry import register_connector
from mcp_manager.config import settings

logger = logging.getLogger(__name__)

REGISTRY_API = "https://registry.modelcontextprotocol.io/v0.1"


@register_connector
class McpRegistryConnector(AbstractConnector):
    def source_type(self) -> str:
        return "mcp_registry"

    def _github_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if settings.github_token:
            headers["Authorization"] = f"token {settings.github_token}"
        return headers

    async def fetch_services(self) -> list[RawMcpService]:
        services: list[RawMcpService] = []
        cursor: str | None = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                params: dict[str, str] = {"limit": "96", "version": "latest"}
                if cursor:
                    params["cursor"] = cursor

                resp = await client.get(f"{REGISTRY_API}/servers", params=params)
                resp.raise_for_status()
                data = resp.json()

                servers = data.get("servers", [])
                if not servers:
                    break

                for server_data in servers:
                    try:
                        service = self._parse_server_json(server_data)
                        raw_json = json.dumps(server_data, sort_keys=True)
                        service.doc_hash = hashlib.sha256(raw_json.encode()).hexdigest()
                        services.append(service)
                    except Exception:
                        logger.exception(
                            "Failed to parse server %s", server_data.get("name", "unknown")
                        )

                cursor = data.get("metadata", {}).get("nextCursor")
                if not cursor:
                    break

        logger.info("MCP registry: fetched %d services", len(services))
        return services

    def _parse_server_json(self, data: dict) -> RawMcpService:
        name = data.get("name", "")
        description = data.get("description", "")
        version = data.get("version", "")
        repository = data.get("repository", {})

        # Resolve doc URL: subfolder in repo takes priority
        doc_url = data.get("websiteUrl") or repository.get("url")
        if repository.get("url") and repository.get("subfolder"):
            doc_url = f"{repository['url']}/tree/main/{repository['subfolder']}"

        # Extract first package info
        packages = data.get("packages", [])
        registry_type = None
        package_identifier = None
        runtime_hint = None
        transport = None
        env_vars: dict[str, str] = {}

        if packages:
            pkg = packages[0]
            registry_type = pkg.get("registryType")
            package_identifier = pkg.get("identifier")
            runtime_hint = pkg.get("runtimeHint")
            transport = pkg.get("transport", {}).get("type")
            for ev in pkg.get("environmentVariables", []):
                env_vars[ev["name"]] = ev.get("description", "")

        # Check remotes if no packages
        remotes = data.get("remotes", [])
        if not transport and remotes:
            transport = remotes[0].get("type")

        return RawMcpService(
            name=name,
            source_url=repository.get("url", ""),
            source_type="mcp_registry",
            doc_url=doc_url,
            branch_hash=version,
            transport=transport,
            registry_type=registry_type,
            package_identifier=package_identifier,
            runtime_hint=runtime_hint,
            env_vars=env_vars,
        )

    async def fetch_doc_content(self, service: RawMcpService) -> str | None:
        if not service.doc_url:
            return None

        # Try subfolder README first
        readme_url = self._resolve_raw_readme_url(service.doc_url)
        if readme_url:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(readme_url, headers=self._github_headers())
                if resp.status_code == 200:
                    return resp.text

        # Fallback: root README of the repo
        if service.source_url:
            root_readme = (
                service.source_url.replace("github.com", "raw.githubusercontent.com")
                + "/main/README.md"
            )
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(root_readme, headers=self._github_headers())
                if resp.status_code == 200:
                    return resp.text

        return None

    def _resolve_raw_readme_url(self, doc_url: str) -> str | None:
        if "github.com" not in doc_url:
            return None
        raw_url = doc_url.replace("github.com", "raw.githubusercontent.com").replace(
            "/tree/", "/"
        )
        return f"{raw_url}/README.md"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_connectors/test_mcp_registry.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_manager/connectors/mcp_registry.py backend/tests/test_connectors/test_mcp_registry.py
git commit -m "feat: Official MCP Registry connector with link resolution"
```

---

## Phase 3: Summarizer

### Task 7: Markdown cleaner

**Files:**
- Create: `backend/mcp_manager/summarizer/__init__.py`
- Create: `backend/mcp_manager/summarizer/cleaner.py`
- Create: `backend/tests/test_summarizer/__init__.py`
- Create: `backend/tests/test_summarizer/test_cleaner.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_summarizer/__init__.py
```

```python
# backend/tests/test_summarizer/test_cleaner.py
from mcp_manager.summarizer.cleaner import clean_markdown


def test_removes_badges():
    md = "# Server\n[![Build](https://img.shields.io/badge.svg)](url)\nContent here."
    result = clean_markdown(md)
    assert "img.shields.io" not in result
    assert "Content here." in result


def test_removes_image_lines():
    md = "# Server\n![screenshot](https://example.com/img.png)\nUseful text."
    result = clean_markdown(md)
    assert "screenshot" not in result
    assert "Useful text." in result


def test_removes_contributing_section():
    md = "# Server\nMain content.\n## Contributing\nPlease submit PRs.\n## License\nMIT"
    result = clean_markdown(md)
    assert "Main content." in result
    assert "Please submit PRs" not in result
    assert "MIT" not in result


def test_preserves_code_blocks():
    md = "# Usage\n```bash\nnpx @test/mcp\n```\nDone."
    result = clean_markdown(md)
    assert "npx @test/mcp" in result


def test_empty_input():
    assert clean_markdown("") == ""
    assert clean_markdown(None) == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_summarizer/test_cleaner.py -v`
Expected: FAIL

- [ ] **Step 3: Implement cleaner**

```python
# backend/mcp_manager/summarizer/__init__.py
```

```python
# backend/mcp_manager/summarizer/cleaner.py
import re

SKIP_SECTIONS = {"contributing", "contributors", "license", "changelog", "acknowledgements"}


def clean_markdown(content: str | None) -> str:
    if not content:
        return ""

    lines = content.split("\n")
    result: list[str] = []
    in_skip_section = False
    skip_level = 0
    in_code_block = False

    for line in lines:
        # Track code blocks — never skip content inside them
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
            continue

        if in_code_block:
            result.append(line)
            continue

        # Detect section headers
        header_match = re.match(r"^(#{1,6})\s+(.+)", line)
        if header_match:
            level = len(header_match.group(1))
            title = header_match.group(2).strip().lower()
            if title in SKIP_SECTIONS:
                in_skip_section = True
                skip_level = level
                continue
            if in_skip_section and level <= skip_level:
                in_skip_section = False

        if in_skip_section:
            continue

        # Remove badge images: [![...](img.shields.io/...)](...)
        if re.search(r"\[!\[.*?\]\(https?://img\.shields\.io", line):
            continue

        # Remove standalone images: ![alt](url)
        if re.match(r"^\s*!\[.*?\]\(.*?\)\s*$", line):
            continue

        result.append(line)

    return "\n".join(result).strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_summarizer/test_cleaner.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_manager/summarizer/ backend/tests/test_summarizer/
git commit -m "feat: markdown cleaner for doc preprocessing"
```

---

### Task 8: Ollama client + summarizer pipeline

**Files:**
- Create: `backend/mcp_manager/summarizer/ollama_client.py`
- Create: `backend/mcp_manager/summarizer/summarizer.py`
- Create: `backend/tests/test_summarizer/test_summarizer.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_summarizer/test_summarizer.py
from unittest.mock import AsyncMock, patch

import pytest

from mcp_manager.summarizer.summarizer import generate_summary, CULTURES


def test_cultures_defined():
    assert "en" in CULTURES
    assert "fr" in CULTURES


@patch("mcp_manager.summarizer.summarizer.ollama_generate")
async def test_generate_summary_calls_ollama(mock_ollama):
    mock_ollama.return_value = "This is a test MCP server that does testing."

    result = await generate_summary("# Test Server\nA server for tests.", "en")

    assert result == "This is a test MCP server that does testing."
    mock_ollama.assert_called_once()
    call_args = mock_ollama.call_args
    assert "en" in call_args[0][0].lower() or "english" in call_args[0][0].lower()


@patch("mcp_manager.summarizer.summarizer.ollama_generate")
async def test_generate_summary_french(mock_ollama):
    mock_ollama.return_value = "Un serveur MCP de test."

    result = await generate_summary("# Test Server\nA server for tests.", "fr")

    assert result == "Un serveur MCP de test."
    call_args = mock_ollama.call_args
    assert "fr" in call_args[0][0].lower() or "french" in call_args[0][0].lower()


async def test_generate_summary_empty_content():
    result = await generate_summary("", "en")
    assert result is None


async def test_generate_summary_none_content():
    result = await generate_summary(None, "en")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_summarizer/test_summarizer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Ollama client and summarizer**

```python
# backend/mcp_manager/summarizer/ollama_client.py
import logging

import httpx

from mcp_manager.config import settings

logger = logging.getLogger(__name__)


async def ollama_generate(prompt: str) -> str:
    url = f"{settings.ollama_base_url}/api/generate"
    payload = {
        "model": settings.ollama_summary_model,
        "prompt": prompt,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
```

```python
# backend/mcp_manager/summarizer/summarizer.py
import logging

from mcp_manager.summarizer.cleaner import clean_markdown
from mcp_manager.summarizer.ollama_client import ollama_generate

logger = logging.getLogger(__name__)

CULTURES = {
    "en": "English",
    "fr": "French",
}

PROMPT_TEMPLATE = """Summarize this MCP (Model Context Protocol) server documentation in {language}.

Include:
- What the server does
- Key tools/capabilities it exposes
- Prerequisites and requirements
- Typical use cases

Be concise: maximum 300 words. No marketing language. No badges or links.

Documentation:
---
{content}
---

Summary in {language}:"""


async def generate_summary(raw_content: str | None, culture: str) -> str | None:
    if not raw_content or not raw_content.strip():
        return None

    language = CULTURES.get(culture, culture)
    cleaned = clean_markdown(raw_content)

    if not cleaned:
        return None

    # Truncate to ~8000 chars to fit in context window
    if len(cleaned) > 8000:
        cleaned = cleaned[:8000] + "\n\n[truncated]"

    prompt = PROMPT_TEMPLATE.format(language=language, content=cleaned)
    result = await ollama_generate(prompt)
    return result if result else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_summarizer/test_summarizer.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_manager/summarizer/ollama_client.py backend/mcp_manager/summarizer/summarizer.py backend/tests/test_summarizer/test_summarizer.py
git commit -m "feat: Ollama summarizer pipeline with culture support"
```

---

## Phase 4: Exporters

### Task 9: Exporter base + rule engine

**Files:**
- Create: `backend/mcp_manager/exporters/__init__.py`
- Create: `backend/mcp_manager/exporters/base.py`
- Create: `backend/mcp_manager/exporters/engine.py`
- Create: `backend/tests/test_exporters/__init__.py`
- Create: `backend/tests/test_exporters/test_engine.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_exporters/__init__.py
```

```python
# backend/tests/test_exporters/test_engine.py
from mcp_manager.exporters.engine import generate_installation_data


def test_npm_stdio_claude_code():
    result = generate_installation_data(
        registry_type="npm",
        package_identifier="@playwright/mcp",
        runtime_hint="npx",
        transport="stdio",
        target_name="claude_code",
        service_name="playwright",
        env_vars={"PLAYWRIGHT_HEADLESS": "Run in headless mode"},
    )
    assert result["action_type"] == "cmd"
    assert "claude mcp add" in result["data"]
    assert "@playwright/mcp" in result["data"]


def test_npm_stdio_langgraph():
    result = generate_installation_data(
        registry_type="npm",
        package_identifier="@playwright/mcp",
        runtime_hint="npx",
        transport="stdio",
        target_name="langgraph",
        service_name="playwright",
        env_vars={},
    )
    assert result["action_type"] == "insert_in_file"
    assert '"command": "npx"' in result["data"]


def test_pypi_stdio_claude_code():
    result = generate_installation_data(
        registry_type="pypi",
        package_identifier="mcp-server-git",
        runtime_hint="uvx",
        transport="stdio",
        target_name="claude_code",
        service_name="git",
        env_vars={},
    )
    assert result["action_type"] == "cmd"
    assert "uvx" in result["data"]


def test_oci_docker_stdio():
    result = generate_installation_data(
        registry_type="oci",
        package_identifier="mcp/playwright:latest",
        runtime_hint="docker",
        transport="stdio",
        target_name="docker_stdio",
        service_name="playwright",
        env_vars={},
    )
    assert result["action_type"] == "docker_run"
    assert "docker run" in result["data"]


def test_unknown_target_returns_none():
    result = generate_installation_data(
        registry_type="npm",
        package_identifier="test",
        runtime_hint="npx",
        transport="stdio",
        target_name="unknown_target",
        service_name="test",
        env_vars={},
    )
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_exporters/test_engine.py -v`
Expected: FAIL

- [ ] **Step 3: Implement engine**

```python
# backend/mcp_manager/exporters/__init__.py
```

```python
# backend/mcp_manager/exporters/base.py
from abc import ABC, abstractmethod


class AbstractExporter(ABC):
    @abstractmethod
    def target_name(self) -> str: ...

    @abstractmethod
    def generate(
        self,
        service_name: str,
        registry_type: str | None,
        package_identifier: str | None,
        runtime_hint: str | None,
        transport: str | None,
        env_vars: dict[str, str],
    ) -> dict[str, str] | None:
        """Return {action_type, data} or None if unsupported."""
        ...
```

```python
# backend/mcp_manager/exporters/engine.py
import json


def generate_installation_data(
    registry_type: str | None,
    package_identifier: str | None,
    runtime_hint: str | None,
    transport: str | None,
    target_name: str,
    service_name: str,
    env_vars: dict[str, str],
) -> dict[str, str] | None:
    generators = {
        "claude_code": _gen_claude_code,
        "claude_desktop": _gen_claude_desktop,
        "langgraph": _gen_langgraph,
        "docker_stdio": _gen_docker_stdio,
    }
    gen = generators.get(target_name)
    if not gen:
        return None
    return gen(
        registry_type=registry_type,
        package_identifier=package_identifier,
        runtime_hint=runtime_hint,
        transport=transport,
        service_name=service_name,
        env_vars=env_vars,
    )


def _cmd_parts(runtime_hint: str | None, package_identifier: str | None) -> str:
    rh = runtime_hint or "npx"
    pkg = package_identifier or ""
    return f"{rh} {pkg}"


def _gen_claude_code(
    registry_type: str | None,
    package_identifier: str | None,
    runtime_hint: str | None,
    transport: str | None,
    service_name: str,
    env_vars: dict[str, str],
) -> dict[str, str]:
    cmd = _cmd_parts(runtime_hint, package_identifier)
    return {
        "action_type": "cmd",
        "data": f"claude mcp add {service_name} -- {cmd}",
    }


def _gen_claude_desktop(
    registry_type: str | None,
    package_identifier: str | None,
    runtime_hint: str | None,
    transport: str | None,
    service_name: str,
    env_vars: dict[str, str],
) -> dict[str, str]:
    rh = runtime_hint or "npx"
    pkg = package_identifier or ""
    args = ["-y", pkg] if rh == "npx" else [pkg]
    entry = {
        service_name: {
            "command": rh,
            "args": args,
        }
    }
    if env_vars:
        entry[service_name]["env"] = {k: f"${{{k}}}" for k in env_vars}
    return {
        "action_type": "insert_in_file",
        "data": json.dumps(entry, indent=2),
    }


def _gen_langgraph(
    registry_type: str | None,
    package_identifier: str | None,
    runtime_hint: str | None,
    transport: str | None,
    service_name: str,
    env_vars: dict[str, str],
) -> dict[str, str]:
    rh = runtime_hint or "npx"
    pkg = package_identifier or ""
    args = ["-y", pkg] if rh == "npx" else [pkg]
    entry = {
        "command": rh,
        "args": args,
        "transport": transport or "stdio",
        "env": {k: k for k in env_vars},
        "name": service_name,
        "enabled": True,
    }
    return {
        "action_type": "insert_in_file",
        "data": json.dumps(entry, indent=2),
    }


def _gen_docker_stdio(
    registry_type: str | None,
    package_identifier: str | None,
    runtime_hint: str | None,
    transport: str | None,
    service_name: str,
    env_vars: dict[str, str],
) -> dict[str, str]:
    image = package_identifier or f"mcp/{service_name}:latest"
    env_flags = " ".join(f"-e {k}" for k in env_vars)
    env_part = f" {env_flags}" if env_flags else ""
    return {
        "action_type": "docker_run",
        "data": f"docker run -i --rm{env_part} {image}",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_exporters/test_engine.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_manager/exporters/ backend/tests/test_exporters/
git commit -m "feat: export engine with rules for claude_code, langgraph, docker_stdio"
```

---

## Phase 5: API REST

### Task 10: FastAPI app + services router

**Files:**
- Create: `backend/mcp_manager/api/__init__.py`
- Create: `backend/mcp_manager/api/app.py`
- Create: `backend/mcp_manager/api/deps.py`
- Create: `backend/mcp_manager/api/routers/__init__.py`
- Create: `backend/mcp_manager/api/routers/services.py`
- Create: `backend/tests/test_api/__init__.py`
- Create: `backend/tests/test_api/test_services.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_api/__init__.py
```

```python
# backend/tests/test_api/test_services.py
import pytest
from httpx import ASGITransport, AsyncClient

from mcp_manager.api.app import create_app
from mcp_manager.db.models import Base, McpService


@pytest.fixture
async def app(engine):
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_list_services_empty(client):
    resp = await client.get("/api/v1/services")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)


async def test_list_services_with_data(client, db):
    service = McpService(
        name="test-api-service",
        source_url="https://github.com/test/test",
        source_type="docker_registry",
        transport="stdio",
    )
    db.add(service)
    await db.commit()

    resp = await client.get("/api/v1/services")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) >= 1
    assert data["items"][0]["name"] == "test-api-service"


async def test_get_service_by_id(client, db):
    service = McpService(
        name="detail-test",
        source_url="https://github.com/test/detail",
        source_type="mcp_registry",
    )
    db.add(service)
    await db.commit()

    resp = await client.get(f"/api/v1/services/{service.id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "detail-test"


async def test_get_service_not_found(client):
    resp = await client.get("/api/v1/services/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_search_services(client, db):
    service = McpService(
        name="playwright-mcp",
        source_url="https://github.com/playwright/mcp",
        source_type="docker_registry",
        category="Development",
    )
    db.add(service)
    await db.commit()

    resp = await client.get("/api/v1/services", params={"search": "playwright"})
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_api/test_services.py -v`
Expected: FAIL

- [ ] **Step 3: Implement app, deps, and services router**

```python
# backend/mcp_manager/api/__init__.py
```

```python
# backend/mcp_manager/api/deps.py
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from mcp_manager.db.session import SessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
```

```python
# backend/mcp_manager/api/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mcp_manager.config import settings
from mcp_manager.api.routers import services, summaries, installations, targets, sync, stats


def create_app() -> FastAPI:
    app = FastAPI(title="MCP Manager", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(services.router, prefix="/api/v1")
    app.include_router(summaries.router, prefix="/api/v1")
    app.include_router(installations.router, prefix="/api/v1")
    app.include_router(targets.router, prefix="/api/v1")
    app.include_router(sync.router, prefix="/api/v1")
    app.include_router(stats.router, prefix="/api/v1")

    return app
```

```python
# backend/mcp_manager/api/routers/__init__.py
```

```python
# backend/mcp_manager/api/routers/services.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_manager.api.deps import get_db
from mcp_manager.db.models import McpService

router = APIRouter(tags=["services"])


@router.get("/services")
async def list_services(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    source_type: str | None = None,
    category: str | None = None,
    search: str | None = None,
    is_deprecated: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(McpService)

    if source_type:
        query = query.where(McpService.source_type == source_type)
    if category:
        query = query.where(McpService.category == category)
    if is_deprecated is not None:
        query = query.where(McpService.is_deprecated == is_deprecated)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            McpService.name.ilike(pattern) | McpService.source_url.ilike(pattern)
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(McpService.name).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    services = result.scalars().all()

    return {
        "items": [_serialize_service(s) for s in services],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/services/{service_id}")
async def get_service(service_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(McpService).where(McpService.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return _serialize_service(service)


def _serialize_service(s: McpService) -> dict:
    return {
        "id": str(s.id),
        "name": s.name,
        "source_url": s.source_url,
        "doc_url": s.doc_url,
        "doc_hash": s.doc_hash,
        "branch_hash": s.branch_hash,
        "source_type": s.source_type,
        "transport": s.transport,
        "category": s.category,
        "tags": s.tags or [],
        "is_deprecated": s.is_deprecated,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
```

- [ ] **Step 4: Create stub routers** (to satisfy app.py imports)

```python
# backend/mcp_manager/api/routers/summaries.py
from fastapi import APIRouter
router = APIRouter(tags=["summaries"])
```

```python
# backend/mcp_manager/api/routers/installations.py
from fastapi import APIRouter
router = APIRouter(tags=["installations"])
```

```python
# backend/mcp_manager/api/routers/targets.py
from fastapi import APIRouter
router = APIRouter(tags=["targets"])
```

```python
# backend/mcp_manager/api/routers/sync.py
from fastapi import APIRouter
router = APIRouter(tags=["sync"])
```

```python
# backend/mcp_manager/api/routers/stats.py
from fastapi import APIRouter
router = APIRouter(tags=["stats"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_api/test_services.py -v`
Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/mcp_manager/api/ backend/tests/test_api/
git commit -m "feat: FastAPI app + services router with pagination and search"
```

---

### Task 11: Remaining API routers (summaries, installations, targets, sync, stats)

**Files:**
- Modify: `backend/mcp_manager/api/routers/summaries.py`
- Modify: `backend/mcp_manager/api/routers/installations.py`
- Modify: `backend/mcp_manager/api/routers/targets.py`
- Modify: `backend/mcp_manager/api/routers/sync.py`
- Modify: `backend/mcp_manager/api/routers/stats.py`
- Create: `backend/tests/test_api/test_summaries.py`
- Create: `backend/tests/test_api/test_targets.py`
- Create: `backend/tests/test_api/test_stats.py`

This task follows the same TDD pattern as Task 10. Each router gets:
1. Failing tests
2. Implementation
3. Passing tests
4. Commit per router

Due to plan length, implementation details for these routers follow the exact same patterns as `services.py`. Key endpoints:

**summaries.py:**
- `GET /summaries` — filter by culture, mcp_service_id
- `POST /summaries/generate` — trigger generation for outdated
- `GET /summaries/stats` — count by culture, outdated count

**installations.py:**
- `GET /installations` — filter by install_target_id, mcp_service_id
- `GET /installations/{id}` — detail
- `PUT /installations/{id}` — manual edit
- `POST /installations/generate` — regenerate auto recipes

**targets.py:**
- `GET /targets` — list all
- `POST /targets` — create
- `PUT /targets/{id}` — update

**sync.py:**
- `POST /services/sync` — trigger sync (runs in background task)
- `GET /services/sync/status` — last sync info

**stats.py:**
- `GET /stats` — total services, by source_type, by category, outdated summaries count

- [ ] **Step 1-4: TDD cycle for each router** (write test, verify fail, implement, verify pass)

- [ ] **Step 5: Commit all routers**

```bash
git add backend/mcp_manager/api/routers/ backend/tests/test_api/
git commit -m "feat: complete API routers (summaries, installations, targets, sync, stats)"
```

---

## Phase 6: CLI

### Task 12: Typer CLI

**Files:**
- Create: `backend/mcp_manager/cli.py`
- Create: `backend/tests/test_cli.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_cli.py
from typer.testing import CliRunner
from unittest.mock import patch, AsyncMock

from mcp_manager.cli import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "sync" in result.output
    assert "summarize" in result.output
    assert "export" in result.output


@patch("mcp_manager.cli._run_sync", new_callable=AsyncMock)
def test_sync_command(mock_sync):
    mock_sync.return_value = {"new": 5, "updated": 2, "unchanged": 100}
    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0
    mock_sync.assert_called_once()


@patch("mcp_manager.cli._run_sync", new_callable=AsyncMock)
def test_sync_with_source_filter(mock_sync):
    mock_sync.return_value = {"new": 0, "updated": 0, "unchanged": 50}
    result = runner.invoke(app, ["sync", "--source", "docker_registry"])
    assert result.exit_code == 0
    mock_sync.assert_called_once_with(source="docker_registry")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_cli.py -v`
Expected: FAIL

- [ ] **Step 3: Implement CLI**

```python
# backend/mcp_manager/cli.py
import asyncio
import logging

import typer

from mcp_manager.connectors.registry import get_all_connectors, get_connector

app = typer.Typer(name="mcp-manager", help="MCP Server Reference Manager")
logger = logging.getLogger(__name__)


@app.command()
def sync(source: str | None = typer.Option(None, help="Sync a specific source only")):
    """Sync MCP services from all registered sources."""
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(_run_sync(source=source))
    typer.echo(f"Sync complete: {result['new']} new, {result['updated']} updated, {result['unchanged']} unchanged")


async def _run_sync(source: str | None = None) -> dict[str, int]:
    from sqlalchemy import select
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import McpService

    if source:
        connector = get_connector(source)
        connectors = [connector] if connector else []
    else:
        connectors = get_all_connectors()

    stats = {"new": 0, "updated": 0, "unchanged": 0}

    for connector in connectors:
        services = await connector.fetch_services()
        async with SessionLocal() as db:
            for raw in services:
                result = await db.execute(
                    select(McpService).where(
                        McpService.source_type == raw.source_type,
                        McpService.name == raw.name,
                    )
                )
                existing = result.scalar_one_or_none()

                if not existing:
                    svc = McpService(
                        name=raw.name,
                        source_url=raw.source_url,
                        source_type=raw.source_type,
                        doc_url=raw.doc_url,
                        doc_hash=raw.doc_hash,
                        branch_hash=raw.branch_hash,
                        transport=raw.transport,
                        category=raw.category,
                        tags=raw.tags,
                        is_deprecated=raw.is_deprecated,
                    )
                    db.add(svc)
                    stats["new"] += 1
                elif existing.doc_hash != raw.doc_hash or existing.branch_hash != raw.branch_hash:
                    existing.doc_url = raw.doc_url
                    existing.doc_hash = raw.doc_hash
                    existing.branch_hash = raw.branch_hash
                    existing.transport = raw.transport
                    existing.category = raw.category
                    existing.tags = raw.tags
                    stats["updated"] += 1
                else:
                    stats["unchanged"] += 1

            await db.commit()

    return stats


@app.command()
def summarize(force: bool = typer.Option(False, help="Regenerate all summaries")):
    """Generate AI summaries for outdated or missing services."""
    logging.basicConfig(level=logging.INFO)
    count = asyncio.run(_run_summarize(force=force))
    typer.echo(f"Summaries generated: {count}")


async def _run_summarize(force: bool = False) -> int:
    from sqlalchemy import select
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import McpService, McpSummary
    from mcp_manager.summarizer.summarizer import generate_summary, CULTURES
    from mcp_manager.connectors.registry import get_connector

    count = 0
    async with SessionLocal() as db:
        result = await db.execute(select(McpService))
        services = result.scalars().all()

        for service in services:
            connector = get_connector(service.source_type)
            if not connector:
                continue

            for culture in CULTURES:
                # Check if summary exists and is up-to-date
                if not force:
                    existing = await db.execute(
                        select(McpSummary).where(
                            McpSummary.mcp_service_id == service.id,
                            McpSummary.culture == culture,
                        )
                    )
                    summary_row = existing.scalar_one_or_none()
                    if summary_row and summary_row.source_hash == service.doc_hash:
                        continue

                # Fetch doc and generate summary
                from mcp_manager.connectors.base import RawMcpService
                raw = RawMcpService(
                    name=service.name,
                    source_url=service.source_url,
                    source_type=service.source_type,
                    doc_url=service.doc_url,
                )
                doc_content = await connector.fetch_doc_content(raw)
                if not doc_content:
                    continue

                summary_text = await generate_summary(doc_content, culture)
                if not summary_text:
                    continue

                # Upsert summary
                existing = await db.execute(
                    select(McpSummary).where(
                        McpSummary.mcp_service_id == service.id,
                        McpSummary.culture == culture,
                    )
                )
                summary_row = existing.scalar_one_or_none()

                if summary_row:
                    summary_row.summary = summary_text
                    summary_row.source_hash = service.doc_hash
                else:
                    db.add(McpSummary(
                        mcp_service_id=service.id,
                        culture=culture,
                        summary=summary_text,
                        source_hash=service.doc_hash,
                    ))
                count += 1

        await db.commit()
    return count


@app.command()
def export(
    target: str = typer.Option(..., help="Target name (claude_code, langgraph, docker_stdio)"),
    output: str | None = typer.Option(None, help="Output file path"),
):
    """Export installation recipes for a target."""
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(_run_export(target=target, output=output))
    typer.echo(f"Exported {result} installations for {target}")


async def _run_export(target: str, output: str | None = None) -> int:
    from sqlalchemy import select
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import McpService, McpInstallation, InstallTarget
    from mcp_manager.exporters.engine import generate_installation_data

    count = 0
    async with SessionLocal() as db:
        target_result = await db.execute(
            select(InstallTarget).where(InstallTarget.name == target)
        )
        target_row = target_result.scalar_one_or_none()
        if not target_row:
            typer.echo(f"Unknown target: {target}", err=True)
            raise typer.Exit(1)

        services_result = await db.execute(select(McpService).where(McpService.is_deprecated == False))
        services = services_result.scalars().all()

        for service in services:
            data = generate_installation_data(
                registry_type=None,
                package_identifier=None,
                runtime_hint=None,
                transport=service.transport,
                target_name=target,
                service_name=service.name,
                env_vars={},
            )
            if not data:
                continue

            # Upsert installation
            existing = await db.execute(
                select(McpInstallation).where(
                    McpInstallation.mcp_service_id == service.id,
                    McpInstallation.install_target_id == target_row.id,
                )
            )
            install_row = existing.scalar_one_or_none()

            if install_row:
                install_row.action_type = data["action_type"]
                install_row.data = data["data"]
            else:
                db.add(McpInstallation(
                    mcp_service_id=service.id,
                    install_target_id=target_row.id,
                    action_type=data["action_type"],
                    data=data["data"],
                ))
            count += 1

        await db.commit()
    return count


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_cli.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/mcp_manager/cli.py backend/tests/test_cli.py
git commit -m "feat: Typer CLI with sync, summarize, export commands"
```

---

## Phase 7: Frontend

### Task 13: Frontend scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`

- [ ] **Step 1: Initialize frontend project**

Run:
```bash
cd frontend && npm create vite@latest . -- --template react-ts
npm install react-router-dom @tanstack/react-query tailwindcss @tailwindcss/vite
```

- [ ] **Step 2: Configure Vite with Tailwind and API proxy**

```typescript
// frontend/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3001,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

- [ ] **Step 3: Create App with router and query provider**

```tsx
// frontend/src/App.tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MainLayout } from "./layouts/MainLayout";
import { DashboardPage } from "./pages/DashboardPage";
import { ServicesPage } from "./pages/ServicesPage";
import { ServiceDetailPage } from "./pages/ServiceDetailPage";
import { TargetsPage } from "./pages/TargetsPage";
import { SyncPage } from "./pages/SyncPage";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/services" element={<ServicesPage />} />
            <Route path="/services/:id" element={<ServiceDetailPage />} />
            <Route path="/targets" element={<TargetsPage />} />
            <Route path="/sync" element={<SyncPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 4: Verify it builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: frontend scaffold (React, TypeScript, Vite, Tailwind, TanStack Query)"
```

---

### Task 14: Types + API client

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/services.ts`
- Create: `frontend/src/api/summaries.ts`
- Create: `frontend/src/api/installations.ts`
- Create: `frontend/src/api/targets.ts`
- Create: `frontend/src/api/sync.ts`
- Create: `frontend/src/api/stats.ts`

- [ ] **Step 1: Define types**

```typescript
// frontend/src/types/index.ts
export interface McpService {
  id: string;
  name: string;
  source_url: string;
  doc_url: string | null;
  doc_hash: string | null;
  branch_hash: string | null;
  source_type: string;
  transport: string | null;
  category: string | null;
  tags: string[];
  is_deprecated: boolean;
  created_at: string;
  updated_at: string;
}

export interface McpSummary {
  id: string;
  mcp_service_id: string;
  culture: string;
  summary: string;
  source_hash: string | null;
  created_at: string;
  updated_at: string;
}

export interface InstallTarget {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface McpInstallation {
  id: string;
  mcp_service_id: string;
  install_target_id: string;
  action_type: string;
  data: string;
  env_vars: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}

export interface Stats {
  total_services: number;
  by_source: Record<string, number>;
  by_category: Record<string, number>;
  outdated_summaries: number;
}

export interface SyncStatus {
  running: boolean;
  last_run: string | null;
  last_stats: { new: number; updated: number; unchanged: number } | null;
}
```

- [ ] **Step 2: Create typed API client**

```typescript
// frontend/src/api/client.ts
const BASE = "/api/v1";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!resp.ok) {
    throw new Error(`API error: ${resp.status} ${resp.statusText}`);
  }
  return resp.json();
}
```

```typescript
// frontend/src/api/services.ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { McpService, PaginatedResponse } from "../types";

interface ServiceFilters {
  page?: number;
  per_page?: number;
  source_type?: string;
  category?: string;
  search?: string;
  is_deprecated?: boolean;
}

export function useServices(filters: ServiceFilters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== "") params.set(k, String(v));
  });
  const qs = params.toString();
  return useQuery({
    queryKey: ["services", qs],
    queryFn: () => apiFetch<PaginatedResponse<McpService>>(`/services?${qs}`),
  });
}

export function useService(id: string) {
  return useQuery({
    queryKey: ["service", id],
    queryFn: () => apiFetch<McpService>(`/services/${id}`),
    enabled: !!id,
  });
}
```

The remaining API hooks (`summaries.ts`, `installations.ts`, `targets.ts`, `sync.ts`, `stats.ts`) follow the same pattern — `useQuery` for GET, `useMutation` for POST/PUT.

- [ ] **Step 3: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/ frontend/src/api/
git commit -m "feat: typed API client + React Query hooks"
```

---

### Task 15: UI components

**Files:**
- Create: all files under `frontend/src/components/ui/`

- [ ] **Step 1: Build reusable UI primitives**

Each component is a standalone, typed React component using Tailwind CSS. Key components:

- `Button.tsx` — variants (primary, secondary, danger), sizes, loading state
- `Badge.tsx` — colored label (source type, category, tags)
- `Card.tsx` — container with optional header
- `DataTable.tsx` — generic paginated table with column definitions, sorting, filters
- `SearchInput.tsx` — debounced search input
- `Modal.tsx` — overlay dialog
- `Tabs.tsx` — tab navigation
- `StatusBadge.tsx` — colored dot + label (active/deprecated/outdated)

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/
git commit -m "feat: reusable UI components (Button, Badge, Card, DataTable, etc.)"
```

---

### Task 16: Domain components + pages

**Files:**
- Create: all files under `frontend/src/components/domain/`
- Create: all files under `frontend/src/pages/`
- Create: `frontend/src/layouts/MainLayout.tsx`

- [ ] **Step 1: Build domain components**

- `ServiceCard.tsx` — displays name, source badge, category, transport, tags
- `SummaryView.tsx` — shows summary with en/fr toggle tabs
- `InstallCommand.tsx` — copyable code block with the install command
- `SyncStatusBar.tsx` — shows last sync time, running indicator
- `FilterPanel.tsx` — source type, category, deprecated toggle, search

- [ ] **Step 2: Build pages**

- `DashboardPage.tsx` — stats cards, recent services, sync status
- `ServicesPage.tsx` — DataTable with FilterPanel, pagination, links to detail
- `ServiceDetailPage.tsx` — full service info, SummaryView, InstallCommand per target
- `TargetsPage.tsx` — list targets, add/edit modal
- `SyncPage.tsx` — trigger sync button, history/logs

- [ ] **Step 3: Build layout**

```tsx
// frontend/src/layouts/MainLayout.tsx
import { Outlet, NavLink } from "react-router-dom";

export function MainLayout() {
  const links = [
    { to: "/", label: "Dashboard" },
    { to: "/services", label: "Services" },
    { to: "/targets", label: "Targets" },
    { to: "/sync", label: "Sync" },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="flex items-center gap-8">
          <span className="font-bold text-lg">MCP Manager</span>
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              className={({ isActive }) =>
                `text-sm ${isActive ? "text-blue-600 font-medium" : "text-gray-600 hover:text-gray-900"}`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat: domain components + pages + layout"
```

---

## Phase 8: Docker Compose + GitHub Actions

### Task 17: Docker Compose update + Dockerfiles

**Files:**
- Modify: `docker-compose.yml`
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`

- [ ] **Step 1: Create backend Dockerfile**

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY mcp_manager/ ./mcp_manager/
COPY scripts/ ./scripts/
CMD ["uvicorn", "mcp_manager.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create frontend Dockerfile**

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

```nginx
# frontend/nginx.conf
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://mcp-backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 3: Update docker-compose.yml**

```yaml
networks:
  langgraph-net:
    driver: bridge

services:
  langgraph-postgres:
    image: pgvector/pgvector:pg16
    container_name: langgraph-postgres
    restart: unless-stopped
    ports:
      - "127.0.0.1:5432:5432"
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - /opt/langgraph-data/postgres:/var/lib/postgresql/data
      - ./backend/scripts/init.sql:/docker-entrypoint-initdb.d/init.sql
    command:
      - postgres
      - -c
      - shared_preload_libraries=vector
      - -c
      - max_connections=200
      - -c
      - shared_buffers=256MB
      - -c
      - effective_cache_size=1GB
      - -c
      - work_mem=16MB
    healthcheck:
      test: pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 15s
    networks:
      - langgraph-net

  mcp-backend:
    build: ./backend
    container_name: mcp-backend
    restart: unless-stopped
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      langgraph-postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@langgraph-postgres:5432/${POSTGRES_DB}
      OLLAMA_BASE_URL: ${OLLAMA_BASE_URL:-http://192.168.10.80:11434}
      OLLAMA_SUMMARY_MODEL: ${OLLAMA_SUMMARY_MODEL:-llama3.1}
      CORS_ORIGINS: '["http://localhost:3001"]'
      GITHUB_TOKEN: ${GITHUB_TOKEN:-}
    networks:
      - langgraph-net

  mcp-frontend:
    build: ./frontend
    container_name: mcp-frontend
    restart: unless-stopped
    ports:
      - "127.0.0.1:3001:80"
    depends_on:
      - mcp-backend
    networks:
      - langgraph-net
```

- [ ] **Step 4: Verify compose config**

Run: `docker compose config`
Expected: Valid YAML output with all 3 services

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml backend/Dockerfile frontend/Dockerfile frontend/nginx.conf
git commit -m "feat: Docker Compose with backend, frontend, PostgreSQL"
```

---

### Task 18: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/sync.yml`

- [ ] **Step 1: Create workflow**

```yaml
# .github/workflows/sync.yml
name: MCP Sync

on:
  schedule:
    - cron: "0 */6 * * *"
  workflow_dispatch:

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        working-directory: backend
        run: pip install .

      - name: Run sync
        working-directory: backend
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}
        run: python -m mcp_manager.cli sync

      - name: Run summarize
        working-directory: backend
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          OLLAMA_BASE_URL: ${{ secrets.OLLAMA_BASE_URL }}
          OLLAMA_SUMMARY_MODEL: ${{ secrets.OLLAMA_SUMMARY_MODEL }}
        run: python -m mcp_manager.cli summarize

      - name: Run export (all targets)
        working-directory: backend
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          python -m mcp_manager.cli export --target claude_code
          python -m mcp_manager.cli export --target langgraph
          python -m mcp_manager.cli export --target docker_stdio
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/sync.yml
git commit -m "feat: GitHub Actions cron sync workflow (every 6h)"
```

---

### Task 19: Update env.example + final verification

**Files:**
- Modify: `env.example`

- [ ] **Step 1: Update env.example with all required vars**

```bash
# ── PostgreSQL ───────────────────────────────
POSTGRES_DB=langgraph
POSTGRES_USER=langgraph
POSTGRES_PASSWORD=CHANGEZ-MOI-EN-PROD

# ── Ollama ───────────────────────────────────
OLLAMA_BASE_URL=http://192.168.10.80:11434
OLLAMA_SUMMARY_MODEL=llama3.1
OLLAMA_EMBED_MODEL=mxbai-embed-large
EMBEDDING_DIM=1024

# ── MCP Manager ──────────────────────────────
GITHUB_TOKEN=
CORS_ORIGINS=["http://localhost:3001"]

# ── Admin Dashboard ──────────────────────────
WEB_ADMIN_USERNAME=admin
WEB_ADMIN_PASSWORD=CHANGEZ-MOI-EN-PROD
```

- [ ] **Step 2: Full stack verification**

Run:
```bash
docker compose up -d
# Wait for healthy
docker compose exec mcp-backend python -m mcp_manager.cli sync
docker compose exec mcp-backend python -m mcp_manager.cli summarize
curl http://localhost:8000/api/v1/stats
curl http://localhost:3001/
```

Expected:
- All 3 containers running
- Sync imports 300+ services
- Stats endpoint returns counters > 0
- Frontend loads in browser

- [ ] **Step 3: Commit**

```bash
git add env.example
git commit -m "feat: update env.example with MCP Manager variables"
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1-3 | DB foundation: scaffold, models, migrations |
| 2 | 4-6 | Connectors: base, Docker registry, MCP registry |
| 3 | 7-8 | Summarizer: cleaner, Ollama pipeline |
| 4 | 9 | Exporters: rule engine |
| 5 | 10-11 | API REST: all routers |
| 6 | 12 | CLI: sync, summarize, export |
| 7 | 13-16 | Frontend: scaffold, types, components, pages |
| 8 | 17-19 | Docker Compose, GitHub Actions, verification |
