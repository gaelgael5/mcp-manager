BEGIN;
ALTER TABLE skill_sources
    ADD COLUMN repo_format VARCHAR(20) NOT NULL DEFAULT 'skills';
COMMIT;
