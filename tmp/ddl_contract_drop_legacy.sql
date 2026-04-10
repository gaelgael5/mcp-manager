BEGIN;

-- Drop legacy summary/quality/rag columns from skill_sources
ALTER TABLE skill_sources DROP COLUMN IF EXISTS summary_en;
ALTER TABLE skill_sources DROP COLUMN IF EXISTS summary_fr;
ALTER TABLE skill_sources DROP COLUMN IF EXISTS heuristic_quality;
ALTER TABLE skill_sources DROP COLUMN IF EXISTS llm_quality;
ALTER TABLE skill_sources DROP COLUMN IF EXISTS rag_indexed_at;

-- Drop legacy summary/quality/rag columns from skills
ALTER TABLE skills DROP COLUMN IF EXISTS summary_en;
ALTER TABLE skills DROP COLUMN IF EXISTS summary_fr;
ALTER TABLE skills DROP COLUMN IF EXISTS heuristic_quality;
ALTER TABLE skills DROP COLUMN IF EXISTS llm_quality;
ALTER TABLE skills DROP COLUMN IF EXISTS rag_indexed_at;

COMMIT;

-- Verify: remaining columns of skills and skill_sources
SELECT 'skills' AS t, column_name FROM information_schema.columns
WHERE table_schema='public' AND table_name='skills'
  AND column_name IN ('summary_en','summary_fr','heuristic_quality','llm_quality','rag_indexed_at')
UNION ALL
SELECT 'skill_sources', column_name FROM information_schema.columns
WHERE table_schema='public' AND table_name='skill_sources'
  AND column_name IN ('summary_en','summary_fr','heuristic_quality','llm_quality','rag_indexed_at');
