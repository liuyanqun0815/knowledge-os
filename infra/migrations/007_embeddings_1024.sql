-- Idempotent upgrade: embeddings scoped by knowledge_base_id + vector(768).

ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS knowledge_base_id TEXT;
UPDATE embeddings SET knowledge_base_id = 'legacy' WHERE knowledge_base_id IS NULL;
ALTER TABLE embeddings ALTER COLUMN knowledge_base_id SET NOT NULL;

ALTER TABLE embeddings DROP CONSTRAINT IF EXISTS embeddings_ref_type_ref_id_key;
ALTER TABLE embeddings DROP CONSTRAINT IF EXISTS embeddings_kb_ref_unique;
ALTER TABLE embeddings ADD CONSTRAINT embeddings_kb_ref_unique UNIQUE (knowledge_base_id, ref_type, ref_id);

TRUNCATE TABLE embeddings;

ALTER TABLE embeddings DROP COLUMN IF EXISTS embedding;
ALTER TABLE embeddings ADD COLUMN embedding vector(768) NOT NULL;

CREATE INDEX IF NOT EXISTS idx_embeddings_kb_type ON embeddings (knowledge_base_id, ref_type);
DROP INDEX IF EXISTS idx_embeddings_hnsw;
CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw ON embeddings USING hnsw (embedding vector_cosine_ops);
