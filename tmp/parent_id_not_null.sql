BEGIN;

ALTER TABLE mcp_summaries ALTER COLUMN parent_id SET NOT NULL;
ALTER TABLE mcp_parameters ALTER COLUMN parent_id SET NOT NULL;
ALTER TABLE mcp_installations ALTER COLUMN parent_id SET NOT NULL;
ALTER TABLE skill_sources_translations ALTER COLUMN parent_id SET NOT NULL;
ALTER TABLE skills_translations ALTER COLUMN parent_id SET NOT NULL;

COMMIT;
