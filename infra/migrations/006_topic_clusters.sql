CREATE TABLE IF NOT EXISTS topic_clusters (
    id TEXT PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases (id),
    name TEXT NOT NULL,
    aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
    chunk_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    claim_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    content_hash TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (knowledge_base_id, name)
);

CREATE INDEX IF NOT EXISTS idx_topic_clusters_kb_status
    ON topic_clusters (knowledge_base_id, status);
