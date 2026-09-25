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

2. **pgvector is the production adapter.** Chroma is the local and test adapter.
   Both satisfy the same interface, so both are real adapters and the seam is
   real rather than hypothetical.

3. **Ingest is a deep module.** One entry point accepts a document plus metadata
   and returns a result. Internally it extracts text, chunks with a fixed
   strategy, embeds with the LLM module, writes `content_chunks` rows, and
   records an ingest event. Callers never chunk, embed, or write vectors.

4. **Chunks are stored, not recomputed.** A `content_chunks` table holds
   `org_id`, `document_id`, `chunk_index`, `content`, `token_count`,
   `embedding vector(768)`, and citation coordinates (`page`, `section`,
   `char_start`, `char_end`). A GIN index serves the text leg; an HNSW index on
   the vector column serves the dense leg. Fixed chunking is 1000 tokens with
   150 tokens of overlap, recorded on the ingest event so a chunk can always be
   reproduced.

5. **Tenant isolation is enforced in the query, not in the caller.** Every
   retrieval query filters `(org_id = :org_id OR org_id IS NULL)`. This is
   asserted by a test that runs the same query for two organizations and checks
   that a private chunk never appears in the other tenant's results.

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
- Chroma remains available for local development and tests without becoming a
  production dependency.
- Citations are exact: page, section, and character coordinates per chunk.

### Negative

- Hybrid search is more code than pure full-text; `RRF` merging of two ranked
  lists is required.
- pgvector HNSW consumes memory; the index must be tuned per environment.
- Changing the embedding model requires a migration and a full re-ingest.

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
