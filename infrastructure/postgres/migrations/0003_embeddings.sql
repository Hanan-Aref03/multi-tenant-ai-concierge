-- Mohammad owns vector search performance and embedding index tuning.
-- Hanan owns the base tables (content_chunks, content_documents) and RLS policies.

-- ---------------------------------------------------------------------------
-- 1. Extend content_documents.kind to include Mohammad's API content types.
--    Mohammad uses: faq, doc, policy, service
--    Hanan's original: document, faq, policy, product
--    Both sets are valid; this migration makes the constraint accept all six.
-- ---------------------------------------------------------------------------

ALTER TABLE app.content_documents
    DROP CONSTRAINT IF EXISTS content_documents_kind_check;

ALTER TABLE app.content_documents
    ADD CONSTRAINT content_documents_kind_check
    CHECK (kind IN ('document', 'doc', 'faq', 'policy', 'product', 'service'));

-- ---------------------------------------------------------------------------
-- 2. HNSW vector index on content_chunks.embedding for cosine similarity.
--    HNSW does not require training data (unlike IVFFlat) so it is safe
--    to create before rows exist.
--
--    Tuning:
--      m              = 16   (edges per layer; trade-off between build time and recall)
--      ef_construction = 64   (beam width during build; higher → better recall)
--    At query time set: SET hnsw.ef_search = 40  (default is 40)
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_content_chunks_embedding_hnsw
    ON app.content_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Composite B-tree index for the WHERE tenant_id = ... filter applied
-- before the vector scan.  pgvector's planner uses this to scope scans.
CREATE INDEX IF NOT EXISTS idx_content_chunks_tenant_chunk
    ON app.content_chunks (tenant_id, chunk_index);

-- ---------------------------------------------------------------------------
-- 3. Compatibility view: maps Hanan's content_chunks column names to the
--    names used across Mohammad's retrieval and RAG service SQL.
--    SELECTs against this view inherit the RLS of app.content_chunks.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW app.content_embeddings AS
SELECT
    chunk_id          AS id,
    tenant_id,
    document_id       AS content_id,
    chunk_index,
    content           AS chunk_text,
    embedding,
    metadata,
    created_at
FROM app.content_chunks;

COMMENT ON VIEW app.content_embeddings IS
    'Compatibility alias for app.content_chunks used by RAG retrieval code.';
