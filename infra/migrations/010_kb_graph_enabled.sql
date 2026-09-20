-- Per-KB toggle: skip entity/relation maintenance when false.
-- Existing rows get TRUE when the column is first added; new inserts default to FALSE.
ALTER TABLE knowledge_bases
    ADD COLUMN IF NOT EXISTS graph_enabled BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE knowledge_bases
    ALTER COLUMN graph_enabled SET DEFAULT FALSE;
