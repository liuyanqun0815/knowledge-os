-- Scope source identity to knowledge base so the same path-derived id can exist in multiple KBs.
-- Live DBs may lack FKs on sources; drop them if present before changing the PK.

ALTER TABLE IF EXISTS source_texts DROP CONSTRAINT IF EXISTS source_texts_source_id_fkey;
ALTER TABLE IF EXISTS claim_evidence DROP CONSTRAINT IF EXISTS claim_evidence_source_id_fkey;
ALTER TABLE IF EXISTS events DROP CONSTRAINT IF EXISTS events_source_id_fkey;
ALTER TABLE IF EXISTS sources DROP CONSTRAINT IF EXISTS fk_sources_replaces_source;
ALTER TABLE IF EXISTS sources DROP CONSTRAINT IF EXISTS sources_replaces_source_id_fkey;
ALTER TABLE IF EXISTS source_texts DROP CONSTRAINT IF EXISTS source_texts_source_fkey;
ALTER TABLE IF EXISTS claim_evidence DROP CONSTRAINT IF EXISTS claim_evidence_source_fkey;
ALTER TABLE IF EXISTS events DROP CONSTRAINT IF EXISTS events_source_fkey;

ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_pkey;
ALTER TABLE sources ADD PRIMARY KEY (knowledge_base_id, id);

ALTER TABLE source_texts DROP CONSTRAINT IF EXISTS source_texts_pkey;
ALTER TABLE source_texts ADD PRIMARY KEY (knowledge_base_id, source_id);

ALTER TABLE source_texts
    ADD CONSTRAINT source_texts_source_fkey
    FOREIGN KEY (knowledge_base_id, source_id)
    REFERENCES sources (knowledge_base_id, id)
    ON DELETE CASCADE;

ALTER TABLE claim_evidence
    ADD CONSTRAINT claim_evidence_source_fkey
    FOREIGN KEY (knowledge_base_id, source_id)
    REFERENCES sources (knowledge_base_id, id);

ALTER TABLE events
    ADD CONSTRAINT events_source_fkey
    FOREIGN KEY (knowledge_base_id, source_id)
    REFERENCES sources (knowledge_base_id, id);

ALTER TABLE sources
    ADD CONSTRAINT fk_sources_replaces_source
    FOREIGN KEY (knowledge_base_id, replaces_source_id)
    REFERENCES sources (knowledge_base_id, id);
