BEGIN;

ALTER TABLE mcp_parameters ADD COLUMN updated_at TIMESTAMPTZ;
UPDATE mcp_parameters SET updated_at = created_at WHERE updated_at IS NULL;
ALTER TABLE mcp_parameters ALTER COLUMN updated_at SET NOT NULL;
ALTER TABLE mcp_parameters ALTER COLUMN updated_at SET DEFAULT NOW();

ALTER TABLE skill_sources ADD COLUMN updated_at TIMESTAMPTZ;
UPDATE skill_sources SET updated_at = created_at WHERE updated_at IS NULL;
ALTER TABLE skill_sources ALTER COLUMN updated_at SET NOT NULL;
ALTER TABLE skill_sources ALTER COLUMN updated_at SET DEFAULT NOW();

COMMIT;
