-- save_chunks 会先把旧行标 stale 再插入同 (kb, source, chunk_index) 的新行。
-- UNIQUE 会让第二次写入失败，且 mark_stale 已单独提交，界面只剩「过期」Chunk。
ALTER TABLE source_chunks
    DROP CONSTRAINT IF EXISTS source_chunks_knowledge_base_id_source_id_chunk_index_key;

CREATE INDEX IF NOT EXISTS idx_source_chunks_kb_source_idx
    ON source_chunks (knowledge_base_id, source_id, chunk_index);

UPDATE source_chunks AS sc
SET status = 'active'
WHERE sc.status = 'stale'
  AND NOT EXISTS (
      SELECT 1
      FROM source_chunks AS active_chunk
      WHERE active_chunk.knowledge_base_id = sc.knowledge_base_id
        AND active_chunk.source_id = sc.source_id
        AND active_chunk.status = 'active'
  );
