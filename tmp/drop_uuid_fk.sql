BEGIN;

-- Drop UUID FK constraints (keep the UUID columns themselves)
ALTER TABLE mcp_summaries
    DROP CONSTRAINT mcp_summaries_mcp_service_id_fkey;

ALTER TABLE mcp_parameters
    DROP CONSTRAINT mcp_parameters_mcp_service_id_fkey;

ALTER TABLE mcp_installations
    DROP CONSTRAINT mcp_installations_mcp_service_id_fkey;

ALTER TABLE skill_sources_translations
    DROP CONSTRAINT skill_sources_translations_skill_source_id_fkey;

ALTER TABLE skills_translations
    DROP CONSTRAINT skills_translations_skill_id_fkey;

COMMIT;
