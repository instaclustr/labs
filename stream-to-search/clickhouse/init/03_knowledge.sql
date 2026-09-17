-- Knowledge base for the RAG module (instaclustr_sdk/rag.py).
--
-- Stores two kinds of documents as vector-embedded text, retrieved by cosine similarity:
--   * 'domain'  — domain-specific context on what an anomaly is / is not for an entity+metric
--   * 'finding' — memories of past anomaly findings (the AI agent writes these back)
--
-- Keeping the vector store in ClickHouse (alongside events/anomalies) stays true to the
-- "one seamless datastore" theme. `embedding` is an unsized Array(Float32) so any embedding
-- model works; cosineDistance() brute-forces over the (small, demo-sized) table.
-- NOTE: all rows must be embedded by the SAME model — mixing dimensions breaks cosineDistance.

CREATE TABLE IF NOT EXISTS knowledge
(
    id         UUID DEFAULT generateUUIDv4(),
    kind       Enum8('domain' = 1, 'finding' = 2),
    entity     String DEFAULT '',
    metric     String DEFAULT '',
    text       String,
    embedding  Array(Float32),
    created_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY (kind, entity, metric, created_at);
