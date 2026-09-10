CREATE TABLE IF NOT EXISTS source_chunks (
    id TEXT PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases (id),
    source_id TEXT NOT NULL,
    chunk_index INT NOT NULL,
    title TEXT,
    summary TEXT,
    text TEXT NOT NULL,
    start_offset INT NOT NULL,
    end_offset INT NOT NULL,
    section_path JSONB DEFAULT '[]'::jsonb,
    topics JSONB DEFAULT '[]'::jsonb,
    token_count INT DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    content_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (knowledge_base_id, source_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_source_chunks_kb_source ON source_chunks (knowledge_base_id, source_id);
CREATE INDEX IF NOT EXISTS idx_source_chunks_hash ON source_chunks (content_hash);
