-- AKOS Phase 2.4 Task 3: procedural memory
CREATE TABLE IF NOT EXISTS procedures (
    id TEXT PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases (id),
    name TEXT NOT NULL,
    steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    ontology_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    domain TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_procedures_kb_name ON procedures (knowledge_base_id, name);
CREATE INDEX IF NOT EXISTS idx_procedures_kb ON procedures (knowledge_base_id);
