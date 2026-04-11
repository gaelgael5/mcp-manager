BEGIN;

-- mcp_parameters
DROP INDEX idx_mcp_parameters__id;
UPDATE mcp_parameters SET _id = subq.new_id
FROM (
    SELECT id, ROW_NUMBER() OVER (ORDER BY created_at, id) AS new_id
    FROM mcp_parameters
) subq
WHERE mcp_parameters.id = subq.id;
SELECT setval('mcp_parameters__id_seq', (SELECT MAX(_id) FROM mcp_parameters));
CREATE UNIQUE INDEX idx_mcp_parameters__id ON mcp_parameters (_id);

-- mcp_summaries
DROP INDEX idx_mcp_summaries__id;
UPDATE mcp_summaries SET _id = subq.new_id
FROM (
    SELECT id, ROW_NUMBER() OVER (ORDER BY created_at, id) AS new_id
    FROM mcp_summaries
) subq
WHERE mcp_summaries.id = subq.id;
SELECT setval('mcp_summaries__id_seq', (SELECT MAX(_id) FROM mcp_summaries));
CREATE UNIQUE INDEX idx_mcp_summaries__id ON mcp_summaries (_id);

-- mcp_services
DROP INDEX idx_mcp_services__id;
UPDATE mcp_services SET _id = subq.new_id
FROM (
    SELECT id, ROW_NUMBER() OVER (ORDER BY created_at, id) AS new_id
    FROM mcp_services
) subq
WHERE mcp_services.id = subq.id;
SELECT setval('mcp_services__id_seq', (SELECT MAX(_id) FROM mcp_services));
CREATE UNIQUE INDEX idx_mcp_services__id ON mcp_services (_id);

-- mcp_installations (744k rows — plus long)
DROP INDEX idx_mcp_installations__id;
UPDATE mcp_installations SET _id = subq.new_id
FROM (
    SELECT id, ROW_NUMBER() OVER (ORDER BY created_at, id) AS new_id
    FROM mcp_installations
) subq
WHERE mcp_installations.id = subq.id;
SELECT setval('mcp_installations__id_seq', (SELECT MAX(_id) FROM mcp_installations));
CREATE UNIQUE INDEX idx_mcp_installations__id ON mcp_installations (_id);

COMMIT;
