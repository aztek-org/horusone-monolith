# Knowledge ingest

The knowledge ingest path turns an uploaded document into searchable, cited
chunks. `KnowledgeIngestor.ingest()` is the single entry point for Markdown,
plain text, and PDF uploads. It extracts text, creates overlapping chunks,
embeds every chunk in one provider call, writes `content_chunks`, and records a
succeeded `ingest_events` audit row. It flushes but never commits; the request
or job transaction owns the commit.

## Supported formats

- `.md` / `.markdown`: UTF-8 Markdown. The first `# ` heading is retained as
  the chunk citation `section`.
- `.txt`: UTF-8 plain text.
- `.pdf`: UTF-8 text extracted with `pypdf`. Page text is joined in page order;
  v1 records page 1 as a coarse page hint. Per-page chunking is deferred until
  the PDF size policy is needed.

Unsupported extensions are rejected before persistence. The pypdf dependency
is pinned in `backend/pyproject.toml`.

## Chunking contract

The production chunking contract is a **1000-token window with a 150-token
overlap**. The tokenizer is a whitespace approximation and each span records
its original character offsets, so citations remain anchored to the extracted
source. Set the deployment's `KNOWLEDGE_CHUNK_SIZE=1000` and
`KNOWLEDGE_CHUNK_OVERLAP=150` to use that contract. The settings object remains
the source of truth; changing those values changes future ingestions only.

## Embedding dimension lock

`content_chunks.embedding` is a 768-dimensional pgvector. Every embedding
result is checked before any `ContentChunk` is written. A provider result with
another dimension raises the typed `EmbeddingDimensionMismatch` failure, so a
bad provider cannot leave partially embedded chunks behind. The model used is
recorded on every ingest event.

Changing the dimension is a deliberate data migration, not a configuration
rollout:

1. Choose a new dimension and add an Alembic migration that changes the
   `content_chunks.embedding` column to the new `Vector(n)` type.
2. Deploy the provider/model configuration and re-ingest every document.
3. Verify the new vectors and retrieval results, then remove old data using
   the migration's documented retention procedure.

Do not change `KNOWLEDGE_EMBEDDING_DIMENSIONS` alone: old 768-dimensional rows
cannot be compared with vectors from a different-dimensional model.

## Quotas and publication

The default chunk quota is checked before the embedding provider is called. A
rejected upload raises `QuotaExceeded` without paying for embeddings. The
current quota is the configured `KNOWLEDGE_DEFAULT_CHUNK_QUOTA`; it applies to
the organization scope being uploaded (`org_id IS NULL` is platform-wide).

Documents are private by default. `is_published=False` is always excluded by
retrieval, including searches made by the owning organization. Publishing is an
explicit ingest/API decision, not an implicit consequence of upload.

## Tenant isolation

A document and each of its chunks carry the same `org_id`. A retrieval query
always applies:

```sql
(content_chunks.org_id = :org_id OR content_chunks.org_id IS NULL)
```

and additionally requires the joined document to be published. A tenant can
therefore see its own chunks and platform-wide chunks, never another tenant's
chunks. This predicate belongs in the database query; callers must not be
trusted to perform isolation themselves.

## Chroma as a local adapter

`FakeRetriever` is the in-process adapter used outside production and for
route tests. Chroma can be used as a local development adapter behind the same
`KnowledgeRetriever.search()` seam: persist the same chunk text, vector,
organization, publication, and citation offsets in a local Chroma collection,
then apply the same tenant/publication/reference predicates before returning
results. Production remains PostgreSQL + pgvector so the durable system of
record and the HNSW operator workflow stay centralized. Chroma is not a second
source of truth and must not bypass the query-level tenant gate.
