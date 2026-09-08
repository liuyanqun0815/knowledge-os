-- AKOS Phase 1 PostgreSQL schema (spec §4.2)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    type TEXT NOT NULL,
    uri TEXT NOT NULL,
    version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_texts (
    source_id TEXT PRIMARY KEY REFERENCES sources (id) ON DELETE CASCADE,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    props JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS relations (
    id SERIAL PRIMARY KEY,
    src TEXT NOT NULL REFERENCES entities (id),
    predicate TEXT NOT NULL,
    dst TEXT NOT NULL REFERENCES entities (id),
    props JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_relations_src ON relations (src);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
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

CREATE TABLE IF NOT EXISTS claim_evidence (
    id SERIAL PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES claims (id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES sources (id),
    start_pos INTEGER NOT NULL,
    end_pos INTEGER NOT NULL,
    quote TEXT NOT NULL,
    weight DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_claim_evidence_claim_id ON claim_evidence (claim_id);

CREATE TABLE IF NOT EXISTS embeddings (
    id SERIAL PRIMARY KEY,
    ref_type TEXT NOT NULL,
    ref_id TEXT NOT NULL,
    embedding vector(64) NOT NULL,
    UNIQUE (ref_type, ref_id)
);

CREATE TABLE IF NOT EXISTS quarantine (
    id SERIAL PRIMARY KEY,
    reason TEXT NOT NULL,
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memory_episodes (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    episode JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_episodes_session_id ON memory_episodes (session_id);

CREATE TABLE IF NOT EXISTS memory_semantics (
    id SERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    value JSONB NOT NULL DEFAULT '{}'::jsonb
);
