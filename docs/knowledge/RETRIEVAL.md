# Knowledge retrieval

`PgVectorRetriever` provides a tenant-scoped retrieval seam for training
sessions. It supports `hybrid` (the default), `vector`, and `text` modes and
returns citation-ready chunks with document, page/section, and character span
metadata.

## Hybrid search and RRF

Hybrid search runs two independent legs against the same filtered candidate
set:

1. The dense leg embeds the query and orders by pgvector cosine distance:
   `ORDER BY embedding <=> :query_vec LIMIT :k`.
2. The text leg uses PostgreSQL `to_tsvector` / `to_tsquery` and orders by
   `ts_rank_cd DESC LIMIT :k`.

Both legs require `(org_id = :org_id OR org_id IS NULL)` and join
`content_documents.is_published IS TRUE`. If `knowledge_refs` is supplied, the
query is also restricted to referenced document UUIDs; Scene references that
are filenames or titles are accepted as the equivalent local reference form.
The two ranked lists are merged with Reciprocal Rank Fusion (RRF), using the
constant `k = 60`:

```text
score(chunk) = sum(1 / (60 + rank_in_leg))
```

The final list is sorted by the fused score and truncated to `top_k`. A chunk
appearing in both legs receives both contributions, which rewards agreement
without requiring dense and lexical scores to have the same units.

## HNSW index

The vector index is deliberately **not** created by Alembic. Its build cost
depends on the amount of production data, so operators create it after the
initial corpus is loaded (recommended threshold: about 50,000 chunks). Run the
following exact command against the application database:

```sql
CREATE INDEX CONCURRENTLY idx_content_chunks_embedding_hnsw ON content_chunks USING hnsw (embedding vector_cosine_ops) WHERE org_id IS NOT NULL;
```

`CONCURRENTLY` avoids taking an exclusive table lock while the index is built.
The partial predicate is intentional: organization-owned chunks are the main
private-tenant corpus, while platform-wide rows remain queryable through the
normal scan path. Re-run the command only after a deliberate vector-model or
index-version change, and monitor the build in a migration/runbook window.
