BEGIN;

CREATE TABLE IF NOT EXISTS skill_sources_translations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_source_id UUID NOT NULL REFERENCES skill_sources(id) ON DELETE CASCADE,
    culture VARCHAR(5) NOT NULL,
    summary TEXT NOT NULL,
    source_hash VARCHAR(64),
    heuristic_quality INTEGER,
    llm_quality INTEGER,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    rag_indexed_at TIMESTAMPTZ,
    CONSTRAINT uq_skill_source_culture UNIQUE (skill_source_id, culture)
);

CREATE INDEX IF NOT EXISTS idx_skill_sources_translations_culture
    ON skill_sources_translations (culture);

CREATE TABLE IF NOT EXISTS skills_translations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    culture VARCHAR(5) NOT NULL,
    summary TEXT NOT NULL,
    source_hash VARCHAR(64),
    heuristic_quality INTEGER,
    llm_quality INTEGER,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    rag_indexed_at TIMESTAMPTZ,
    CONSTRAINT uq_skill_culture UNIQUE (skill_id, culture)
);

CREATE INDEX IF NOT EXISTS idx_skills_translations_culture
    ON skills_translations (culture);

-- Backfill skill_sources_translations from skill_sources columns
INSERT INTO skill_sources_translations
    (skill_source_id, culture, summary, source_hash,
     heuristic_quality, llm_quality, created_at, updated_at, rag_indexed_at)
SELECT id, 'en', summary_en, NULL,
       heuristic_quality, llm_quality,
       created_at, created_at, rag_indexed_at
FROM skill_sources
WHERE summary_en IS NOT NULL AND length(summary_en) > 0
ON CONFLICT DO NOTHING;

INSERT INTO skill_sources_translations
    (skill_source_id, culture, summary, source_hash,
     heuristic_quality, llm_quality, created_at, updated_at, rag_indexed_at)
SELECT id, 'fr', summary_fr, NULL,
       NULL, NULL,
       created_at, created_at, NULL
FROM skill_sources
WHERE summary_fr IS NOT NULL AND length(summary_fr) > 0
ON CONFLICT DO NOTHING;

-- Backfill skills_translations from skills columns
INSERT INTO skills_translations
    (skill_id, culture, summary, source_hash,
     heuristic_quality, llm_quality, created_at, updated_at, rag_indexed_at)
SELECT id, 'en', summary_en, NULL,
       heuristic_quality, llm_quality,
       created_at, updated_at, rag_indexed_at
FROM skills
WHERE summary_en IS NOT NULL AND length(summary_en) > 0
ON CONFLICT DO NOTHING;

INSERT INTO skills_translations
    (skill_id, culture, summary, source_hash,
     heuristic_quality, llm_quality, created_at, updated_at, rag_indexed_at)
SELECT id, 'fr', summary_fr, NULL,
       NULL, NULL,
       created_at, updated_at, NULL
FROM skills
WHERE summary_fr IS NOT NULL AND length(summary_fr) > 0
ON CONFLICT DO NOTHING;

COMMIT;

SELECT 'skill_sources_translations' AS t, culture, COUNT(*) FROM skill_sources_translations GROUP BY culture
UNION ALL
SELECT 'skills_translations', culture, COUNT(*) FROM skills_translations GROUP BY culture
ORDER BY 1, 2;
