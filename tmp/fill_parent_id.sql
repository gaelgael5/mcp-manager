BEGIN;

-- mcp_summaries.parent_id <- mcp_services._id via mcp_service_id
UPDATE mcp_summaries s
SET parent_id = p._id
FROM mcp_services p
WHERE s.mcp_service_id = p.id;

-- mcp_parameters.parent_id <- mcp_services._id via mcp_service_id
UPDATE mcp_parameters s
SET parent_id = p._id
FROM mcp_services p
WHERE s.mcp_service_id = p.id;

-- mcp_installations.parent_id <- mcp_services._id via mcp_service_id
UPDATE mcp_installations s
SET parent_id = p._id
FROM mcp_services p
WHERE s.mcp_service_id = p.id;

-- skill_sources_translations.parent_id <- skill_sources._id via skill_source_id
UPDATE skill_sources_translations s
SET parent_id = p._id
FROM skill_sources p
WHERE s.skill_source_id = p.id;

-- skills_translations.parent_id <- skills._id via skill_id
UPDATE skills_translations s
SET parent_id = p._id
FROM skills p
WHERE s.skill_id = p.id;

COMMIT;
