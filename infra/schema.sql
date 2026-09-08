-- AKOS Phase 1 PostgreSQL schema (spec §4.2) + Phase 2.1 knowledge_base_id
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    domain_type TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases (id),
    title TEXT NOT NULL,
    type TEXT NOT NULL,
    uri TEXT NOT NULL,
    version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sources_kb ON sources (knowledge_base_id);

CREATE TABLE IF NOT EXISTS source_texts (
    source_id TEXT PRIMARY KEY REFERENCES sources (id) ON DELETE CASCADE,
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases (id),
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases (id),
    type TEXT NOT NULL,
    props JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_entities_kb ON entities (knowledge_base_id);

CREATE TABLE IF NOT EXISTS relations (
    id SERIAL PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases (id),
    src TEXT NOT NULL REFERENCES entities (id),
    predicate TEXT NOT NULL,
    dst TEXT NOT NULL REFERENCES entities (id),
    props JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_relations_src ON relations (src);
CREATE INDEX IF NOT EXISTS idx_relations_kb ON relations (knowledge_base_id);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases (id),
    family_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    object_type TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    source_ids JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_claims_family_id ON claims (family_id);
CREATE INDEX IF NOT EXISTS idx_claims_subject_predicate_status ON claims (subject, predicate, status);
CREATE INDEX IF NOT EXISTS idx_claims_kb ON claims (knowledge_base_id);

CREATE TABLE IF NOT EXISTS claim_evidence (
    id SERIAL PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases (id),
    claim_id TEXT NOT NULL REFERENCES claims (id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES sources (id),
    start_pos INTEGER NOT NULL,
    end_pos INTEGER NOT NULL,
    quote TEXT NOT NULL,
    weight DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_claim_evidence_claim_id ON claim_evidence (claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_evidence_kb ON claim_evidence (knowledge_base_id);

CREATE TABLE IF NOT EXISTS embeddings (
    id SERIAL PRIMARY KEY,
    ref_type TEXT NOT NULL,
    ref_id TEXT NOT NULL,
    embedding vector(64) NOT NULL,
    UNIQUE (ref_type, ref_id)
);

CREATE TABLE IF NOT EXISTS quarantine (
    id SERIAL PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases (id),
    reason TEXT NOT NULL,
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quarantine_kb ON quarantine (knowledge_base_id);

CREATE TABLE IF NOT EXISTS memory_episodes (
    id SERIAL PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases (id),
    session_id TEXT NOT NULL,
    episode JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_episodes_session_id ON memory_episodes (session_id);
CREATE INDEX IF NOT EXISTS idx_memory_episodes_kb ON memory_episodes (knowledge_base_id);

CREATE TABLE IF NOT EXISTS memory_semantics (
    id SERIAL PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases (id),
    key TEXT NOT NULL,
    value JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (knowledge_base_id, key)
);

CREATE INDEX IF NOT EXISTS idx_memory_semantics_kb ON memory_semantics (knowledge_base_id);
