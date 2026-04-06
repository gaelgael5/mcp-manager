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
    package_info    JSONB DEFAULT '{}',
    source_origins  TEXT[] DEFAULT '{}',
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

-- Note: skills table managed by SQLAlchemy, but for fresh installs ensure install_command column
-- ALTER TABLE skills ADD COLUMN IF NOT EXISTS install_command TEXT;
-- ALTER TABLE skills ADD COLUMN IF NOT EXISTS weekly_installs INTEGER DEFAULT 0;

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
