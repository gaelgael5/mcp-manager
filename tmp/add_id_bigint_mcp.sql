BEGIN;

-- mcp_parameters (15 414 rows)
CREATE SEQUENCE mcp_parameters__id_seq;
ALTER TABLE mcp_parameters
    ADD COLUMN _id BIGINT NOT NULL
    DEFAULT nextval('mcp_parameters__id_seq');
CREATE UNIQUE INDEX idx_mcp_parameters__id ON mcp_parameters (_id);

-- mcp_summaries (32 510 rows)
CREATE SEQUENCE mcp_summaries__id_seq;
ALTER TABLE mcp_summaries
    ADD COLUMN _id BIGINT NOT NULL
    DEFAULT nextval('mcp_summaries__id_seq');
CREATE UNIQUE INDEX idx_mcp_summaries__id ON mcp_summaries (_id);

-- mcp_services (37 122 rows)
CREATE SEQUENCE mcp_services__id_seq;
ALTER TABLE mcp_services
    ADD COLUMN _id BIGINT NOT NULL
    DEFAULT nextval('mcp_services__id_seq');
CREATE UNIQUE INDEX idx_mcp_services__id ON mcp_services (_id);

-- mcp_installations (744 514 rows — 1 à 2 minutes attendues)
CREATE SEQUENCE mcp_installations__id_seq;
ALTER TABLE mcp_installations
    ADD COLUMN _id BIGINT NOT NULL
    DEFAULT nextval('mcp_installations__id_seq');
CREATE UNIQUE INDEX idx_mcp_installations__id ON mcp_installations (_id);

COMMIT;
