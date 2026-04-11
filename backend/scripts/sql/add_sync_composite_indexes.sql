BEGIN;

CREATE INDEX IF NOT EXISTS idx_mcp_services_sync ON mcp_services (updated_at, _id);
CREATE INDEX IF NOT EXISTS idx_mcp_summaries_sync ON mcp_summaries (updated_at, _id);
CREATE INDEX IF NOT EXISTS idx_mcp_parameters_sync ON mcp_parameters (updated_at, _id);
CREATE INDEX IF NOT EXISTS idx_mcp_installations_sync ON mcp_installations (updated_at, _id);
CREATE INDEX IF NOT EXISTS idx_skill_sources_sync ON skill_sources (updated_at, _id);
CREATE INDEX IF NOT EXISTS idx_skill_sources_translations_sync ON skill_sources_translations (updated_at, _id);
CREATE INDEX IF NOT EXISTS idx_skills_sync ON skills (updated_at, _id);
CREATE INDEX IF NOT EXISTS idx_skills_translations_sync ON skills_translations (updated_at, _id);

COMMIT;
