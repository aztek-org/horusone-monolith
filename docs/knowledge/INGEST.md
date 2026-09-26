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

## A failed ingest leaves no audit row

This is the one thing about the path that is easy to assume and is not true.

`ingest()` catches an exception after `db.flush()` has given the `ContentDocument`
an id, adds a `failed` `IngestEvent` carrying the error text, and re-raises. It
does **not** commit. The caller owns the transaction, and the HTTP upload path's
session dependency does this on the way out:

```python
try:
    yield session
    await session.commit()
except Exception:
    await session.rollback()   # app/db/session.py
    raise
```

`ingest()` re-raises, so the dependency rolls back, and the `failed` row is
discarded along with the half-written document and its chunks. After a failed
upload, `ingest_events` contains **nothing at all** — not a `succeeded` row and
not a `failed` one. That is the right call for the document: a rolled-back
document is a document that never existed, and a `failed` row pointing at a
`content_documents` id that no longer exists would be a dangling reference.

It does mean **"every ingest is audited" is false today**, and the only durable
record of a failed upload is the application log. Two ways to change that, if the
audit trail is required:

1. Commit the failure event on its own connection, outside the caller's
   transaction — a second short-lived session that inserts only the
   `ingest_events` row. The document row must not be part of that transaction, so
   the `document_id` foreign key has to be satisfied by something, or made
   nullable for the failure case.
2. Keep the single transaction and make failure a recorded outcome rather than a
   raised one: return an `IngestResult(status="failed")` and let the caller
   decide. That changes the interface, so it is a real design decision rather
   than a bug fix.

Until one of those is done, an operator investigating "why did my upload not
appear" reads the log, not the table.

## The local adapter

`FakeRetriever` (`backend/app/knowledge/retrieval/fake.py`) is the in-process
retriever used outside production and for route tests. It is an in-memory list
with deterministic token-overlap scoring. It satisfies the same
`KnowledgeRetriever.search()` seam as `PgVectorRetriever`, and the two are held
to the same contract: both accept a `knowledge_refs` entry as a document UUID, a
source filename, or a document title, so a Scene that names a document by
filename resolves identically in development and in production. That parity is
asserted from both sides —
`backend/tests/unit/knowledge/test_retriever_reference_contract.py` covers the
fake, and `backend/tests/unit/knowledge/test_pgvector_retriever.py` asserts that
the pgvector compiled SQL carries `source_filename IN` and `title IN`.

There is **no Chroma in this repository.** Not in `backend/pyproject.toml`, not
in `backend/uv.lock`, not under `backend/app/`. A local vector store can be put
behind the same seam — persist the same chunk text, vector, organization,
publication, and citation offsets, then apply the same
tenant/publication/reference predicates before returning results — and it must
not become a second source of truth or bypass the query-level tenant gate. But
describing that as "the local adapter" describes an aspiration, not a shipped
adapter. Production remains PostgreSQL + pgvector, so the durable system of
record and the HNSW operator workflow stay centralized.
