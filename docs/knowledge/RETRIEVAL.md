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
query is also restricted to referenced documents, and a reference matches on any
of three forms: a document UUID, a document's `source_filename`, or a document's
`title`. `FakeRetriever` accepts the same three forms — see
[INGEST.md](./INGEST.md#the-local-adapter) — so a Scene resolves identically
against the in-memory adapter and the production one. The two ranked lists are
merged with Reciprocal Rank Fusion (RRF), using the constant `k = 60`:

```text
score(chunk) = sum(1 / (60 + rank_in_leg))
```

The final list is sorted by the fused score and truncated to `top_k`. A chunk
appearing in both legs receives both contributions, which rewards agreement
without requiring dense and lexical scores to have the same units.

## No index ships: neither HNSW nor a full-text index

Neither leg is served by an index that a migration creates, and the reason is
different for each.

- **The dense leg has no index at all.** The vector index is deliberately not
  created by a migration: its build cost depends on the amount of production
  data, so operators create it after the initial corpus is loaded (recommended
  threshold: about 50,000 chunks). See [HNSW index](#hnsw-index) below.
- **The text leg has no full-text index at all**, and this one is not a
  deliberate deferral. `to_tsvector('english', content)` is computed for every
  candidate row on every query. The knowledge migration
  (`alembic/versions/c2d3e4f5061_add_knowledge_documents_chunks.py`) creates
  three B-tree indexes — `ix_content_documents_org_id`, `idx_content_chunks_org`
  and `idx_content_chunks_doc` — and no GIN index. There is a GIN
  `to_tsvector` index in this schema, but it belongs to the older
  `content_articles` table (`idx_content_articles_fts`), not to
  `content_chunks`.

An earlier version of this manual said a GIN index served the text leg. None
does. On a corpus where the tenant filter narrows `content_chunks` to a few
thousand rows that is tolerable; on a large platform-wide corpus it is a
sequential scan per query. If text-leg latency matters, the fix is one
migration:

```sql
CREATE INDEX CONCURRENTLY idx_content_chunks_fts ON content_chunks
USING gin (to_tsvector('english', content));
```

That expression is the one the query computes, so the index is matched. Do
**not** add `WHERE org_id IS NOT NULL` to it; the next section explains why a
partial predicate is the wrong shape for this table.

## HNSW index

Run the following exact command against the application database:

```sql
CREATE INDEX CONCURRENTLY idx_content_chunks_embedding_hnsw ON content_chunks USING hnsw (embedding vector_cosine_ops);
```

`CONCURRENTLY` avoids taking an exclusive table lock while the index is built.

**The index must not be partial.** An earlier version of this runbook ended the
`CREATE INDEX` with `WHERE org_id IS NOT NULL`, and that predicate makes the
index unusable by the shipped query. A partial index is only a candidate for a
plan when the query's `WHERE` clause implies the index predicate, and
`content_chunks.org_id = :org_id OR content_chunks.org_id IS NULL` does not
imply `org_id IS NOT NULL` — the `IS NULL` branch admits exactly the
platform-wide rows the predicate excludes, and the planner has no proof that the
predicate is redundant. An operator who follows the old command ends up with an
index the planner never selects, and a vector search as slow as no index at all,
while this manual claimed retrieval was indexed.

Two ways to make a partial index usable; the second is a code change, not a
runbook change:

1. **Drop the predicate (recommended).** One full HNSW index, used by the query
   as written, and no coordination between the index and the code. The cost is
   that tenant and platform-wide chunks share one index; at the target scale
   (50k–500k chunks) that is the right trade, and it is the only option that
   cannot silently stop matching when the query changes.
2. **Split the query into an org-owned leg and a platform-wide leg**, so each
   leg's `WHERE` implies its own partial index. Two HNSW indexes, a `UNION ALL`,
   and two sets of ranks to feed the RRF accumulator. That is the correct fix if
   a partial index ever becomes necessary, and it belongs in
   `app/knowledge/retrieval/pgvector.py` together with a migration — never in
   the index definition alone.

This recommendation rests on the predicate/index-predicate disagreement described
above, **not** on a measured plan. No `EXPLAIN` has been run against a corpus
resembling production: the development database holds only the handful of rows
the integration tests ingest, at which size any plan is cheap and uninformative.
Before trusting either leg's cost in production, run
`EXPLAIN (ANALYZE, BUFFERS)` on both legs against a populated corpus and confirm
which index the planner picks.

Re-run the command only after a deliberate vector-model or index-version change,
and monitor the build in a migration/runbook window.
