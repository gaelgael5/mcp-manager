BEGIN;

-- Migrate any remaining skill_sources rows
INSERT INTO skill_sources_translations
    (skill_source_id, culture, summary, source_hash,
     heuristic_quality, llm_quality, created_at, updated_at, rag_indexed_at)
SELECT id, 'en', summary_en, NULL,
       heuristic_quality, llm_quality,
       created_at, created_at, rag_indexed_at
FROM skill_sources
WHERE summary_en IS NOT NULL AND length(summary_en) > 0
ON CONFLICT (skill_source_id, culture) DO NOTHING;

INSERT INTO skill_sources_translations
    (skill_source_id, culture, summary, source_hash,
     heuristic_quality, llm_quality, created_at, updated_at, rag_indexed_at)
SELECT id, 'fr', summary_fr, NULL,
       NULL, NULL,
       created_at, created_at, NULL
FROM skill_sources
WHERE summary_fr IS NOT NULL AND length(summary_fr) > 0
ON CONFLICT (skill_source_id, culture) DO NOTHING;

-- Migrate any remaining skills rows
INSERT INTO skills_translations
    (skill_id, culture, summary, source_hash,
     heuristic_quality, llm_quality, created_at, updated_at, rag_indexed_at)
SELECT id, 'en', summary_en, NULL,
       heuristic_quality, llm_quality,
       created_at, updated_at, rag_indexed_at
FROM skills
WHERE summary_en IS NOT NULL AND length(summary_en) > 0
ON CONFLICT (skill_id, culture) DO NOTHING;

INSERT INTO skills_translations
    (skill_id, culture, summary, source_hash,
     heuristic_quality, llm_quality, created_at, updated_at, rag_indexed_at)
SELECT id, 'fr', summary_fr, NULL,
       NULL, NULL,
       created_at, updated_at, NULL
FROM skills
WHERE summary_fr IS NOT NULL AND length(summary_fr) > 0
ON CONFLICT (skill_id, culture) DO NOTHING;

COMMIT;

-- Final state check
SELECT 'skills.summary_en' AS src, COUNT(*) AS n FROM skills WHERE summary_en IS NOT NULL AND length(summary_en) > 0
UNION ALL SELECT 'skills_translations.en', COUNT(*) FROM skills_translations WHERE culture='en'
UNION ALL SELECT 'skills.summary_fr', COUNT(*) FROM skills WHERE summary_fr IS NOT NULL AND length(summary_fr) > 0
UNION ALL SELECT 'skills_translations.fr', COUNT(*) FROM skills_translations WHERE culture='fr'
UNION ALL SELECT 'skill_sources.summary_en', COUNT(*) FROM skill_sources WHERE summary_en IS NOT NULL AND length(summary_en) > 0
UNION ALL SELECT 'skill_sources_translations.en', COUNT(*) FROM skill_sources_translations WHERE culture='en'
UNION ALL SELECT 'skill_sources.summary_fr', COUNT(*) FROM skill_sources WHERE summary_fr IS NOT NULL AND length(summary_fr) > 0
UNION ALL SELECT 'skill_sources_translations.fr', COUNT(*) FROM skill_sources_translations WHERE culture='fr'
ORDER BY src;

-- Check that no row in source columns lacks its translation
SELECT 'skills en missing in translations' AS check_name, COUNT(*) AS n
FROM skills s
WHERE s.summary_en IS NOT NULL AND length(s.summary_en) > 0
  AND NOT EXISTS (SELECT 1 FROM skills_translations t WHERE t.skill_id = s.id AND t.culture = 'en')
UNION ALL SELECT 'skills fr missing in translations', COUNT(*)
FROM skills s
WHERE s.summary_fr IS NOT NULL AND length(s.summary_fr) > 0
  AND NOT EXISTS (SELECT 1 FROM skills_translations t WHERE t.skill_id = s.id AND t.culture = 'fr')
UNION ALL SELECT 'skill_sources en missing in translations', COUNT(*)
FROM skill_sources s
WHERE s.summary_en IS NOT NULL AND length(s.summary_en) > 0
  AND NOT EXISTS (SELECT 1 FROM skill_sources_translations t WHERE t.skill_source_id = s.id AND t.culture = 'en')
UNION ALL SELECT 'skill_sources fr missing in translations', COUNT(*)
FROM skill_sources s
WHERE s.summary_fr IS NOT NULL AND length(s.summary_fr) > 0
  AND NOT EXISTS (SELECT 1 FROM skill_sources_translations t WHERE t.skill_source_id = s.id AND t.culture = 'fr');
