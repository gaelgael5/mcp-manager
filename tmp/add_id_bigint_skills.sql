BEGIN;

-- skill_sources (~10k rows)
CREATE SEQUENCE skill_sources__id_seq;
ALTER TABLE skill_sources ADD COLUMN _id BIGINT NOT NULL DEFAULT 0;
UPDATE skill_sources SET _id = subq.new_id
FROM (
    SELECT id, ROW_NUMBER() OVER (ORDER BY created_at, id) AS new_id
    FROM skill_sources
) subq
WHERE skill_sources.id = subq.id;
SELECT setval('skill_sources__id_seq', (SELECT MAX(_id) FROM skill_sources));
ALTER TABLE skill_sources ALTER COLUMN _id SET DEFAULT nextval('skill_sources__id_seq');
CREATE UNIQUE INDEX idx_skill_sources__id ON skill_sources (_id);

-- skill_sources_translations (~11k rows)
CREATE SEQUENCE skill_sources_translations__id_seq;
ALTER TABLE skill_sources_translations ADD COLUMN _id BIGINT NOT NULL DEFAULT 0;
UPDATE skill_sources_translations SET _id = subq.new_id
FROM (
    SELECT id, ROW_NUMBER() OVER (ORDER BY created_at, id) AS new_id
    FROM skill_sources_translations
) subq
WHERE skill_sources_translations.id = subq.id;
SELECT setval('skill_sources_translations__id_seq', (SELECT MAX(_id) FROM skill_sources_translations));
ALTER TABLE skill_sources_translations ALTER COLUMN _id SET DEFAULT nextval('skill_sources_translations__id_seq');
CREATE UNIQUE INDEX idx_skill_sources_translations__id ON skill_sources_translations (_id);

-- skills_translations (~95k rows)
CREATE SEQUENCE skills_translations__id_seq;
ALTER TABLE skills_translations ADD COLUMN _id BIGINT NOT NULL DEFAULT 0;
UPDATE skills_translations SET _id = subq.new_id
FROM (
    SELECT id, ROW_NUMBER() OVER (ORDER BY created_at, id) AS new_id
    FROM skills_translations
) subq
WHERE skills_translations.id = subq.id;
SELECT setval('skills_translations__id_seq', (SELECT MAX(_id) FROM skills_translations));
ALTER TABLE skills_translations ALTER COLUMN _id SET DEFAULT nextval('skills_translations__id_seq');
CREATE UNIQUE INDEX idx_skills_translations__id ON skills_translations (_id);

-- skills (~925k rows — plusieurs minutes attendues)
CREATE SEQUENCE skills__id_seq;
ALTER TABLE skills ADD COLUMN _id BIGINT NOT NULL DEFAULT 0;
UPDATE skills SET _id = subq.new_id
FROM (
    SELECT id, ROW_NUMBER() OVER (ORDER BY created_at, id) AS new_id
    FROM skills
) subq
WHERE skills.id = subq.id;
SELECT setval('skills__id_seq', (SELECT MAX(_id) FROM skills));
ALTER TABLE skills ALTER COLUMN _id SET DEFAULT nextval('skills__id_seq');
CREATE UNIQUE INDEX idx_skills__id ON skills (_id);

COMMIT;
