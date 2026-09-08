-- AKOS Phase 2.1: knowledge_bases table (Task 1)
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    domain_type TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

-- AKOS Phase 2.1 Task 2: scope business tables by knowledge_base_id
INSERT INTO knowledge_bases (id, name, domain_type, description, status, created_at, updated_at)
VALUES ('legacy', 'Legacy', 'ecommerce_cs', 'Migrated pre-2.1 data', 'active', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

ALTER TABLE sources ADD COLUMN IF NOT EXISTS knowledge_base_id TEXT;
UPDATE sources SET knowledge_base_id = 'legacy' WHERE knowledge_base_id IS NULL;
ALTER TABLE sources ALTER COLUMN knowledge_base_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sources_kb ON sources (knowledge_base_id);

ALTER TABLE source_texts ADD COLUMN IF NOT EXISTS knowledge_base_id TEXT;
UPDATE source_texts st
SET knowledge_base_id = s.knowledge_base_id
FROM sources s
WHERE st.source_id = s.id AND st.knowledge_base_id IS NULL;
UPDATE source_texts SET knowledge_base_id = 'legacy' WHERE knowledge_base_id IS NULL;
ALTER TABLE source_texts ALTER COLUMN knowledge_base_id SET NOT NULL;

ALTER TABLE claims ADD COLUMN IF NOT EXISTS knowledge_base_id TEXT;
UPDATE claims SET knowledge_base_id = 'legacy' WHERE knowledge_base_id IS NULL;
ALTER TABLE claims ALTER COLUMN knowledge_base_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_claims_kb ON claims (knowledge_base_id);

ALTER TABLE quarantine ADD COLUMN IF NOT EXISTS knowledge_base_id TEXT;
UPDATE quarantine SET knowledge_base_id = 'legacy' WHERE knowledge_base_id IS NULL;
ALTER TABLE quarantine ALTER COLUMN knowledge_base_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_quarantine_kb ON quarantine (knowledge_base_id);

ALTER TABLE entities ADD COLUMN IF NOT EXISTS knowledge_base_id TEXT;
UPDATE entities SET knowledge_base_id = 'legacy' WHERE knowledge_base_id IS NULL;
ALTER TABLE entities ALTER COLUMN knowledge_base_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_entities_kb ON entities (knowledge_base_id);

ALTER TABLE relations ADD COLUMN IF NOT EXISTS knowledge_base_id TEXT;
UPDATE relations SET knowledge_base_id = 'legacy' WHERE knowledge_base_id IS NULL;
ALTER TABLE relations ALTER COLUMN knowledge_base_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_relations_kb ON relations (knowledge_base_id);

ALTER TABLE claim_evidence ADD COLUMN IF NOT EXISTS knowledge_base_id TEXT;
UPDATE claim_evidence SET knowledge_base_id = 'legacy' WHERE knowledge_base_id IS NULL;
ALTER TABLE claim_evidence ALTER COLUMN knowledge_base_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_claim_evidence_kb ON claim_evidence (knowledge_base_id);

ALTER TABLE memory_episodes ADD COLUMN IF NOT EXISTS knowledge_base_id TEXT;
UPDATE memory_episodes SET knowledge_base_id = 'legacy' WHERE knowledge_base_id IS NULL;
ALTER TABLE memory_episodes ALTER COLUMN knowledge_base_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memory_episodes_kb ON memory_episodes (knowledge_base_id);

ALTER TABLE memory_semantics ADD COLUMN IF NOT EXISTS knowledge_base_id TEXT;
UPDATE memory_semantics SET knowledge_base_id = 'legacy' WHERE knowledge_base_id IS NULL;
ALTER TABLE memory_semantics ALTER COLUMN knowledge_base_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memory_semantics_kb ON memory_semantics (knowledge_base_id);

DO $$
BEGIN
    ALTER TABLE sources
        ADD CONSTRAINT fk_sources_knowledge_base
        FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases (id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE source_texts
        ADD CONSTRAINT fk_source_texts_knowledge_base
        FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases (id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE claims
        ADD CONSTRAINT fk_claims_knowledge_base
        FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases (id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE quarantine
        ADD CONSTRAINT fk_quarantine_knowledge_base
        FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases (id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE entities
        ADD CONSTRAINT fk_entities_knowledge_base
        FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases (id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE relations
        ADD CONSTRAINT fk_relations_knowledge_base
        FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases (id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE claim_evidence
        ADD CONSTRAINT fk_claim_evidence_knowledge_base
        FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases (id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE memory_episodes
        ADD CONSTRAINT fk_memory_episodes_knowledge_base
        FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases (id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE memory_semantics
        ADD CONSTRAINT fk_memory_semantics_knowledge_base
        FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases (id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;
