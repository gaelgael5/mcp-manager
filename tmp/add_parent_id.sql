BEGIN;

-- mcp_summaries (parent : mcp_services)
ALTER TABLE mcp_summaries ADD COLUMN parent_id BIGINT;

-- mcp_parameters (parent : mcp_services)
ALTER TABLE mcp_parameters ADD COLUMN parent_id BIGINT;

-- mcp_installations (parent : mcp_services)
ALTER TABLE mcp_installations ADD COLUMN parent_id BIGINT;

-- skill_sources_translations (parent : skill_sources)
ALTER TABLE skill_sources_translations ADD COLUMN parent_id BIGINT;

-- skills_translations (parent : skills)
ALTER TABLE skills_translations ADD COLUMN parent_id BIGINT;

COMMIT;
