BEGIN;

ALTER TABLE mcp_summaries
    ADD CONSTRAINT fk_mcp_summaries_parent
    FOREIGN KEY (parent_id) REFERENCES mcp_services (_id) ON DELETE CASCADE;

ALTER TABLE mcp_parameters
    ADD CONSTRAINT fk_mcp_parameters_parent
    FOREIGN KEY (parent_id) REFERENCES mcp_services (_id) ON DELETE CASCADE;

ALTER TABLE mcp_installations
    ADD CONSTRAINT fk_mcp_installations_parent
    FOREIGN KEY (parent_id) REFERENCES mcp_services (_id) ON DELETE CASCADE;

ALTER TABLE skill_sources_translations
    ADD CONSTRAINT fk_skill_sources_translations_parent
    FOREIGN KEY (parent_id) REFERENCES skill_sources (_id) ON DELETE CASCADE;

ALTER TABLE skills_translations
    ADD CONSTRAINT fk_skills_translations_parent
    FOREIGN KEY (parent_id) REFERENCES skills (_id) ON DELETE CASCADE;

COMMIT;
