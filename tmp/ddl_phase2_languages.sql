BEGIN;

CREATE TABLE IF NOT EXISTS languages (
    code VARCHAR(5) PRIMARY KEY,
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT false,
    display_order INTEGER NOT NULL DEFAULT 100,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO languages (code, name, is_active, display_order) VALUES
    ('en', 'English', true, 10),
    ('fr', 'Français', true, 20),
    ('de', 'Deutsch', false, 30),
    ('es', 'Español', false, 40),
    ('pt', 'Português', false, 50),
    ('it', 'Italiano', false, 60),
    ('ru', 'Русский', false, 70),
    ('ar', 'العربية', false, 80),
    ('zh', '中文', false, 90),
    ('ja', '日本語', false, 100),
    ('ko', '한국어', false, 110),
    ('hi', 'हिन्दी', false, 120)
ON CONFLICT (code) DO NOTHING;

-- Add FK constraints on culture columns
ALTER TABLE mcp_summaries
    ADD CONSTRAINT fk_mcp_summaries_culture
    FOREIGN KEY (culture) REFERENCES languages(code);

ALTER TABLE skill_sources_translations
    ADD CONSTRAINT fk_ss_translations_culture
    FOREIGN KEY (culture) REFERENCES languages(code);

ALTER TABLE skills_translations
    ADD CONSTRAINT fk_s_translations_culture
    FOREIGN KEY (culture) REFERENCES languages(code);

COMMIT;

SELECT code, name, is_active, display_order FROM languages ORDER BY display_order;
