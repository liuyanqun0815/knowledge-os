-- AKOS Phase 2.2 Task 2: evolution chain + events
ALTER TABLE sources ADD COLUMN IF NOT EXISTS replaces_source_id TEXT;

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases (id),
    type TEXT NOT NULL,
    participants JSONB NOT NULL DEFAULT '[]'::jsonb,
    timestamp TIMESTAMPTZ NOT NULL,
    source_id TEXT NOT NULL REFERENCES sources (id)
);

CREATE INDEX IF NOT EXISTS idx_events_kb ON events (knowledge_base_id);
CREATE INDEX IF NOT EXISTS idx_events_source_id ON events (source_id);

DO $$
BEGIN
    ALTER TABLE sources
        ADD CONSTRAINT fk_sources_replaces_source
        FOREIGN KEY (replaces_source_id) REFERENCES sources (id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;
