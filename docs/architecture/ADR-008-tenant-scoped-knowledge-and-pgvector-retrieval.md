# ADR-008: Tenant-Scoped Knowledge and pgvector Retrieval

**Status**: Accepted
**Date**: 2026-09-25

## Context

Horus today stores Knowledge as Markdown `ContentArticle` rows in PostgreSQL
and searches them with `to_tsvector` plus an `ILIKE` fallback. There is no
ingest path, no embedding, no citation, and no tenant filter on the search
path. `backend/app/models/content.py` already carries `org_id IS NULL` meaning
"platform-wide", which is the right model for private tenant manuals versus
shared professional context.

The product requires every organization to upload its own manuals, SOPs, and
custom knowledge, and requires the ATC agents to cite what they used. We
considered three stores:

- **PostgreSQL + pgvector**: one database, one backup, ACID tenant isolation,
  existing `to_tsvector` full-text search. Strong for our scale
  (50k-500k chunks, tens of tenants).
- **Chroma**: pleasant local development experience, but weak multi-tenant
  isolation and awkward concurrent writes for production.
- **Qdrant**: excellent HNSW and payload filtering, but introduces a second
  production datastore, a second backup story, and a second failure mode before
  we have measured a need for it.

## Decision

1. **Retrieval lives behind one module interface.**

   ```python
   class KnowledgeRetriever(Protocol):
       async def search(self, query: RetrievalQuery) -> list[RetrievedChunk]: ...
   ```

   `RetrievalQuery` carries `query`, `org_id`, `top_k`, `knowledge_refs`, and
   `mode` (`hybrid` | `vector` | `text`). The interface is the test surface.

2. **pgvector is the production adapter.** `FakeRetriever`
   (`backend/app/knowledge/retrieval/fake.py`) is the other adapter: an
   in-memory list with deterministic token-overlap scoring, used outside
   production and for route tests. It satisfies the same interface, so the seam
   is real rather than hypothetical.

   > **Correction.** An earlier version of this decision named Chroma as the
   > local and test adapter, and this ADR's own manual named it too. There is
   > no Chroma in the repository: not in `backend/pyproject.toml`, not in
   > `backend/uv.lock`, not under `backend/app/`. The two retrieval adapters
   > that exist are the two named above. Putting a local vector store behind the
   > same seam is a legitimate future option — see
   > [INGEST.md](../knowledge/INGEST.md#the-local-adapter) — but describing it
   > as "the local adapter" described an aspiration as a shipped component.

   The two adapters are held to one contract, not two. A `knowledge_refs` entry
   resolves as a document UUID, a source filename, or a document title in
   **both**; that parity is what stops a Scene that resolves in production from
   silently returning nothing in development. It is asserted from both sides
   under `backend/tests/unit/knowledge/`.

3. **Ingest is a deep module.** One entry point accepts a document plus metadata
   and returns a result. Internally it extracts text, chunks with a fixed
   strategy, embeds with the LLM module, writes `content_chunks` rows, and
   records an ingest event. Callers never chunk, embed, or write vectors.

4. **Chunks are stored, not recomputed.** A `content_chunks` table holds
   `org_id`, `document_id`, `chunk_index`, `content`, `token_count`,
   `embedding vector(768)`, and citation coordinates (`page`, `section`,
   `char_start`, `char_end`). Fixed chunking is 1000 tokens with
   150 tokens of overlap, recorded on the ingest event so a chunk can always be
   reproduced.

   > **Correction: no index ships with this table.** The original text said "A
   > GIN index serves the text leg; an HNSW index on the vector column serves
   > the dense leg." No migration creates either. The knowledge migration
   > (`alembic/versions/c2d3e4f5061_add_knowledge_documents_chunks.py`) creates
   > three B-tree indexes — `ix_content_documents_org_id`,
   > `idx_content_chunks_org`, `idx_content_chunks_doc` — and its own docstring
   > defers HNSW to a later task, which added no migration. There is no GIN
   > index on `content_chunks` and no full-text index of any kind on it, so the
   > text leg computes `to_tsvector` over every candidate row on every query.
   > The GIN `to_tsvector` index that does exist in this schema,
   > `idx_content_articles_fts`, belongs to the older `content_articles` table.
   >
   > HNSW is a **deliberate operator step**, not an oversight;
   > [RETRIEVAL.md](../knowledge/RETRIEVAL.md#hnsw-index) is the authority on it,
   > including the rule that the index must **not** be partial, because the
   > shipped tenant predicate does not imply a `WHERE org_id IS NOT NULL`
   > predicate and the planner cannot therefore select such an index. The
   > missing text index is a gap rather than a deferral; the migration that
   > closes it is written out in
   > [RETRIEVAL.md](../knowledge/RETRIEVAL.md#no-index-ships-neither-hnsw-nor-a-full-text-index).

5. **Tenant isolation is enforced in the query, not in the caller.** Every
   retrieval query filters `(org_id = :org_id OR org_id IS NULL)`. This is
   asserted two ways. `backend/tests/unit/knowledge/test_pgvector_retriever.py`
   asserts the compiled SQL carries the predicate and the exact RRF arithmetic.
   `backend/tests/integration/test_retrieval_isolation.py` asserts the property
   against a real database, and — this is the part that matters — it first makes
   the result set **non-empty**: it ingests a platform-wide published document so
   the other tenant has a row it is allowed to see. An earlier version of that
   test asserted `all(result.org_id != org_a for result in results)` over a result
   set its own setup guaranteed was empty, so it passed unchanged even if
   `PgVectorRetriever.search` returned `[]` unconditionally — the exact failure
   it exists to catch. A `all(...)` over an empty iterable is not an assertion of
   a property.

6. **Publishing and quota are enforced at the ingest entry point.** A document
   must be explicitly published before its chunks become retrievable. Each
   organization has a configurable chunk quota. Uploading a document that
   exceeds quota fails before any embedding work begins.

7. **RAG first, fine-tuning later.** Fine-tuning is not introduced in v1. When
   it is introduced it will be a separate adapter behind a `ModelRegistry` seam
   and will be evaluated against a fixed aviation eval set before it is
   promoted. A fine-tuned model is never the sole source of a Citation.

## Consequences

### Positive

- One production datastore. One backup. One set of access controls.
- Full-text search keeps working; the vector leg is additive.
- `FakeRetriever` gives development and route tests a real retriever behind the
  same seam, with no second datastore to run.
- Citations are exact: page, section, and character coordinates per chunk.

### Negative

- Hybrid search is more code than pure full-text; `RRF` merging of two ranked
  lists is required.
- pgvector HNSW consumes memory; the index must be tuned per environment.
- Changing the embedding model requires a migration and a full re-ingest.
- **Neither retrieval leg is indexed out of the box.** The dense leg waits on an
  operator-built HNSW index, and the text leg has no index at all, so its cost
  grows linearly with the candidate set until the GIN index in
  [RETRIEVAL.md](../knowledge/RETRIEVAL.md#no-index-ships-neither-hnsw-nor-a-full-text-index)
  is added. This is a known, bounded, and documented gap, not a hidden one.

### Neutral

- `ContentArticle` is kept for human-readable articles; `content_documents` and
  `content_chunks` are the ingest and retrieval substrate.
- Qdrant remains a documented future option, triggered only by measured
  pgvector recall or latency failure at our target scale.

## References

- [ADR-002: Database Selection](./ADR-002-database-postgresql.md)
- [ADR-007: LLM Provider Adapters](./ADR-007-llm-provider-adapters.md)
- [ADR-009: OpenTelemetry and Postgres Trace](./ADR-009-opentelemetry-and-postgres-trace.md)
- Index: [ARCHITECTURE-INDEX.md](./ARCHITECTURE-INDEX.md)
