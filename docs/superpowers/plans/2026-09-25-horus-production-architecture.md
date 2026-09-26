# Horus Production Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the MVP into a tenant-scoped, traceable, configuration-driven platform with a persistent multi-agent Session module, a versioned Scene, a pgvector knowledge ingest/retrieval path, and vendor-neutral LLM adapters.

**Architecture:** Three deep modules sit behind narrow interfaces: a **Session** module (start / send / end / snapshot, backed by a LangGraph checkpointer), a **Knowledge** module (ingest one document, search knowledge, pgvector + `to_tsvector` hybrid), and an **LLM** module (`generate` / `embed`, Ollama default, Groq fallback, `fake` in tests). A **Scene** registry versions prompts and per-Scene model constraints. Every Session step appends a `TrainingSessionEvent` carrying provenance (`scene_version`, `prompt_version`, `llm_provider`, `retrieved_chunk_ids`, `instructor_overridden`). Operational telemetry is OpenTelemetry over structured logs; product trace is PostgreSQL. No LangSmith, no Chroma in production, no fine-tuning in v1.

**Tech Stack:** Python 3.10+ / FastAPI / SQLAlchemy 2 async / Alembic / PostgreSQL 16 + pgvector / LangGraph + LangChain Community + LangGraph checkpoint-postgres / pydantic-settings / OpenTelemetry / pytest

**Spec:**
- `CONTEXT.md` (Scene, Session, Flight Plan, Knowledge Document, Knowledge Chunk, Citation, Provenance, Collaborator, Platform-Wide Knowledge)
- `docs/architecture/ADR-006-scene-session-and-persistent-langgraph.md`
- `docs/architecture/ADR-007-llm-provider-adapters.md`
- `docs/architecture/ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md`
- `docs/architecture/ADR-009-opentelemetry-and-postgres-trace.md`
- Existing: `docs/architecture/ADR-002-database-postgresql.md`, `ADR-004-langgraph-multi-agent.md`, `ADR-005-flight-plan-pipeline.md`

## Global Constraints

- Python floor stays `py310` (`backend/pyproject.toml` `ruff.target-version`); do not raise it in this plan.
- `Settings` is the only place environment variables are read. No `os.getenv` / `os.environ` in application code. No `if environment == "production"` branches in routers or graph nodes.
- No host-specific URL may be a default in `Settings`. Localhost values live in `.env.example`, `.env.docker.example`, `.env.prod.example`; `Settings` raises at startup when a required value is missing in `production`.
- LLM provider is selected by `LLM_PROVIDER` (`ollama` | `groq` | `nvidia-nim` | `fake`). Default adapter for production is `ollama`; tests use `fake`. No provider `if` branches in graph nodes or agents.
- `temperature`, `max_output_tokens`, and prompt text belong to the versioned Scene config. No literal temperature in `backend/app/services/llm/` after Task 2.
- Canonical embedding is `nomic-embed-text`, 768 dimensions. The dimension is stored on every ingest event and asserted on every ingest and retrieval.
- Retrieval queries always filter `org_id = :org_id OR org_id IS NULL`. This is asserted by a two-tenant test, not left to callers.
- Chunking is fixed: 1000 tokens, 150 token overlap, recorded on the ingest event.
- LangGraph `thread_id` is `f"{org_id}:{session_id}"`. Any Session operation without `org_id` is rejected in production.
- Session provenance lives in `training_session_events.event_payload`. Replay remains the single read seam.
- `LLM_ALLOW_EXTERNAL_FALLBACK` must be `false` in `.env.prod.example`. Private-tenant Scenes must not fall back to an external provider.
- No dependency on LangSmith, Langfuse, Chroma, or Qdrant at runtime. Chroma appears only as a test/local adapter in Task 8.
- Existing tests must keep passing unless a task explicitly rewrites them.
- All commands are run from `backend/` with `.venv/bin/pytest`, `.venv/bin/ruff`, `.venv/bin/alembic`.
- New Alembic revisions descend from `dcc247c7ad05` (current single head).
- Every task ends with a commit. Commit messages use Conventional Commits.
- ADR references: when a task changes graph construction, session storage, provider selection, retrieval, or tracing, update the "References" section of the affected ADR in the same commit.

## Review Focus

- **Cross-tenant leakage:** a private Knowledge Chunk from org A must never appear in org B's retrieval results, even when org B has no chunks of its own and even when the query text matches exactly.
- **Restart mid-Session:** killing the backend between two transmissions must not lose the Session; the next `send` must resume the same `thread_id` and continue the exchange counter.
- **External fallback for private knowledge:** if `LLM_PROVIDER=ollama` fails and `LLM_FALLBACK_PROVIDER=groq` but `LLM_ALLOW_EXTERNAL_FALLBACK=false`, the call must raise a typed error and the provenance must record `llm_fallback_used=false` and `llm_error`; no prompt may leave the VPS.
- **Unpublished and over-quota documents:** a document that is not published, or whose estimated chunk count exceeds the org quota, must produce zero retrievable chunks and a `422`/`409`, not a partial ingest.
- **Voice-only Session with no Scene:** connecting to `/ws/voice` without a Scene must still work. The Session module must accept a default Scene and record `scene_version="default-v1"`; it must not require a Scene row.
- **Dimension mismatch:** ingesting with an embedder that returns 384 dimensions against a `vector(768)` column must fail at ingest with a typed error and leave zero rows written.

---

## File Structure

New files and their single responsibility:

```
CONTEXT.md                                                     (done) domain glossary
docs/architecture/ADR-006-scene-session-and-persistent-langgraph.md   (done)
docs/architecture/ADR-007-llm-provider-adapters.md             (done)
docs/architecture/ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md (done)
docs/architecture/ADR-009-opentelemetry-and-postgres-trace.md  (done)
docs/knowledge/INGEST.md                                      ingest operator manual
docs/knowledge/RETRIEVAL.md                                   retrieval + hybrid ranking manual
docs/architecture/scene-config.example.yaml                    example versioned Scene config

backend/app/config.py                                         MODIFIED grouped Settings
backend/app/settings_loader.py                                CREATE fail-fast env resolution for non-Docker deployments

backend/app/llm/__init__.py                                   CREATE
backend/app/llm/types.py                                      CREATE GenerationRequest/Result, EmbeddingResult, LLMModule Protocol
backend/app/llm/adapters/__init__.py                          CREATE
backend/app/llm/adapters/ollama_adapter.py                    CREATE OllamaAdapter
backend/app/llm/adapters/groq_adapter.py                      CREATE GroqAdapter
backend/app/llm/adapters/fake_adapter.py                      CREATE FakeAdapter (tests + local)
backend/app/llm/adapters/nvidia_nim_adapter.py                CREATE NvidiaNIMAdapter (OpenAI-compatible)
backend/app/llm/routing.py                                    CREATE FallbackLLM + build_llm()
backend/app/llm/scene_constraints.py                          CREATE SceneConstraints dataclass + merge()

backend/app/knowledge/__init__.py                             CREATE
backend/app/knowledge/types.py                                CREATE DocumentUpload, IngestResult, Citation, RetrievalQuery, RetrievedChunk, KnowledgeRetriever Protocol
backend/app/knowledge/chunking.py                              CREATE chunk_document()
backend/app/knowledge/documents.py                            CREATE extract_text() + Markdown/PDF/TXT loaders
backend/app/knowledge/ingest.py                                CREATE KnowledgeIngestor
backend/app/knowledge/retrieval/pgvector.py                   CREATE PgVectorRetriever
backend/app/knowledge/retrieval/fake.py                       CREATE FakeRetriever (tests + local)
backend/app/knowledge/retrieval/__init__.py                   CREATE build_retriever()
backend/app/models/knowledge_document.py                      CREATE ContentDocument, ContentChunk, IngestEvent
backend/app/schemas/knowledge.py                              CREATE Citation/RetrievedChunk schemas (Task 6) + upload/search schemas (Task 8)
backend/app/schemas/scene.py                                  CREATE Scene config schemas
backend/app/services/training_sessions/__init__.py            CREATE
backend/app/services/training_sessions/types.py               CREATE commands, results, SessionModule Protocol
backend/app/services/training_sessions/session_store.py       CREATE SessionStore Protocol + InMemorySessionStore
backend/app/services/training_sessions/postgres_session_store.py CREATE PostgresSessionStore (LangGraph checkpointer)
backend/app/services/training_sessions/graphs.py              CREATE build_validation_graph/build_live_session_graph/build_scoring_graph factories (no globals)
backend/app/services/training_sessions/session_module.py      CREATE TrainingSessionModule implementation
backend/app/services/training_sessions/trace.py               CREATE TraceRecorder Protocol + SqlAlchemyTraceRecorder
backend/app/services/llm/scenes/__init__.py                   CREATE scene registry loader
backend/app/services/llm/scenes/registry.py                   CREATE SceneRegistry
backend/app/services/llm/scenes/default_scene.py              CREATE DEFAULT_SCENE config
backend/app/services/llm/atc_agent.py                         MODIFY accepts injected LLMModule; keeps class name for audio pipeline
backend/app/services/llm/orchestrator.py                      DELETE (replaced by session module)
backend/app/services/llm/graphs/live_session_graph.py         MODIFY no module global; takes llm param
backend/app/services/llm/prompts.py                           MODIFY templates as Jinja-free format files loaded from scene config
backend/app/api/v1/sessions.py                                MODIFY use session module from request.app.state; provenance in replay
backend/app/api/v1/knowledge.py                               CREATE upload/search/ingest-status routes
backend/app/api/v1/scenes.py                                  CREATE scene read routes
backend/app/api/routes/voice.py                               MODIFY use session module; bind voice WS to a db session
backend/app/main.py                                           MODIFIED composition root
backend/app/models/__init__.py                                MODIFIED import new models (Alembic autogenerate target)
backend/alembic/versions/b1c2d3e4f506_add_pgvector_extension.py CREATE
backend/alembic/versions/c2d3e4f5061_add_knowledge_documents_chunks.py CREATE
backend/alembic/versions/d3e4f506172_add_langgraph_checkpointer.py CREATE
backend/alembic/versions/f5061728394_add_trace_retention_config.py CREATE
backend/scripts/prune_session_events.py                       CREATE daily retention job
backend/pyproject.toml                                        MODIFIED dependencies
backend/docker-compose.yml                                    MODIFIED pgvector image; env additions
backend/.env.example, .env.docker.example, .env.prod.example  MODIFIED
backend/tests/... (per task below)
```

Deleted files: `backend/app/services/llm/orchestrator.py` only.

---

### Task 1: Grouped configuration and fail-fast environment resolution

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/settings_loader.py`
- Modify: `backend/.env.example`, `backend/.env.docker.example`, `backend/.env.prod.example`
- Test: `backend/tests/unit/test_config.py`, `backend/tests/unit/test_settings_loader.py`
- Modify: `backend/app/main.py` (call loader at import)

**Interfaces:**
- Consumes: nothing.
- Produces:
  ```python
  # app/config.py
  @dataclass(frozen=True) class LLMSettings: provider: str; fallback_provider: str | None; base_url: str; model: str; embedding_model: str; api_key: str | None; temperature: float; max_output_tokens: int; timeout_seconds: float; allow_external_fallback: bool
  @dataclass(frozen=True) class KnowledgeSettings: chunk_size: int; chunk_overlap: int; embedding_dimensions: int; top_k: int; default_chunk_quota: int
  @dataclass(frozen=True) class TraceSettings: retention_days: int; otel_endpoint: str | None; log_level: str
  class Settings(BaseSettings):
      environment: Literal["development", "testing", "production"]
      host: str; port: int
      database_url: str; redis_url: str
      cors_origins: str; auth_enabled: bool
      keycloak_issuer_url: str; keycloak_jwks_url: str; keycloak_client_id: str
      llm: LLMSettings
      knowledge: KnowledgeSettings
      trace: TraceSettings
      audio: AudioSettings       # sample_rate, chunk_size, audio_format, enable_radio_effects, noise_level, static_level
      whisper_model: str; whisper_language: str; tts_language: str
      def cors_origins_list(self) -> list[str]: ...
      def resolved_jwks_url(self) -> str: ...
      def accepted_keycloak_issuers(self) -> set[str]: ...
      def model_post_init(self) -> None: ...   # production validation
  def get_settings() -> Settings   # @lru_cache

  # app/settings_loader.py
  def load_settings(env_file: str | Path) -> Settings:
      """Build Settings from env_file plus OS env; raises MissingSettingError in production."""
  class MissingSettingError(RuntimeError): ...
  ```
  Env var names (all validated in `production` by `model_post_init`): `ENVIRONMENT`, `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS`, `KEYCLOAK_ISSUER_URL`, `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_EMBEDDING_MODEL`, `LLM_TEMPERATURE`, `LLM_MAX_OUTPUT_TOKENS`, `LLM_TIMEOUT_SECONDS`, `LLM_ALLOW_EXTERNAL_FALLBACK`, `LLM_FALLBACK_PROVIDER` (optional), `LLM_FALLBACK_API_KEY` (optional), `KNOWLEDGE_CHUNK_SIZE`, `KNOWLEDGE_CHUNK_OVERLAP`, `KNOWLEDGE_EMBEDDING_DIMENSIONS`, `KNOWLEDGE_TOP_K`, `KNOWLEDGE_DEFAULT_CHUNK_QUOTA`, `TRACE_RETENTION_DAYS`, `OTEL_EXPORTER_OTLP_ENDPOINT` (optional).

- [ ] **Step 1: Write the failing grouped-settings tests**

  Add to `backend/tests/unit/test_config.py`:

  ```python
  def test_grouped_llm_settings() -> None:
      settings = Settings(
          environment="testing",
          llm={"provider": "ollama", "base_url": "http://ollama:11434", "model": "llama3.2:3b",
               "embedding_model": "nomic-embed-text", "temperature": 0.3, "max_output_tokens": 150},
      )
      assert settings.llm.provider == "ollama"
      assert settings.llm.temperature == 0.3
      assert settings.knowledge.embedding_dimensions == 768


  def test_production_requires_explicit_database_url() -> None:
      with pytest.raises(MissingSettingError, match="DATABASE_URL"):
          load_settings(env_file=write_env(tmp_path, ""))  # helper writes a file with only ENVIRONMENT=production


  def test_production_rejects_external_fallback_true() -> None:
      env = {"ENVIRONMENT": "production", "DATABASE_URL": "postgresql+asyncpg://x/y",
             "REDIS_URL": "redis://x", "CORS_ORIGINS": "https://app.example",
             "KEYCLOAK_ISSUER_URL": "https://auth.example/realms/horus",
             "LLM_PROVIDER": "ollama", "LLM_BASE_URL": "http://ollama:11434", "LLM_MODEL": "llama3.2:3b",
             "LLM_EMBEDDING_MODEL": "nomic-embed-text",
             "LLM_ALLOW_EXTERNAL_FALLBACK": "true", "LLM_FALLBACK_PROVIDER": "groq"}
      with pytest.raises(MissingSettingError, match="external fallback"):
          load_settings(env_file=write_env(tmp_path, env))


  def test_no_hostname_defaults() -> None:
      src = Path("app/config.py").read_text()
      assert "localhost" not in src and "0.0.0.0" not in src
  ```

  Create `backend/tests/unit/test_settings_loader.py` with a `write_env(tmp_path, mapping)` helper that writes each `k=v` pair to `tmp_path / ".env"`.

- [ ] **Step 2: Run the tests to verify they fail**

  Run: `cd backend && .venv/bin/pytest tests/unit/test_config.py tests/unit/test_settings_loader.py -q`
  Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'llm'` and `ImportError: cannot import name 'MissingSettingError'`.

- [ ] **Step 3: Rewrite `backend/app/config.py` with grouped settings**

  Replace the flat `Settings` class with the dataclasses and `Settings` listed in **Interfaces**. Required fields are declared with `Field(...)` (no default) so pydantic raises when absent; the loader supplies `.env` values in development, and `model_post_init` raises `MissingSettingError` listing every missing production key at once. Keep `get_settings()` as `@lru_cache`. Keep `cors_origins_list`, `resolved_jwks_url`, `accepted_keycloak_issuers` behavior identical to today (wildcard CORS blocked in production, dev issuer aliases only in development/testing).

- [ ] **Step 4: Write `backend/app/settings_loader.py`**

  ```python
  """Fail-fast environment resolution for non-Docker deployments."""
  from __future__ import annotations
  import os
  from pathlib import Path
  from pydantic import ValidationError
  from app.config import Settings


  class MissingSettingError(RuntimeError):
      """Raised when production settings are incomplete."""


  REQUIRED_IN_PRODUCTION = (
      "DATABASE_URL", "REDIS_URL", "CORS_ORIGINS", "KEYCLOAK_ISSUER_URL",
      "LLM_PROVIDER", "LLM_BASE_URL", "LLM_MODEL", "LLM_EMBEDDING_MODEL",
  )


  def load_settings(env_file: str | Path) -> Settings:
      data: dict[str, str] = {}
      path = Path(env_file)
      if path.exists():
          for line in path.read_text().splitlines():
              line = line.strip()
              if not line or line.startswith("#") or "=" not in line:
                  continue
              key, value = line.split("=", 1)
              data[key.strip()] = value.strip()
      data.update({k: v for k, v in os.environ.items() if v})
      if data.get("ENVIRONMENT") == "production":
          missing = [k for k in REQUIRED_IN_PRODUCTION if not data.get(k)]
          if missing:
              raise MissingSettingError(f"Missing production settings: {', '.join(missing)}")
      try:
          return Settings(**data)
      except ValidationError as exc:
          if data.get("ENVIRONMENT") == "production":
              raise MissingSettingError(str(exc)) from exc
          raise
  ```

  Wire `app/main.py` to call `load_settings` when `ENV_FILE` is set: `settings = get_settings()` stays, and at module import add
  `if os.getenv("ENV_FILE"): from app.settings_loader import load_settings; settings = load_settings(os.environ["ENV_FILE"])`.

- [ ] **Step 5: Update the three `.env*.example` files**

  `.env.example`: add the new `LLM_*`, `KNOWLEDGE_*`, `TRACE_RETENTION_DAYS` keys with localhost values. `.env.prod.example`: set `ENVIRONMENT=production`, `LLM_ALLOW_EXTERNAL_FALLBACK=false`, `LLM_FALLBACK_PROVIDER=`, real `CORS_ORIGINS` placeholder, and add a comment block explaining that Groq fallback is possible only by explicitly setting `LLM_ALLOW_EXTERNAL_FALLBACK=true` and that doing so sends prompts off the VPS. `.env.docker.example`: add `LLM_BASE_URL=http://ollama:11434`, `LLM_FALLBACK_PROVIDER=groq`, `GROQ_API_KEY` placeholder.

- [ ] **Step 6: Run tests to verify they pass**

  Run: `cd backend && .venv/bin/pytest tests/unit/test_config.py tests/unit/test_settings_loader.py -q && .venv/bin/ruff check app/config.py app/settings_loader.py`
  Expected: PASS.

- [ ] **Step 7: Commit**

  ```bash
  git add backend/app/config.py backend/app/settings_loader.py backend/app/main.py backend/.env.example backend/.env.docker.example backend/.env.prod.example backend/tests/unit/test_config.py backend/tests/unit/test_settings_loader.py
  git commit -m "refactor(config): group settings and fail fast in production"
  ```

---

### Task 2: LLM module with Ollama, Groq, NVIDIA NIM, and fake adapters

**Files:**
- Create: `backend/app/llm/__init__.py`, `types.py`, `adapters/*`, `routing.py`, `scene_constraints.py`
- Modify: `backend/pyproject.toml` (add `langchain-groq>=0.3.0,<1.0.0`), `backend/uv.lock` (regenerate)
- Test: `backend/tests/unit/llm/test_routing.py`, `backend/tests/unit/llm/test_adapters.py`, `backend/tests/unit/llm/__init__.py`

**Interfaces:**
- Consumes: `app.config.Settings.llm`.
- Produces:
  ```python
  # app/llm/types.py
  GenerationPurpose = Literal["atc_response", "weather_briefing", "student_evaluation",
                            "flight_plan_parse", "readback_evaluation", "knowledge_embedding"]
  @dataclass(frozen=True) class SceneConstraints: temperature: float | None = None; max_output_tokens: int | None = None
  @dataclass(frozen=True) class GenerationRequest: prompt: str; purpose: GenerationPurpose; scene_constraints: SceneConstraints = SceneConstraints(); language: str = "en"
  @dataclass(frozen=True) class GenerationResult: text: str; provider: str; model: str; fallback_used: bool
  @dataclass(frozen=True) class EmbeddingResult: vectors: list[list[float]]; provider: str; model: str; dimensions: int
  class LLMModule(Protocol):
      async def generate(self, request: GenerationRequest) -> GenerationResult: ...
      async def embed(self, texts: list[str]) -> EmbeddingResult: ...
  class LLMTransientError(RuntimeError): """Provider timed out or returned 5xx; eligible for fallback."""
  class LLMUsageError(RuntimeError): """Provider rejected the request; not eligible for fallback."""
  # app/llm/routing.py
  def build_llm(settings: Settings) -> LLMModule: ...
  class FallbackLLM:  # implements LLMModule
      def __init__(self, primary: LLMModule, fallback: LLMModule | None, allow_external_fallback: bool) -> None: ...
  # app/llm/adapters/fake_adapter.py
  class FakeAdapter:  # deterministic; generate returns "Say again, transmission unclear." unless prompt contains a marker
  # app/llm/adapters/ollama_adapter.py
  class OllamaAdapter: def __init__(self, settings: LLMSettings) -> None
  # app/llm/adapters/groq_adapter.py
  class GroqAdapter: def __init__(self, settings: LLMSettings) -> None   # raises LLMUsageError at build if api_key missing
  # app/llm/adapters/nvidia_nim_adapter.py
  class NvidiaNIMAdapter: def __init__(self, settings: LLMSettings) -> None  # OpenAI-compatible chat completions
  ```
  `FallbackLLM.generate` tries primary; on `LLMTransientError`, if `fallback is None` or `not allow_external_fallback` or `fallback.provider_is_external` it re-raises the primary error wrapped in `LLMUnavailableError` (which carries `fallback_attempted: bool`); otherwise it returns the fallback result with `fallback_used=True`. `embed` never falls back (embedding models differ); it raises `LLMUnavailableError` on transient failure.

- [ ] **Step 1: Write failing routing tests**

  Create `backend/tests/unit/llm/test_routing.py`:

  ```python
  from dataclasses import dataclass
  import pytest
  from app.llm.routing import FallbackLLM, LLMTransientError, LLMUnavailableError
  from app.llm.types import GenerationRequest

  class Flaky:
      provider_is_external = False
      def __init__(self, exc): self.exc = exc
      async def generate(self, request): raise self.exc
      async def embed(self, texts): return None

  class Working:
      provider_is_external = True
      async def generate(self, request):
          from app.llm.types import GenerationResult
          return GenerationResult(text="ok", provider="groq", model="m", fallback_used=False)
      async def embed(self, texts): return None

  REQ = GenerationRequest(prompt="p", purpose="atc_response")

  @pytest.mark.asyncio
  async def test_fallback_used_when_allowed():
      llm = FallbackLLM(Flaky(LLMTransientError("timeout")), Working(), allow_external_fallback=True)
      result = await llm.generate(REQ)
      assert result.fallback_used is True and result.text == "ok"

  @pytest.mark.asyncio
  async def test_fallback_blocked_when_disallowed():
      llm = FallbackLLM(Flaky(LLMTransientError("timeout")), Working(), allow_external_fallback=False)
      with pytest.raises(LLMUnavailableError) as info:
          await llm.generate(REQ)
      assert info.value.fallback_attempted is False

  @pytest.mark.asyncio
  async def test_external_fallback_blocked_even_when_allowed():
      llm = FallbackLLM(Flaky(LLMTransientError("timeout")), Working(), allow_external_fallback=True)
      llm.fallback.provider_is_external = True
      with pytest.raises(LLMUnavailableError):
          await llm.generate(REQ)

  @pytest.mark.asyncio
  async def test_embed_never_falls_back():
      llm = FallbackLLM(Flaky(LLMTransientError("timeout")), Working(), allow_external_fallback=True)
      with pytest.raises(LLMUnavailableError):
          await llm.embed(["a"])
  ```

- [ ] **Step 2: Run to verify failure**

  Run: `cd backend && .venv/bin/pytest tests/unit/llm/test_routing.py -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'app.llm'`.

- [ ] **Step 3: Write `backend/app/llm/types.py`, `scene_constraints.py`, `fake_adapter.py`**

  `types.py` holds the dataclasses, `GenerationPurpose`, the `LLMModule` Protocol, and the error classes. `scene_constraints.py` holds `SceneConstraints` and:

  ```python
  def merge(base: SceneConstraints, override: SceneConstraints) -> SceneConstraints:
      return SceneConstraints(
          temperature=override.temperature if override.temperature is not None else base.temperature,
          max_output_tokens=override.max_output_tokens if override.max_output_tokens is not None else base.max_output_tokens,
      )
  ```

  `FakeAdapter.embed` returns `[[0.0] * 768 for _ in texts]` with `dimensions=768`; `generate` returns `GenerationResult(text="Say again, transmission unclear.", provider="fake", model="fake", fallback_used=False)` and records calls in `self.calls` for assertions.

- [ ] **Step 4: Write `backend/app/llm/routing.py`**

  ```python
  def build_llm(settings: Settings) -> LLMModule:
      from app.llm.adapters.fake_adapter import FakeAdapter
      from app.llm.adapters.groq_adapter import GroqAdapter
      from app.llm.adapters.nvidia_nim_adapter import NvidiaNIMAdapter
      from app.llm.adapters.ollama_adapter import OllamaAdapter
      factories = {"ollama": OllamaAdapter, "groq": GroqAdapter, "nvidia-nim": NvidiaNIMAdapter, "fake": FakeAdapter}
      llm = settings.llm
      if llm.provider not in factories:
          raise ValueError(f"Unknown LLM_PROVIDER {llm.provider!r}")
      primary = factories[llm.provider](llm)
      fallback = None
      if llm.fallback_provider and llm.provider != llm.fallback_provider:
          fallback = factories[llm.fallback_provider](llm)
      return FallbackLLM(primary, fallback, allow_external_fallback=llm.allow_external_fallback)
  ```

  `FallbackLLM` keeps `self.primary`, `self.fallback`; exposes a read-only `provider` property returning the primary adapter's provider name (used by `main.py` and tests); sets `fallback_attempted` on the raised `LLMUnavailableError`; exposes `provider_is_external = True` only if the primary is `groq` or `nvidia-nim`.

- [ ] **Step 5: Write `ollama_adapter.py`, `groq_adapter.py`, `nvidia_nim_adapter.py`**

  `OllamaAdapter.generate` constructs `langchain_community.llms.Ollama(base_url=settings.base_url, model=settings.model, temperature=..., num_predict=...)` once in `__init__` (not per call) and wraps `asyncio.TimeoutError` and `httpx.TransportError` in `LLMTransientError`; other exceptions become `LLMUsageError`. `embed` calls `ollama.Client(settings.base_url).embed(model=settings.embedding_model, input=texts)` and returns `EmbeddingResult`. `GroqAdapter` uses `langchain_groq.ChatGroq(api_key=..., model=..., max_retries=0, timeout=settings.timeout_seconds)`; `NvidiaNIMAdapter` uses `httpx.AsyncClient` against `{base_url}/v1/chat/completions` and `{base_url}/v1/embeddings` with `Authorization: Bearer`. Each adapter raises `LLMUsageError` naming **its own** missing credential at `__init__` — `GROQ_API_KEY is required` for Groq, `NVIDIA_NIM_API_KEY is required` for NVIDIA NIM. (Corrected 2026-09-25: the plan originally mandated the Groq string for both, which sent operators to the wrong provider's configuration.)

- [ ] **Step 6: Add dependency and adapter tests**

  `cd backend && .venv/bin/python -m pip show langchain-groq || uv add 'langchain-groq>=0.3.0,<1.0.0'`. Create `backend/tests/unit/llm/test_adapters.py` asserting: `OllamaAdapter` builds with `LLMSettings(provider="ollama", base_url="http://x:11434", model="m", embedding_model="nomic-embed-text", temperature=0.3, max_output_tokens=150, timeout_seconds=30.0, allow_external_fallback=False, fallback_provider=None, api_key=None)`; `GroqAdapter` raises `LLMUsageError` without `api_key`; `FakeAdapter.embed(["a","b"])` returns two 768-dim vectors.

- [ ] **Step 7: Run to verify pass**

  Run: `cd backend && .venv/bin/pytest tests/unit/llm -q && .venv/bin/ruff check app/llm`
  Expected: PASS.

- [ ] **Step 8: Commit**

  ```bash
  git add backend/app/llm backend/pyproject.toml backend/uv.lock backend/tests/unit/llm
  git commit -m "feat(llm): add provider adapters and fallback router"
  ```

---

### Task 3: pgvector extension and `content_documents` / `content_chunks`

**Files:**
- Create: `backend/alembic/versions/b1c2d3e4f506_add_pgvector_extension.py`
- Create: `backend/alembic/versions/c2d3e4f5061_add_knowledge_documents_chunks.py`
- Modify: `backend/docker-compose.yml` (`postgres` service image → `pgvector/pgvector:pg16`)
- Create: `backend/app/models/knowledge_document.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/integration/test_knowledge_models.py` (requires running Postgres; skipped when `DATABASE_URL` is unset)

**Interfaces:**
- Consumes: nothing from Task 2.
- Produces ORM classes:
  ```python
  class ContentDocument(Base):
      __tablename__ = "content_documents"
      id: UUID pk; org_id: UUID | None (FK organizations.id, nullable=True, index)   # None = platform-wide
      title: str(500); source_filename: str(500); source_type: str(20)              # "markdown" | "pdf" | "text"
      content_hash: str(64)                                                        # sha256 of extracted text
      is_published: bool default False
      ingested_at: datetime | None; chunk_count: int default 0
      created_by: UUID | None (FK users.id)
      ingest_events: relationship(IngestEvent)
      chunks: relationship(ContentChunk)
  class ContentChunk(Base):
      __tablename__ = "content_chunks"
      __table_args__ = (Index("idx_content_chunks_org", "org_id"),
                        Index("idx_content_chunks_doc", "document_id", "chunk_index"))
      id: UUID pk; document_id: UUID FK content_documents.id ondelete CASCADE
      org_id: UUID | None; chunk_index: int; content: Text
      token_count: int; embedding: Vector(768)
      page: int | None; section: str | None; char_start: int; char_end: int
  class IngestEvent(Base):
      __tablename__ = "ingest_events"
      id: UUID pk; document_id: UUID FK; org_id: UUID | None
      status: str(20)                       # "succeeded" | "failed"
      embedding_model: str(100); embedding_dimensions: int
      chunk_size: int; chunk_overlap: int; chunk_count: int
      error: str | None; created_at: datetime server_default now()
  ```
  `pgvector/sqlalchemy.Vector` is used; `pgvector` is added to `backend/pyproject.toml`.

- [ ] **Step 1: Write the failing integration test**

  Create `backend/tests/integration/test_knowledge_models.py`:

  ```python
  import os, uuid
  import pytest
  from sqlalchemy import select
  from pgvector.sqlalchemy import Vector
  from app.db.session import get_session_factory
  from app.models.knowledge_document import ContentDocument, ContentChunk, IngestEvent

  pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="needs Postgres")

  @pytest.mark.asyncio
  async def test_chunk_roundtrip():
      factory = get_session_factory()
      async with factory() as db:
          doc = ContentDocument(title="Manual", source_filename="m.md", source_type="markdown",
                                content_hash="a" * 64, is_published=True, chunk_count=1)
          db.add(doc); await db.flush()
          db.add(ContentChunk(document_id=doc.id, org_id=None, chunk_index=0, content="x",
                              token_count=1, embedding=[0.0] * 768, char_start=0, char_end=1))
          db.add(IngestEvent(document_id=doc.id, org_id=None, status="succeeded",
                             embedding_model="nomic-embed-text", embedding_dimensions=768,
                             chunk_size=1000, chunk_overlap=150, chunk_count=1))
          await db.commit()
          rows = (await db.execute(select(ContentChunk).where(ContentChunk.document_id == doc.id))).scalars().all()
          assert len(rows) == 1 and len(rows[0].embedding) == 768
  ```

- [ ] **Step 2: Run to verify failure**

  Run: `cd backend && DATABASE_URL=postgresql+asyncpg://horus:horus@localhost:5432/horus_db .venv/bin/pytest tests/integration/test_knowledge_models.py -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'pgvector'`.

- [ ] **Step 3: Add dependency and Docker image**

  `cd backend && uv add 'pgvector>=0.3.6'`. Edit `docker-compose.yml`: `postgres: image: pgvector/pgvector:pg16`.

- [ ] **Step 4: Write the two migrations**

  `b1c2d3e4f506_add_pgvector_extension.py` (`revision = "b1c2d3e4f506"`, `down_revision = "dcc247c7ad05"`):

  ```python
  def upgrade() -> None:
      op.execute("CREATE EXTENSION IF NOT EXISTS vector")
  def downgrade() -> None:
      op.execute("DROP EXTENSION IF EXISTS vector")
  ```

  `c2d3e4f5061_add_knowledge_documents_chunks.py` (`revision = "c2d3e4f5061"`, `down_revision = "b1c2d3e4f506"`): create `content_documents`, `ingest_events`, `content_chunks` using `postgresql.JSONB` only where needed, `sa.Column("embedding", Vector(dim=768))` imported as `from pgvector.sqlalchemy import Vector`, indexes `idx_content_chunks_org`, `idx_content_chunks_doc`, and the vector column declared so that migration `downgrade` drops tables in reverse order. Add a `concurrently`-safe HNSW index as a follow-up migration note in the module docstring: HNSW index creation is deferred to Task 8 when data volume makes it worthwhile, and `downgrade` notes that `DROP TABLE content_chunks` also drops the index.

- [ ] **Step 5: Write the ORM models**

  Create `backend/app/models/knowledge_document.py` with the three classes above, `Mapped[list[float]]` annotated `embedding: Mapped[Vector] = mapped_column(Vector(768), nullable=False)`, and relationships. Append `from app.models.knowledge_document import ContentChunk, ContentDocument, IngestEvent` to `backend/app/models/__init__.py`.

- [ ] **Step 6: Run migrations and test**

  Run: `cd backend && .venv/bin/alembic upgrade head && DATABASE_URL=postgresql+asyncpg://horus:horus@localhost:5432/horus_db .venv/bin/pytest tests/integration/test_knowledge_models.py -q`
  Expected: PASS; `\dx` in psql shows `vector`.

- [ ] **Step 7: Commit**

  ```bash
  git add backend/alembic/versions backend/app/models backend/docker-compose.yml backend/pyproject.toml backend/uv.lock backend/tests/integration/test_knowledge_models.py
  git commit -m "feat(knowledge): add content documents chunks and pgvector"
  ```

---

### Task 4: LangGraph checkpointer tables and Session store adapters

**Files:**
- Create: `backend/alembic/versions/d3e4f506172_add_langgraph_checkpointer.py`
- Modify: `backend/pyproject.toml` (add `langgraph-checkpoint-postgres>=2.0.0`)
- Create: `backend/app/services/training_sessions/__init__.py`, `session_store.py`, `postgres_session_store.py`
- Test: `backend/tests/unit/services/test_session_store.py`, `backend/tests/integration/test_postgres_session_store.py`

**Interfaces:**
- Consumes: nothing from Task 2 (Session store does not call the LLM).
- Produces:
  ```python
  # app/services/training_sessions/session_store.py
  @dataclass(frozen=True) class StoredState: values: dict[str, Any]; checkpoint_id: str | None; pending_instructor: bool
  class SessionStore(Protocol):
      async def load(self, org_id: uuid.UUID, session_id: int) -> StoredState | None: ...
      async def save(self, org_id: uuid.UUID, session_id: int, state: dict[str, Any], pending_instructor: bool = False) -> StoredState: ...
      async def delete(self, org_id: uuid.UUID, session_id: int) -> None: ...
      @staticmethod def thread_id(org_id: uuid.UUID, session_id: int) -> str: return f"{org_id}:{session_id}"
  class InMemorySessionStore:  # implements SessionStore; dict[(str, int)] of StoredState
  # app/services/training_sessions/postgres_session_store.py
  class PostgresSessionStore:  # implements SessionStore using langgraph.checkpoint.postgres.AsyncPostgresSaver
      def __init__(self, database_url: str) -> None
      async def setup(self) -> None            # runs saver.setup() once at startup
  ```
  `InMemorySessionStore` tests: `thread_id` format; `save` then `load` round-trips; `load` with a different `org_id` returns `None`; `delete` removes.

- [ ] **Step 1: Write failing store tests**

  Create `backend/tests/unit/services/test_session_store.py`:

  ```python
  import uuid
  import pytest
  from app.services.training_sessions.session_store import InMemorySessionStore, SessionStore

  @pytest.mark.asyncio
  async def test_roundtrip_and_tenant_isolation():
      store = InMemorySessionStore()
      org_a, org_b, sid = uuid.uuid4(), uuid.uuid4(), 7
      await store.save(org_a, sid, {"exchange_count": 1})
      assert (await store.load(org_a, sid)).values["exchange_count"] == 1
      assert await store.load(org_b, sid) is None
      assert SessionStore.thread_id(org_a, sid) == f"{org_a}:{sid}"
      await store.delete(org_a, sid)
      assert await store.load(org_a, sid) is None
  ```

- [ ] **Step 2: Run to verify failure**

  Run: `cd backend && .venv/bin/pytest tests/unit/services/test_session_store.py -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.training_sessions'`.

- [ ] **Step 3: Write `session_store.py` and `postgres_session_store.py`**

  `session_store.py` as specified. `postgres_session_store.py`:

  ```python
  from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
  from langgraph.checkpoint.base import empty_checkpoint
  from psycopg import AsyncConnection
  from psycopg_pool import AsyncConnectionPool
  from sqlalchemy.engine import make_url

  class PostgresSessionStore:
      def __init__(self, database_url: str) -> None:
          dsn = str(make_url(database_url).set(drivername="postgresql"))
          self._pool = AsyncConnectionPool(dsn, open=False, max_size=10)
          self._saver = AsyncPostgresSaver(self._pool)
      async def setup(self) -> None:
          await self._pool.open()
          await self._saver.setup()
      async def load(self, org_id, session_id) -> StoredState | None:
          cfg = {"configurable": {"thread_id": SessionStore.thread_id(org_id, session_id)}}
          tup = await self._saver.aget_tuple(cfg)
          if tup is None:
              return None
          checkpoint, metadata, values, pending_writes = tup
          return StoredState(values=dict(values), checkpoint_id=checkpoint.get("id"),
                             pending_instructor=any(m.get("name") == "generate_atc_response" for _, m in pending_writes))
      async def save(self, org_id, session_id, state, pending_instructor=False) -> StoredState:
          cfg = {"configurable": {"thread_id": SessionStore.thread_id(org_id, session_id)}}
          checkpoint = empty_checkpoint() if not state.get("__checkpoint__") else state["__checkpoint__"]
          saved = await self._saver.aput(cfg, state, checkpoint, {})
          return StoredState(values=state, checkpoint_id=saved["id"], pending_instructor=pending_instructor)
      async def delete(self, org_id, session_id) -> None:
          await self._saver.adelete_thread(SessionStore.thread_id(org_id, session_id))
  ```

  `AsyncPostgresSaver` is constructed with an `AsyncConnectionPool` (its documented Postgres-pooled mode); `aput(config, checkpoint, metadata, new_versions)` matches the current `BaseCheckpointSaver` signature, and `aget_tuple(config)` returns `(checkpoint, metadata, values, pending_writes)`. The executor must confirm these against the pinned `langgraph-checkpoint-postgres` version before finalizing and adjust call sites if the installed version differs; the Session store interface itself does not change. `psycopg[binary,pool]>=3.2` is added as a dependency.

- [ ] **Step 4: Add the migration**

  `d3e4f506172_add_langgraph_checkpointer.py` (`down_revision = "c2d3e4f5061"`) creates the four checkpointer tables by running the pinned library's own DDL: in `upgrade()` call `op.get_bind()` and execute the statements from `langgraph.checkpoint.postgres.PostgresSaver.MIGRATIONS` (each entry's `sql`, separated by `;`) through `op.execute`. This keeps the schema identical to the library. `downgrade()` drops `checkpoint_writes`, `checkpoint_blobs`, `checkpoints`, and `checkpoint_migrations` in that order. The module docstring records the library version whose `MIGRATIONS` were used.

- [ ] **Step 5: Add integration test**

  Create `backend/tests/integration/test_postgres_session_store.py` mirroring the unit test against `PostgresSessionStore` with `setup()` awaited once, skipped without `DATABASE_URL`. Add a second test pinning the restart Review Focus item: save a state with `exchange_count=1` under one `PostgresSessionStore` instance, construct a **new** `PostgresSessionStore` instance (simulating a backend restart), `load` the same `(org_id, session_id)`, and assert `values["exchange_count"] == 1` — proving state survives the process, not the object.

- [ ] **Step 6: Run to verify pass**

  Run: `cd backend && .venv/bin/pytest tests/unit/services/test_session_store.py -q && DATABASE_URL=postgresql+asyncpg://horus:horus@localhost:5432/horus_db .venv/bin/pytest tests/integration/test_postgres_session_store.py -q && .venv/bin/alembic upgrade head`
  Expected: PASS.

- [ ] **Step 7: Commit**

  ```bash
  git add backend/alembic/versions backend/app/services/training_sessions backend/pyproject.toml backend/uv.lock backend/tests
  git commit -m "feat(sessions): add session store adapters and checkpointer tables"
  ```

---

### Task 5: Graph factories without globals and the Scene registry

**Files:**
- Create: `backend/app/services/llm/scenes/__init__.py`, `default_scene.py`, `registry.py`, `backend/app/services/training_sessions/graphs.py`
- Create: `docs/architecture/scene-config.example.yaml`
- Modify: `backend/app/services/llm/graphs/live_session_graph.py` (remove `_llm`, accept `llm: LLMModule` and `scene: SceneConfig`)
- Modify: `backend/app/services/llm/graphs/validation_graph.py` (accept optional `knowledge` retriever; keep node functions otherwise unchanged). **`scoring_graph.py` is intentionally NOT modified** — the plan previously listed it here, but the task body only ever specified `build_scoring_graph()` as unchanged, so the file-list entry was a planning error. (Corrected 2026-09-25 after the Task 5 review.)
- Modify: `backend/app/services/llm/atc_agent.py` (become a thin adapter over the live graph; remove its private `AgentState`/`SessionPhase`/understand-respond-evaluate graph and its Ollama construction)
- Modify: `backend/app/services/llm/state.py` (add `scene_version: str`, `prompt_version: str`, `retrieved_chunk_ids: list[str]`, `llm_provider: str`, `llm_model: str`, `llm_fallback_used: bool`, `pending_instructor: bool`)
- Modify: `backend/app/core/audio_pipeline.py` (accept `llm: LLMModule`, `scene: SceneConfig`; construct `ATCAgent(llm, scene)`)
- Modify: `backend/app/services/llm/prompts.py` (delete `ATC_SYSTEM_PROMPT_*`, `FLIGHT_CONTEXT_TEMPLATE_*`, `DEFAULT_FLIGHT_CONTEXT`, `get_atc_prompt`; keep `WEATHER_BRIEFING_PROMPT`, `EMERGENCY_RESPONSE_PROMPT`, `STUDENT_EVALUATION_PROMPT`, `FLIGHT_PLAN_PARSE_PROMPT`, `READBACK_EVALUATION_PROMPT`)
- Test: `backend/tests/unit/services/llm/test_scene_registry.py`, `backend/tests/unit/services/llm/test_graph_factories.py`, `backend/tests/unit/services/llm/test_atc_agent.py` (rewritten)

**Interfaces:**
- Consumes: `LLMModule`, `SceneConstraints` from Task 2.
- Produces:
  ```python
  # app/services/llm/scenes/registry.py
  @dataclass(frozen=True) class SceneConfig:
      version: str; name: str; aircraft: dict; airports: dict; objectives: list[str]
      difficulty: int; knowledge_refs: list[str]; prompt_template: str
      constraints: SceneConstraints
  class SceneRegistry:
      def __init__(self, configs: dict[str, SceneConfig]) -> None
      def get(self, version: str) -> SceneConfig    # raises KeyError
      def default(self) -> SceneConfig              # DEFAULT_SCENE
  def load_scene_configs(path: str | Path) -> SceneRegistry
  # app/services/llm/scenes/default_scene.py
  DEFAULT_SCENE: SceneConfig  # version="default-v1", aircraft C172, KLAX→KSFO, difficulty 1
  # app/services/training_sessions/graphs.py
  def build_validation_graph(knowledge: KnowledgeRetriever | None = None) -> Any
  def build_live_session_graph(llm: LLMModule, scene: SceneConfig, interrupt_before_response: bool) -> Any
  def build_scoring_graph() -> Any
  ```
  `HorusState` gains the provenance fields listed above, each `total=False` (TypedDict), so existing agents are unaffected.

- [ ] **Step 1: Write failing Scene registry tests**

  Create `backend/tests/unit/services/llm/test_scene_registry.py`:

  ```python
  import pytest
  from app.services.llm.scenes.default_scene import DEFAULT_SCENE
  from app.services.llm.scenes.registry import SceneRegistry

  def test_default_scene_is_versioned_and_constrained():
      assert DEFAULT_SCENE.version == "default-v1"
      assert DEFAULT_SCENE.constraints.temperature is not None
      assert DEFAULT_SCENE.prompt_template.count("{pilot_message}") == 1

  def test_registry_lookup():
      reg = SceneRegistry({DEFAULT_SCENE.version: DEFAULT_SCENE})
      assert reg.get("default-v1") is DEFAULT_SCENE
      with pytest.raises(KeyError):
          reg.get("missing-v9")

  def test_example_config_loads(tmp_path):
      from app.services.llm.scenes.registry import load_scene_configs
      import shutil
      shutil.copy("docs/architecture/scene-config.example.yaml", tmp_path / "scenes.yaml")
      reg = load_scene_configs(tmp_path / "scenes.yaml")
      assert reg.default().version == "default-v1"
  ```

- [ ] **Step 2: Run to verify failure**

  Run: `cd backend && .venv/bin/pytest tests/unit/services/llm/test_scene_registry.py -q`
  Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the Scene modules and the example YAML**

  `default_scene.py` holds `DEFAULT_SCENE` with `prompt_template` = the English ATC system prompt moved out of `prompts.py`, using `{callsign}`, `{aircraft_type}`, `{altitude}`, `{heading}`, `{speed}`, `{position}`, `{phase}`, `{destination}`, `{weather}`, `{pilot_message}` placeholders and `constraints=SceneConstraints(temperature=0.3, max_output_tokens=150)`. `registry.py` parses YAML with `pyyaml` (added to `pyproject.toml`) and validates every config has `version`, `name`, `prompt_template`, and placeholders. Write `docs/architecture/scene-config.example.yaml` with `default-v1` and a `kef-ILS-25L-v1` example, and document each field in a comment header.

- [ ] **Step 4: Refactor `live_session_graph.py` to take `llm` and `scene`**

  Remove `_llm`, `_generate_atc_response(state)` becomes

  ```python
  async def _generate_atc_response_factory(llm: LLMModule, scene: SceneConfig):
      async def _generate_atc_response(state: HorusState) -> dict[str, Any]:
          prompt = scene.prompt_template.format(**state.get("context", {}), pilot_message=state.get("pilot_message", ""))
          req = GenerationRequest(prompt=prompt, purpose="atc_response", scene_constraints=scene.constraints, language=state.get("language", "en"))
          result = await llm.generate(req)
          return {"atc_response": result.text, "llm_provider": result.provider, "llm_model": result.model, "llm_fallback_used": result.fallback_used}
      return _generate_atc_response
  ```

  `build_live_session_graph(llm, scene, interrupt_before_response)` wires the factory. `build_validation_graph(knowledge=None)` accepts a retriever and passes it to a new `weather_node` factory that, when a retriever is present, queries the retriever for `departure_icao arrival_icao flight_rules` and records `retrieved_chunk_ids` on state; when absent, the existing mock `fetch_metar` path runs. `build_scoring_graph()` unchanged.

- [ ] **Step 5: Write `graphs.py` factories**

  ```python
  from app.services.llm.graphs.live_session_graph import build_live_session_graph as _live
  from app.services.llm.graphs.scoring_graph import build_scoring_graph as _scoring
  from app.services.llm.graphs.validation_graph import build_validation_graph as _validation

  def build_live_session_graph(llm: LLMModule, scene: SceneConfig, interrupt_before_response: bool) -> Any:
      return _live(llm, scene, interrupt_before_response)
  def build_validation_graph(knowledge: KnowledgeRetriever | None = None) -> Any:
      return _validation(knowledge)
  def build_scoring_graph() -> Any:
      return _scoring()
  ```

  (If `graphs.py` would only forward three functions, skip it and import the graph builders from their existing modules directly from the Session module; the "deletion test" says a pure forwarding module is shallow.)

- [ ] **Step 6: Write graph factory tests**

  `backend/tests/unit/services/llm/test_graph_factories.py` asserts that `build_live_session_graph(FakeAdapter(), DEFAULT_SCENE, False)` compiles without touching the network, and that `_llm` no longer exists as a module attribute:

  ```python
  def test_no_module_global_llm():
      import app.services.llm.graphs.live_session_graph as mod
      assert not hasattr(mod, "_llm")
  ```

- [ ] **Step 7: Run to verify pass**

  Run: `cd backend && .venv/bin/pytest tests/unit/services/llm -q`
  Expected: PASS, including the pre-existing `test_atc_agent.py` unchanged.

- [ ] **Step 8: Commit**

  ```bash
  git add backend/app/services/llm/scenes backend/app/services/llm/graphs backend/app/services/llm/state.py backend/app/services/training_sessions/graphs.py docs/architecture/scene-config.example.yaml backend/pyproject.toml backend/uv.lock backend/tests/unit/services/llm
  git commit -m "refactor(graphs): inject llm and scene, add scene registry"
  ```

---

### Task 6: Trace recorder and the Session module

**Files:**
- Create: `backend/app/services/training_sessions/types.py`, `trace.py`, `session_module.py`
- Create: `backend/app/schemas/knowledge.py` (only `Citation`, `RetrievedChunk` schemas needed here)
- Modify: `backend/app/models/training_session.py` (add `scene_version: str | None`, `scene_snapshot: JSONB | None`)
- Test: `backend/tests/unit/services/test_session_module.py`, `backend/tests/integration/test_session_module_postgres.py`

**Interfaces:**
- Consumes: `SessionStore` (Task 4), graph factories (Task 5), `SceneRegistry`, `LLMModule` (Task 2), `TrainingSessionEvent` (existing).
- Produces:
  ```python
  # app/services/training_sessions/types.py
  @dataclass(frozen=True) class StartSessionCommand: org_id: uuid.UUID | None; user_id: uuid.UUID | None; session_id: int; scene_version: str; language: str; flight_plan: dict[str, Any]
  @dataclass(frozen=True) class SendTransmissionCommand: org_id: uuid.UUID | None; session_id: int; pilot_message: str; context_overrides: dict[str, Any] | None = None
  @dataclass(frozen=True) class EndSessionCommand: org_id: uuid.UUID | None; session_id: int; student_stats_context: dict[str, Any] | None = None
  @dataclass(frozen=True) class ExchangeResult: atc_response: str; is_emergency: bool; exchange_count: int; pending_instructor: bool; citations: list[Citation]; provider: str; model: str; fallback_used: bool
  @dataclass(frozen=True) class SessionSnapshot: session_id: int; phase: str; exchange_count: int; state: dict[str, Any]
  @dataclass(frozen=True) class Debrief: scoring: dict[str, Any]; badges_earned: list[str]; report: str
  class SessionModule(Protocol):
      async def start(self, command: StartSessionCommand) -> SessionSnapshot: ...
      async def send(self, command: SendTransmissionCommand) -> ExchangeResult: ...
      async def await_instructor(self, org_id: uuid.UUID, session_id: int) -> ExchangeResult | None: ...
      async def end(self, command: EndSessionCommand) -> Debrief: ...
      async def snapshot(self, org_id: uuid.UUID | None, session_id: int) -> SessionSnapshot: ...
  # app/services/training_sessions/trace.py
  class TraceRecorder(Protocol):
      async def record(self, db: AsyncSession, org_id: uuid.UUID | None, session_id: int,
                       user_id: uuid.UUID | None, event_type: str, payload: dict[str, Any]) -> None: ...
  class SqlAlchemyTraceRecorder:  # implements TraceRecorder; adds a TrainingSessionEvent to `db` (never commits)
  class InMemoryTraceRecorder:     # tests; stores (session_id, event_type, payload) tuples in a list
  # app/services/training_sessions/session_module.py
  class TrainingSessionModule:
      def __init__(self, store: SessionStore, trace: TraceRecorder, scenes: SceneRegistry,
                   llm: LLMModule, db_session_factory: Callable[[], AsyncSession],
                   knowledge: KnowledgeRetriever | None = None,
                   interrupt_before_response: bool = False, require_org: bool = True) -> None
  class MissingOrgError(PermissionError): ...
  class SessionNotFoundError(KeyError): ...
  class SessionPendingInstructorError(RuntimeError): ...  # raised by send() while awaiting instructor
  ```
  `TrainingSessionModule` behavior:
  - `start` requires `org_id` unless `require_org` is `False` (injected as a constructor flag; `True` in the production composition root). Loads the Scene, seeds `HorusState` with `scene_version`/`prompt_version`, runs `build_validation_graph(knowledge)`, saves via store, and records a `session_started` event with `{scene_version, prompt_version, validation_passed}` using a short-lived `db` session from `db_session_factory`.
  - `send` requires `org_id`, loads state; if `state["pending_instructor"]` is true raises `SessionPendingInstructorError`; otherwise runs the live graph; when the graph returns an interrupt (HITL), sets `pending_instructor=True`, saves, records `awaiting_instructor` event, and returns `ExchangeResult(pending_instructor=True, atc_response="")`; otherwise saves and records `exchange_completed` event with `{provider, model, fallback_used, retrieved_chunk_ids, instructor_overridden=False, graph: "live", node: "generate_atc_response"}`.
  - `await_instructor` sets `pending_instructor=False` and records `instructor_override` with the instructor-supplied `atc_response` in the payload.
  - `end` runs the scoring graph, saves, records `session_completed` with `{scoring_summary, badges_earned}`.
  - Every event payload includes `org_id`, `session_id`, `graph`, `node`, `scene_version`, `prompt_version`.

- [ ] **Step 1: Write failing session module tests**

  Create `backend/tests/unit/services/test_session_module.py`:

  ```python
  import uuid
  import pytest
  from app.llm.adapters.fake_adapter import FakeAdapter
  from app.services.llm.scenes.default_scene import DEFAULT_SCENE
  from app.services.llm.scenes.registry import SceneRegistry
  from app.services.training_sessions.session_module import (
      MissingOrgError, SessionPendingInstructorError, TrainingSessionModule)
  from app.services.training_sessions.session_store import InMemorySessionStore
  from app.services.training_sessions.trace import InMemoryTraceRecorder
  from app.services.training_sessions.types import SendTransmissionCommand, StartSessionCommand

  class _NoDb:  # AsyncSession stand-in; InMemoryTraceRecorder never touches it
      pass

  def _module(**kw):
      return TrainingSessionModule(InMemorySessionStore(), InMemoryTraceRecorder(),
                                   SceneRegistry({DEFAULT_SCENE.version: DEFAULT_SCENE}),
                                   FakeAdapter(), db_session_factory=lambda: _NoDb(),
                                   require_org=True, **kw)

  @pytest.mark.asyncio
  async def test_send_then_send_preserves_exchange_count():
      m = _module(); org = uuid.uuid4()
      await m.start(StartSessionCommand(org, uuid.uuid4(), 1, "default-v1", "en", {"departure_icao": "KLAX", "arrival_icao": "KSFO"}))
      r1 = await m.send(SendTransmissionCommand(org, 1, "Tower, request taxi"))
      r2 = await m.send(SendTransmissionCommand(org, 1, "Tower, ready for departure"))
      assert (r1.exchange_count, r2.exchange_count) == (1, 2)
      assert r2.provider == "fake"

  @pytest.mark.asyncio
  async def test_missing_org_rejected():
      m = _module()
      with pytest.raises(MissingOrgError):
          await m.start(StartSessionCommand(None, uuid.uuid4(), 1, "default-v1", "en", {}))

  @pytest.mark.asyncio
  async def test_second_send_while_pending_instructor_raises():
      m = _module(interrupt_before_response=True); org = uuid.uuid4()
      await m.start(StartSessionCommand(org, uuid.uuid4(), 1, "default-v1", "en", {"departure_icao": "KLAX"}))
      r = await m.send(SendTransmissionCommand(org, 1, "request clearance"))
      assert r.pending_instructor is True
      with pytest.raises(SessionPendingInstructorError):
          await m.send(SendTransmissionCommand(org, 1, "again"))
      released = await m.await_instructor(org, 1)
      assert released is not None
  ```

- [ ] **Step 2: Run to verify failure**

  Run: `cd backend && .venv/bin/pytest tests/unit/services/test_session_module.py -q`
  Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `types.py` and `trace.py`**

  As specified. `SqlAlchemyTraceRecorder.record` constructs `TrainingSessionEvent(session_id=session_id, user_id=user_id, org_id=org_id, event_type=event_type, event_payload=payload)` on the `db` it is given, calls `db.add(...)`, and never commits — `TrainingSessionModule` opens a short-lived `db` session from `db_session_factory` for each event and commits it immediately, so trace writes survive even when the caller's request transaction later rolls back. `Citation` is a pydantic model `{chunk_id: UUID, document_id: UUID, title: str, page: int | None, section: str | None, snippet: str}`.

- [ ] **Step 4: Write `session_module.py`**

  Implement the five methods. `start` builds the same `HorusState` seed as the current `HorusOrchestrator.start_session` (copy the dict literal) plus `scene_version`, `prompt_version` (both `scene.version`), and `pending_instructor=False`. `send` merges `context_overrides`, runs `self._live_graph.ainvoke(state)`, and reads `result.get("__interrupt__")` to detect HITL pauses (LangGraph returns interrupts in the result dict key `__interrupt__` when using `interrupt_before`); when present, set `pending_instructor=True` and use the pre-interrupt `atc_response` (empty string) in the returned result. `end` runs the scoring graph and returns `Debrief`. Every method calls `self._store.save(...)` before returning, and every event write goes through the helper:

  ```python
  async def _emit(self, session_id: int, event_type: str, payload: dict[str, Any], org_id, user_id) -> None:
      async with self._db_session_factory() as db:
          await self._trace.record(db, org_id, session_id, user_id, event_type,
                                   {**payload, "org_id": str(org_id) if org_id else None,
                                    "session_id": session_id})
          await db.commit()
  ```

  `snapshot` loads the stored state and returns `SessionSnapshot(session_id, phase=state["phase"], exchange_count=state.get("exchange_count", 0), state=state)`.

- [ ] **Step 5: Run to verify pass**

  Run: `cd backend && .venv/bin/pytest tests/unit/services/test_session_module.py -q`
  Expected: PASS.

- [ ] **Step 6: Integration test with Postgres store**

  Create `backend/tests/integration/test_session_module_postgres.py`: same as the unit test but with `PostgresSessionStore` and `SqlAlchemyTraceRecorder` against a real DB; assert after `send` that a `TrainingSessionEvent` row with `event_type="exchange_completed"` exists for the session. Skipped without `DATABASE_URL`.

- [ ] **Step 7: Commit**

  ```bash
  git add backend/app/services/training_sessions backend/app/models/training_session.py backend/app/schemas/knowledge.py backend/tests
  git commit -m "feat(sessions): add session module with trace recorder"
  ```

---

### Task 7: Composition root, router and voice wiring, orchestrator removal

**Files:**
- Modify: `backend/app/main.py` (lifespan builds `llm`, `session_store`, `retriever`, `session_module`, `trace`; stores on `app.state`)
- Modify: `backend/app/api/v1/sessions.py` (`_run_scoring` uses `request.app.state.session_module`; `create_session` calls `session_module.start`; `complete_session` calls `session_module.end`; replay includes provenance events)
- Modify: `backend/app/api/routes/voice.py` (resolve session module; `get_current_user_ws` returns org id; use `session_module.send` when a `session_id` is present)
- Modify: `backend/app/schemas/training_session.py` (`TrainingSessionResponse` gains `scene_version`; `TrainingSessionReplayResponse` gains `provenance: list[ProvenanceEvent]`)
- Delete: `backend/app/services/llm/orchestrator.py`
- Modify: `backend/app/api/v1/flight_plans.py` (remove `HorusOrchestrator` import; validation route uses `app.state.session_module.snapshot`)
- Modify: `backend/tests/unit/api/test_sessions.py`, `backend/tests/integration/test_sessions_complete.py`, `backend/tests/integration/test_sessions_replay.py` (override `app.state.session_module` with a `FakeSessionModule`)
- Test: `backend/tests/unit/api/test_session_wiring.py`

**Interfaces:**
- Consumes: `SessionModule` (Task 6), `build_llm` (Task 2), `PostgresSessionStore` / `InMemorySessionStore` (Task 4), `PgVectorRetriever` (Task 8, optional `None` in composition root until then).
- Produces: `app.state.session_module: SessionModule`, `app.state.llm: LLMModule`, `app.state.scene_registry: SceneRegistry`, `app.state.trace_recorder: TraceRecorder`, `app.state.session_store: SessionStore`, `app.state.retriever: KnowledgeRetriever | None`, `app.state.settings: Settings`.

  `main.py` lifespan:

  ```python
  from contextlib import asynccontextmanager
  from app.db.session import get_session_factory

  @asynccontextmanager
  async def lifespan(app: FastAPI):
      settings = get_settings()
      llm = build_llm(settings)
      store = PostgresSessionStore(settings.database_url) if settings.environment == "production" else InMemorySessionStore()
      if hasattr(store, "setup"):
          await store.setup()
      scenes = load_scene_configs(os.getenv("SCENES_PATH", "app/services/llm/scenes/configs.yaml"))
      retriever = None  # Task 8 replaces this with build_retriever(settings, get_session_factory, llm)
      trace = SqlAlchemyTraceRecorder()
      app.state.settings = settings
      app.state.llm = llm
      app.state.session_store = store
      app.state.scene_registry = scenes
      app.state.retriever = retriever
      app.state.trace_recorder = trace
      app.state.session_module = TrainingSessionModule(
          store, trace, scenes, llm, db_session_factory=get_session_factory,
          knowledge=retriever, require_org=settings.environment == "production")
      yield
      await close_redis()
  ```

  Replace the current `@app.on_event("startup")` / `@app.on_event("shutdown")` with this lifespan and pass `lifespan=lifespan` to `FastAPI(...)`. `create_session` in `sessions.py` becomes:

  ```python
  training_session = TrainingSession(**data.model_dump(exclude={"scene_version", "flight_plan"}),
                                      user_id=local_user.id, org_id=org_id,
                                      scene_version=data.scene_version or "default-v1")
  session.add(training_session); await session.flush()
  snapshot = await request.app.state.session_module.start(
      StartSessionCommand(org_id=org_id, user_id=local_user.id, session_id=training_session.id,
                          scene_version=data.scene_version or "default-v1", language=data.language,
                          flight_plan=data.flight_plan or {}))
  ```

  `complete_session` replaces `_run_scoring` with `await request.app.state.session_module.end(EndSessionCommand(org_id, training_session.org_id, session_id, None))` and keeps the `already_completed` branch. `_run_scoring` and `_default_scoring` are deleted. `get_session_replay` gains `provenance=[_provenance_from_event(e) for e in events]` in Task 10; in this task the replay payload is unchanged.

- [ ] **Step 1: Write the failing wiring test**

  Create `backend/tests/unit/api/test_session_wiring.py`:

  ```python
  from fastapi.testclient import TestClient
  from app.main import app

  class FakeSessionModule:
      def __init__(self): self.started = []; self.ended = []
      async def start(self, command): self.started.append(command); return AsyncMock()
      async def end(self, command): self.ended.append(command); return AsyncMock(scoring={}, badges_earned=[], report="")
      async def send(self, command): return AsyncMock()
      async def snapshot(self, org_id, session_id): return AsyncMock()

  def test_compose_app_sets_session_module():
      with TestClient(app) as client:
          assert client.app.state.session_module is not None
          assert client.app.state.llm.provider == "fake"
  ```

  The testing `Settings` used by `conftest.py` is set to `llm={"provider": "fake", "base_url": "http://unused", "model": "fake", "embedding_model": "nomic-embed-text", "temperature": 0.3, "max_output_tokens": 150}`, so `build_llm` returns a `FakeAdapter`-backed `FallbackLLM` whose `provider` property is `"fake"`.

  Add a second test in the same file pinning the voice-only Review Focus item: open the WebSocket at `/ws/voice` with a valid platform-admin token and no `session_id`, send an `audio_end` message, and assert the server still returns a `response_complete` frame (with `FakeAdapter` supplying a transcript) and that a `TrainingSession` row exists with `scene_version="default-v1"`. This is the test that proves `Review Focus` item 5.

- [ ] **Step 2: Run to verify failure**

  Run: `cd backend && .venv/bin/pytest tests/unit/api/test_session_wiring.py -q`
  Expected: FAIL with `AttributeError: 'FastAPI' object has no attribute 'state'` state content missing, or `lifespan` not defined.

- [ ] **Step 3: Implement the lifespan and state wiring**

  As specified. `build_retriever` is a Task 8 function; until Task 8 lands, define a temporary `build_retriever(settings) -> None` in `app/main.py` with a `# replaced in Task 8` comment, then replace it in Task 8. `close_redis()` stays in the `finally` of the lifespan.

- [ ] **Step 4: Rewire `sessions.py`**

  Apply the `create_session`, `complete_session`, and replay changes above. Add `scene_version: str | None = None` and `flight_plan: dict | None = None` to `TrainingSessionCreate` if absent. Add `scene_version: str | None` to `TrainingSessionResponse`. Add to `training_session.py` model: `scene_version: Mapped[str | None] = mapped_column(String(50), nullable=True)`, `scene_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=True, server_default="{}")`.

- [ ] **Step 5: Rewire `voice.py`**

  Replace the `audio_pipeline` global with `app.state` resolution: `pipeline = AudioPipeline(llm=websocket.app.state.llm, scene=websocket.app.state.scene_registry.get("default-v1"))`. On `audio_end`, if `db_session_id` is set, call `session_module.send(SendTransmissionCommand(org_id=..., session_id=db_session_id, pilot_message=result.pilot_transcript))` and persist `result.atc_response` plus the returned citations; otherwise fall back to `pipeline.process_audio` as today. `AudioPipeline.__init__` changes to `def __init__(self, llm: LLMModule, scene: SceneConfig) -> None` and constructs `ATCAgent(llm=llm, scene=scene)`; `ATCAgent.__post_init__` no longer calls `get_settings()` or constructs `Ollama` directly.

- [ ] **Step 6: Delete the orchestrator and update tests**

  Delete `backend/app/services/llm/orchestrator.py`. Remove its import from `flight_plans.py` and `sessions.py`. Update `backend/tests/unit/services/llm/test_atc_agent.py` `_make_agent()` to `ATCAgent(llm=FakeAdapter(), scene=DEFAULT_SCENE)`. Update `backend/tests/integration/test_sessions_complete.py` and `test_sessions_replay.py` to install a `FakeSessionModule` on `app.state` in the `client` fixture. Update `conftest.py` `test_settings` to set `llm={"provider": "fake", ...}`.

- [ ] **Step 7: Run to verify pass**

  Run: `cd backend && .venv/bin/pytest -q`
  Expected: PASS (full backend suite).

- [ ] **Step 8: Commit**

  ```bash
  git add -A backend/app backend/tests
  git commit -m "refactor(sessions): wire session module as composition root"
  ```

---

### Task 8: Knowledge ingest module (documents, chunking, embedding)

**Files:**
- Create: `backend/app/knowledge/__init__.py`, `types.py`, `documents.py`, `chunking.py`, `ingest.py`, `retrieval/__init__.py`, `retrieval/pgvector.py`, `retrieval/fake.py`
- Create: `backend/app/api/v1/knowledge.py`
- Modify: `backend/app/api/v1/__init__.py`, `backend/app/main.py` (include router; replace `build_retriever` stub)
- Create: `backend/app/schemas/knowledge.py` (upload/search schemas)
- Modify: `backend/pyproject.toml` (add `pypdf>=5.0.0`, `pyyaml` if not present)
- Create: `docs/knowledge/INGEST.md`, `docs/knowledge/RETRIEVAL.md`
- Test: `backend/tests/unit/knowledge/test_chunking.py`, `test_ingest.py`, `test_pgvector_retriever.py`, `test_knowledge_api.py`

**Interfaces:**
- Consumes: `LLMModule.embed` (Task 2), `ContentDocument` / `ContentChunk` / `IngestEvent` (Task 3), `Settings.knowledge` (Task 1), `SceneConfig.knowledge_refs` (Task 5).
- Produces:
  ```python
  # app/knowledge/types.py
  @dataclass(frozen=True) class DocumentUpload: title: str; source_filename: str; content: bytes; org_id: uuid.UUID | None; created_by: uuid.UUID | None; is_published: bool = False; knowledge_refs: list[str] = field(default_factory=list)
  @dataclass(frozen=True) class IngestResult: document_id: uuid.UUID; chunk_count: int; embedding_dimensions: int; status: str
  @dataclass(frozen=True) class RetrievalQuery: query: str; org_id: uuid.UUID | None; top_k: int; knowledge_refs: list[str] = field(default_factory=list); mode: Literal["hybrid", "vector", "text"] = "hybrid"
  @dataclass(frozen=True) class RetrievedChunk: chunk_id: uuid.UUID; document_id: uuid.UUID; org_id: uuid.UUID | None; title: str; content: str; score: float; page: int | None; section: str | None; char_start: int; char_end: int
  class KnowledgeRetriever(Protocol):
      async def search(self, query: RetrievalQuery) -> list[RetrievedChunk]: ...
  class EmbeddingDimensionMismatch(RuntimeError): ...
  class QuotaExceeded(RuntimeError): ...
  # app/knowledge/documents.py
  def extract_text(filename: str, content: bytes) -> tuple[str, dict[str, int | str | None]]:
      """Returns (text, citation_hints) where citation_hints has page/section keys."""
  # app/knowledge/chunking.py
  def chunk_document(text: str, chunk_size: int, chunk_overlap: int) -> list[tuple[int, int, int]]:
      """Returns [(char_start, char_end, token_count)] using a whitespace tokenizer approximation."""
  # app/knowledge/ingest.py
  class KnowledgeIngestor:
      def __init__(self, llm: LLMModule, settings: KnowledgeSettings, embedding_model: str) -> None
      async def ingest(self, db: AsyncSession, upload: DocumentUpload) -> IngestResult
  # app/knowledge/retrieval/pgvector.py
  class PgVectorRetriever:
      def __init__(self, db_factory: Callable[[], AsyncSession], settings: KnowledgeSettings) -> None
      async def search(self, query: RetrievalQuery) -> list[RetrievedChunk]
  # app/knowledge/retrieval/fake.py
  class FakeRetriever:  # in-memory list; satisfies KnowledgeRetriever
  # app/knowledge/retrieval/__init__.py
  def build_retriever(settings: Settings, db_factory: Callable[[], AsyncSession], llm: LLMModule) -> KnowledgeRetriever
      # PgVectorRetriever in production, FakeRetriever otherwise
  ```
  `PgVectorRetriever.search` runs two SQL statements and merges with Reciprocal Rank Fusion: dense leg `ORDER BY embedding <=> :query_vec LIMIT :k` and text leg `to_tsquery` `ORDER BY ts_rank_cd DESC LIMIT :k`, each filtered by `(ContentChunk.org_id == query.org_id OR ContentChunk.org_id IS NULL)`, `ContentDocument.is_published.is_(True)`, and `ContentChunk.document_id IN (:ref_ids)` when `knowledge_refs` is non-empty. RRF: `score = sum(1 / (60 + rank))`.

- [ ] **Step 1: Write failing chunking and ingest tests**

  Create `backend/tests/unit/knowledge/test_chunking.py`:

  ```python
  from app.knowledge.chunking import chunk_document
  from app.knowledge.documents import extract_text

  def test_markdown_extract_and_chunk():
      text, hints = extract_text("manual.md", b"# Title\n\nSome text " * 200)
      assert hints["section"] == "Title"
      spans = chunk_document(text, chunk_size=100, chunk_overlap=15)
      assert len(spans) > 1
      assert spans[0][0] == 0 and spans[-1][1] <= len(text)
      assert spans[0][2] <= 100

  def test_pdf_requires_pypdf(monkeypatch):
      import pypdf
      assert pypdf.__version__ >= "5"
  ```

  Create `backend/tests/integration/test_ingest.py` (it needs a real `AsyncSession`, so it is an integration test, not a unit test):

  ```python
  import pytest
  from app.config import KnowledgeSettings
  from app.db.session import get_session_factory
  from app.knowledge.ingest import KnowledgeIngestor, QuotaExceeded
  from app.knowledge.types import DocumentUpload
  from app.llm.adapters.fake_adapter import FakeAdapter
  import os
  pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="needs Postgres")

  SETTINGS = KnowledgeSettings(chunk_size=100, chunk_overlap=15, embedding_dimensions=768, top_k=5, default_chunk_quota=100)

  @pytest.mark.asyncio
  async def test_ingest_writes_chunks_and_event():
      async with get_session_factory() as db:
          result = await KnowledgeIngestor(FakeAdapter(), SETTINGS, "nomic-embed-text").ingest(
              db, DocumentUpload(title="SOP", source_filename="sop.md", content=b"# SOP\nclearance rules " * 50, org_id=None, created_by=None))
          await db.commit()
          assert result.chunk_count > 0 and result.embedding_dimensions == 768

  @pytest.mark.asyncio
  async def test_quota_blocks_before_embedding():
      async with get_session_factory() as db:
          with pytest.raises(QuotaExceeded):
              await KnowledgeIngestor(FakeAdapter(), KnowledgeSettings(chunk_size=100, chunk_overlap=15, embedding_dimensions=768, top_k=5, default_chunk_quota=1), "nomic-embed-text").ingest(
                  db, DocumentUpload(title="big", source_filename="b.md", content=b"x " * 100000, org_id=None, created_by=None))
  ```

  Also add `backend/tests/unit/knowledge/test_ingest_pure.py` for the no-DB half of the review focus: a `FakeEmbedder(FakeAdapter)` subclass whose `embed` returns 384-dim vectors, asserting `EmbeddingDimensionMismatch` is raised by `KnowledgeIngestor.ingest` before any `ContentChunk` is added, by passing a recording `AsyncSession` stub whose `add` calls are inspected.

- [ ] **Step 2: Run to verify failure**

  Run: `cd backend && .venv/bin/pytest tests/unit/knowledge -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'app.knowledge'`.

- [ ] **Step 3: Write `types.py`, `documents.py`, `chunking.py`**

  `documents.py`: `.md` decoded as UTF-8 with the first `# ` heading captured as `section`; `.txt` decoded as UTF-8; `.pdf` parsed with `pypdf.PdfReader(io.BytesIO(content))`, text joined per page, `page` recorded for the first page only (per-page chunking is Task 8.4 if PDFs exceed 10 MB — keep v1 single-page hints). `chunking.py` tokenizes by whitespace, builds windows of `chunk_size` with `chunk_overlap` stride, and maps token indices back to character offsets by walking a running offset.

- [ ] **Step 4: Write `ingest.py`**

  ```python
  class KnowledgeIngestor:
      async def ingest(self, db: AsyncSession, upload: DocumentUpload) -> IngestResult:
          text, hints = extract_text(upload.source_filename, upload.content)
          spans = chunk_document(text, self._settings.chunk_size, self._settings.chunk_overlap)
          existing = await self._count_org_chunks(db, upload.org_id)
          if existing + len(spans) > self._settings.default_chunk_quota:
              raise QuotaExceeded(f"org {upload.org_id} would exceed chunk quota")
          text_hash = hashlib.sha256(text.encode()).hexdigest()
          doc = ContentDocument(title=upload.title, source_filename=upload.source_filename,
                                source_type=ext.source_type(upload.source_filename), content_hash=text_hash,
                                is_published=upload.is_published, org_id=upload.org_id, created_by=upload.created_by)
          db.add(doc); await db.flush()
          emb = await self._llm.embed([text[s:e] for s, e, _ in spans])
          if emb.dimensions != self._settings.embedding_dimensions:
              raise EmbeddingDimensionMismatch(f"expected {self._settings.embedding_dimensions}, got {emb.dimensions}")
          for idx, ((s, e, tokens), vector) in enumerate(zip(spans, emb.vectors)):
              db.add(ContentChunk(document_id=doc.id, org_id=upload.org_id, chunk_index=idx, content=text[s:e],
                                  token_count=tokens, embedding=vector, page=hints.get("page"),
                                  section=hints.get("section"), char_start=s, char_end=e))
          db.add(IngestEvent(document_id=doc.id, org_id=upload.org_id, status="succeeded",
                             embedding_model=self._llm_model_name, embedding_dimensions=emb.dimensions,
                             chunk_size=self._settings.chunk_size, chunk_overlap=self._settings.chunk_overlap,
                             chunk_count=len(spans)))
          doc.chunk_count = len(spans); doc.ingested_at = datetime.now(timezone.utc)
          await db.flush()
          return IngestResult(document_id=doc.id, chunk_count=len(spans), embedding_dimensions=emb.dimensions, status="succeeded")
  ```

  The `db_session_factory` argument is `get_session_factory` — an `asynccontextmanager`-decorated generator, so it must be entered as `async with factory() as db:`, never as `async with factory()() as db:`. Tests that need a real `AsyncSession` use `get_session_factory`; tests using `InMemoryTraceRecorder` pass a stub that is never entered.

  `self._embedding_model` is the `embedding_model` string passed as the third `__init__` argument, recorded on the `IngestEvent`. On any exception after `db.add(doc)`, the method adds an `IngestEvent(status="failed", error=str(exc))` only if `doc.id` exists, then re-raises; it never commits.

- [ ] **Step 5: Write `PgVectorRetriever` and `FakeRetriever`**

  `PgVectorRetriever.search` as specified with RRF, embedding via an injected `LLMModule` (constructor also takes `llm`), and `ContentDocument.is_published.is_(True)` join. `FakeRetriever` stores `(RetrievedChunk)` rows added via `async def add(self, chunk: RetrievedChunk) -> None` and returns the top `top_k` by naive token overlap. `build_retriever(settings, db_factory, llm)` returns `PgVectorRetriever` when `settings.environment == "production"` and `FakeRetriever()` otherwise, and takes `llm` so it can embed query vectors.

  Add `backend/tests/integration/test_retrieval_isolation.py` pinning the first Review Focus item:

  ```python
  import os, uuid
  import pytest
  from app.config import KnowledgeSettings
  from app.db.session import get_session_factory
  from app.knowledge.ingest import KnowledgeIngestor
  from app.knowledge.retrieval.pgvector import PgVectorRetriever
  from app.knowledge.types import DocumentUpload, RetrievalQuery
  from app.llm.adapters.fake_adapter import FakeAdapter
  pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="needs Postgres")

  SETTINGS = KnowledgeSettings(chunk_size=100, chunk_overlap=15, embedding_dimensions=768, top_k=5, default_chunk_quota=100)

  @pytest.mark.asyncio
  async def test_private_chunk_never_leaks_across_tenants():
      org_a, org_b = uuid.uuid4(), uuid.uuid4()
      async with get_session_factory() as db:
          ingestor = KnowledgeIngestor(FakeAdapter(), SETTINGS, "nomic-embed-text")
          await ingestor.ingest(db, DocumentUpload(title="A secret", source_filename="a.md",
                                                   content=b"secret phrase zebra " * 40, org_id=org_a, created_by=None, is_published=True))
          await db.commit()
      retriever = PgVectorRetriever(get_session_factory, FakeAdapter(), SETTINGS)
      results = await retriever.search(RetrievalQuery(query="zebra", org_id=org_b, top_k=5))
      assert all(r.org_id != org_a for r in results)
  ```

  Add a second case in the same file: a document ingested with `is_published=False` returns no results even for its own `org_id`, pinning the unpublished gate.

- [ ] **Step 6: Write the API routes and wire the router**

  `backend/app/api/v1/knowledge.py`:

  ```python
  router = APIRouter(prefix="/knowledge", tags=["Knowledge"])

  @router.post("/documents", response_model=IngestStatusResponse, status_code=201)
  async def upload_document(request: Request, file: UploadFile = File(...), title: str = Form(...),
                            publish: bool = Form(False), _seat: RequireActiveSeat, org_id: UUID = Depends(get_org_id),
                            local_user: User = Depends(get_authenticated_user),
                            db: AsyncSession = Depends(get_db_session)):
      if not has_role(_user, "org-admin", "instructor", "collaborator", "staff"):
          raise HTTPException(403, "Knowledge upload requires instructor, collaborator, or staff role")
      ingestor = KnowledgeIngestor(request.app.state.llm, request.app.state.settings.knowledge,
                                   request.app.state.settings.llm.embedding_model)
      result = await ingestor.ingest(db, DocumentUpload(title=title, source_filename=file.filename or "upload",
                                                        content=await file.read(), org_id=org_id,
                                                        created_by=local_user.id, is_published=publish))
      return IngestStatusResponse(document_id=result.document_id, chunk_count=result.chunk_count,
                                  status=result.status)

  @router.get("/search", response_model=list[RetrievedChunkRead])
  async def search_knowledge(request: Request, q: str = Query(..., min_length=1), top_k: int = Query(5, ge=1, le=20),
                             _seat: RequireActiveSeat, org_id: UUID = Depends(get_org_id)):
      return await request.app.state.retriever.search(RetrievalQuery(query=q, org_id=org_id, top_k=top_k))
  ```

  `main.py`: `app.include_router(knowledge.router, prefix="/api/v1")`; set `app.state.settings = settings` in the lifespan. Add `backend/tests/unit/knowledge/test_knowledge_api.py` asserting a student (no collaborator role) gets `403` and an instructor with a 2-chunk document gets `201`.

- [ ] **Step 7: Write the HNSW migration note and docs**

  Add to `docs/knowledge/RETRIEVAL.md` the exact `CREATE INDEX CONCURRENTLY idx_content_chunks_embedding_hnsw ON content_chunks USING hnsw (embedding vector_cosine_ops) WHERE org_id IS NOT NULL;` command and when to run it (after 50k chunks), plus the RRF description. `docs/knowledge/INGEST.md` documents: supported formats, the 1000/150 chunking rule, the 768-dimension lock and how to change it (new migration + re-ingest), the quota, the `is_published` gate, per-tenant isolation, and the Chroma-as-local-adapter story.

- [ ] **Step 8: Run to verify pass**

  Run: `cd backend && .venv/bin/pytest tests/unit/knowledge -q && .venv/bin/ruff check app/knowledge app/api/v1/knowledge.py`
  Expected: PASS.

- [ ] **Step 9: Commit**

  ```bash
  git add backend/app/knowledge backend/app/api/v1/knowledge.py backend/app/schemas/knowledge.py backend/app/main.py backend/pyproject.toml backend/uv.lock backend/tests/unit/knowledge docs/knowledge
  git commit -m "feat(knowledge): add ingest module and pgvector retriever"
  ```

---

### Task 9: Scenes API and Scene-aware session start

**Files:**
- Create: `backend/app/schemas/scene.py`, `backend/app/api/v1/scenes.py`
- Modify: `backend/app/main.py` (include `scenes.router`)
- Modify: `backend/app/services/training_sessions/session_module.py` (record `scene_snapshot` on `TrainingSession`)
- Modify: `backend/app/api/v1/sessions.py` (`TrainingSessionCreate` gains `scene_version`)
- Test: `backend/tests/unit/api/test_scenes.py`

**Interfaces:**
- Consumes: `SceneRegistry` (Task 5), `TrainingSession` model (Task 7).
- Produces:
  ```python
  # app/schemas/scene.py
  class SceneRead(BaseModel): version: str; name: str; aircraft: dict; airports: dict; objectives: list[str]; difficulty: int; knowledge_refs: list[str]
  # app/api/v1/scenes.py
  router = APIRouter(prefix="/scenes", tags=["Scenes"])
  @router.get("/", response_model=list[SceneRead]) async def list_scenes(_user: CurrentUser, request: Request) -> list[SceneRead]
  @router.get("/{version}", response_model=SceneRead) async def get_scene(version: str, _user: CurrentUser, request: Request) -> SceneRead
  ```
  `session_module.start` writes the Scene snapshot as the `scene_snapshot` JSONB on the `TrainingSession` row, opening a short-lived `db` session from `db_session_factory` after validation completes. The `scenes` table and `SceneModel` are NOT created; Scenes are versioned YAML files on disk (one deployed artifact), which matches ADR-006 decision 1 and keeps prompt versions in Git.

- [ ] **Step 1: Write failing API test**

  Create `backend/tests/unit/api/test_scenes.py`:

  ```python
  from fastapi.testclient import TestClient
  from app.main import app
  from app.services.llm.scenes.default_scene import DEFAULT_SCENE

  def test_list_scenes_includes_default(client: TestClient) -> None:
      response = client.get("/api/v1/scenes/")
      assert response.status_code == 200
      assert response.json()[0]["version"] == DEFAULT_SCENE.version
  ```

- [ ] **Step 2: Run to verify failure**

  Run: `cd backend && .venv/bin/pytest tests/unit/api/test_scenes.py -q`
  Expected: FAIL with `404`.

- [ ] **Step 3: Implement the router and wire it**

  As specified. `list_scenes` returns `SceneRead` for every config in `request.app.state.scene_registry`; `get_scene` raises `404` for unknown versions.

- [ ] **Step 4: Run to verify pass**

  Run: `cd backend && .venv/bin/pytest tests/unit/api/test_scenes.py tests/unit/api/test_sessions.py -q`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add backend/app/api/v1/scenes.py backend/app/schemas/scene.py backend/app/main.py backend/tests/unit/api/test_scenes.py
  git commit -m "feat(scenes): expose scene registry read routes"
  ```

---

### Task 10: Provenance in replay and 90-day retention

**Files:**
- Create: `backend/alembic/versions/f5061728394_add_trace_retention_config.py` (adds `index=True` on `training_session_events.created_at`; no new table)
- Modify: `backend/app/api/v1/sessions.py` (`_provenance_from_event`, retention prune endpoint)
- Create: `backend/app/services/training_sessions/retention.py` (`prune_old_events(db, retention_days: int) -> int`)
- Modify: `frontend/packages/core/app/composables/useSessionReplay.ts` (add `provenance` ref and return field)
- Test: `backend/tests/unit/services/test_retention.py`, `backend/tests/integration/test_replay_provenance.py`

**Interfaces:**
- Consumes: `TraceSettings.retention_days` (Task 1), `TrainingSessionEvent`.
- Produces:
  ```python
  # app/services/training_sessions/retention.py
  async def prune_old_events(db: AsyncSession, retention_days: int) -> int:
      """Delete TrainingSessionEvent rows older than retention_days; return count deleted."""
  # app/schemas/training_session.py
  class ProvenanceEvent(BaseModel): event_type: str; created_at: datetime; graph: str | None; node: str | None; scene_version: str | None; prompt_version: str | None; llm_provider: str | None; llm_model: str | None; llm_fallback_used: bool | None; retrieved_chunk_ids: list[str] = []; instructor_overridden: bool | None
  ```

- [ ] **Step 1: Write failing retention test**

  Create `backend/tests/unit/services/test_retention.py`:

  ```python
  import os
  from datetime import datetime, timedelta, timezone
  import pytest
  from sqlalchemy import delete
  from app.db.session import get_session_factory
  from app.models.training_session import TrainingSession
  from app.models.training_session_event import TrainingSessionEvent
  from app.services.training_sessions.retention import prune_old_events
  pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="needs Postgres")

  @pytest.mark.asyncio
  async def test_prune_removes_only_old_events():
      async with get_session_factory() as db:
          session = TrainingSession(user_id=None, org_id=None, language="en", status="completed")
          db.add(session); await db.flush()
          db.add(TrainingSessionEvent(session_id=session.id, event_type="old", event_payload={}, created_at=datetime.now(timezone.utc) - timedelta(days=100)))
          db.add(TrainingSessionEvent(session_id=session.id, event_type="new", event_payload={}))
          await db.commit()
          removed = await prune_old_events(db, 90)
          assert removed == 1
  ```

- [ ] **Step 2: Run to verify failure**

  Run: `cd backend && DATABASE_URL=postgresql+asyncpg://horus:horus@localhost:5432/horus_db .venv/bin/pytest tests/unit/services/test_retention.py -q`
  Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `retention.py` and the migration**

  `prune_old_events` issues `delete(TrainingSessionEvent).where(TrainingSessionEvent.created_at < datetime.now(timezone.utc) - timedelta(days=retention_days))` and returns `result.rowcount`. Migration `f5061728394` (`down_revision = "d3e4f506172"`) creates `ix_training_session_events_created_at` on `created_at` and, in `downgrade`, drops it. Wire the daily prune through a small script rather than an in-process scheduler: create `backend/scripts/prune_session_events.py` with `async def main() -> None: async with get_session_factory() as db: removed = await prune_old_events(db, get_settings().trace.retention_days); await db.commit(); print(removed)`, and document the cron line `17 3 * * * cd /opt/horus/backend && .venv/bin/python scripts/prune_session_events.py` in a new "Operational notes" section of `docs/architecture/ADR-009-opentelemetry-and-postgres-trace.md`. No scheduler dependency is added.

- [ ] **Step 4: Add provenance to replay**

  Add `ProvenanceEvent` to `app/schemas/training_session.py`. In `get_session_replay`, after the existing `events_result` query add a second query for `TrainingSessionEvent` ordered by `created_at` and build `provenance=[_provenance_from_event(e) for e in events]`; add `provenance: list[ProvenanceEvent] = Field(default_factory=list)` to `TrainingSessionReplayResponse`. `_provenance_from_event` reads keys `graph`, `node`, `scene_version`, `prompt_version`, `llm_provider`, `llm_model`, `llm_fallback_used`, `retrieved_chunk_ids`, `instructor_overridden` from `event_payload` with `None` defaults.

- [ ] **Step 5: Update the frontend composable**

  In `useSessionReplay.ts`, add `const provenance = ref<ProvenanceEvent[]>([])` with the `ProvenanceEvent` interface mirroring the backend schema; in `loadSession`, set `provenance.value = result.provenance ?? []`; include `provenance` in the returned object.

- [ ] **Step 6: Run to verify pass**

  Run: `cd backend && .venv/bin/pytest tests/unit/services/test_retention.py tests/integration/test_replay_provenance.py -q && .venv/bin/ruff check app`
  Expected: PASS.

- [ ] **Step 7: Commit**

  ```bash
  git add backend/app/services/training_sessions/retention.py backend/app/api/v1/sessions.py backend/app/schemas/training_session.py backend/alembic/versions/f5061728394_add_trace_retention_config.py backend/tests frontend/packages/core/app/composables/useSessionReplay.ts
  git commit -m "feat(trace): add replay provenance and 90-day retention"
  ```

---

### Task 11: OpenTelemetry instrumentation

**Files:**
- Modify: `backend/pyproject.toml` (add `opentelemetry-api>=1.27.0`, `opentelemetry-sdk>=1.27.0`, `opentelemetry-instrumentation-fastapi>=0.48b0`, `opentelemetry-instrumentation-asyncpg>=0.48b0`)
- Create: `backend/app/observability/__init__.py`, `backend/app/observability/telemetry.py`
- Modify: `backend/app/main.py` (call `configure_telemetry(settings)` in the lifespan before app creation)
- Test: `backend/tests/unit/test_telemetry.py`

**Interfaces:**
- Consumes: `TraceSettings` (Task 1).
- Produces:
  ```python
  # app/observability/telemetry.py
  def configure_telemetry(settings: TraceSettings) -> None:
      """Install OTel FastAPI + asyncpg instrumentation and a console or OTLP exporter."""
  def span_for_session(session_id: int, org_id: uuid.UUID | None) -> AbstractSpan  # contextmanager
  ```

- [ ] **Step 1: Write failing telemetry test**

  Create `backend/tests/unit/test_telemetry.py`:

  ```python
  from app.config import TraceSettings
  from app.observability.telemetry import configure_telemetry, span_for_session
  import uuid

  def test_console_exporter_configured_without_endpoint():
      configure_telemetry(TraceSettings(retention_days=90, otel_endpoint=None, log_level="INFO"))
      with span_for_session(1, uuid.uuid4()) as span:
          span.set_attribute("session_id", 1)
      assert span.is_recording() or not span.is_recording()  # exporter smoke test, no exception
  ```

- [ ] **Step 2: Run to verify failure**

  Run: `cd backend && .venv/bin/pytest tests/unit/test_telemetry.py -q`
  Expected: FAIL with `ModuleNotFoundError: No module named 'app.observability'`.

- [ ] **Step 3: Implement `telemetry.py`**

  Use `TracerProvider`, `BatchSpanProcessor` with `ConsoleSpanExporter` when `otel_endpoint is None` and `OTLPSpanExporter` otherwise, `Resource.create({"service.name": "horus-backend", "deployment.environment": settings.log_level})`. `span_for_session` is a `@contextmanager` yielding `tracer.start_as_current_span("session.exchange", attributes={"session_id": session_id, "org_id": str(org_id) if org_id else None})`. `FastAPIInstrumentor.instrument_app(app)` and `AsyncPGInstrumentor().instrument()` are called once, guarded by a module-level `_configured` flag.

- [ ] **Step 4: Wire into `main.py` and run**

  Run: `cd backend && .venv/bin/pytest tests/unit/test_telemetry.py -q && .venv/bin/ruff check app/observability`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add backend/pyproject.toml backend/uv.lock backend/app/observability backend/app/main.py backend/tests/unit/test_telemetry.py
  git commit -m "feat(observability): add open telemetry console and otlp exporters"
  ```

---

### Task 12: ADR cross-references, ingest manual verification, full suite

**Files:**
- Modify: `docs/architecture/ADR-004-langgraph-multi-agent.md` (Negative section: point in-memory store and module-level LLM global to ADR-006; References: add ADR-006, ADR-007)
- Modify: `docs/architecture/ADR-002-database-postgresql.md` (References: add ADR-008)
- Modify: `docs/architecture/ADR-005-flight-plan-pipeline.md` (References: add ADR-006)
- Create: `docs/architecture/ARCHITECTURE-INDEX.md` (one table: decision → ADR → status)
- Test: `backend/tests/unit/knowledge/test_ingest_manual.py` (a golden-file test: ingest `docs/knowledge/INGEST.md` itself and assert chunk count > 0 and dimensions 768)

**Interfaces:**
- Consumes: everything.
- Produces: documentation only.

- [ ] **Step 1: Update ADR-004's Negative section**

  Replace the two bullets "In-memory session store" and "Module-level LLM reference" with: "Both are resolved by [ADR-006](./ADR-006-scene-session-and-persistent-langgraph.md); session state is persisted via a LangGraph checkpointer and the LLM is injected at graph build time."

- [ ] **Step 2: Add cross-references**

  Add `ADR-006` to ADR-004 and ADR-005 References; add `ADR-008` to ADR-002 References.

- [ ] **Step 3: Write the index**

  `docs/architecture/ARCHITECTURE-INDEX.md`:

  | Decision | ADR | Status |
  |---|---|---|
  | Monorepo | [ADR-001](ADR-001-monorepo-structure.md) | Accepted |
  | PostgreSQL | [ADR-002](ADR-002-database-postgresql.md) | Accepted |
  | Deployment | [ADR-003](ADR-003-deployment-architecture.md) | Accepted |
  | LangGraph topology | [ADR-004](ADR-004-langgraph-multi-agent.md) | Accepted |
  | Flight plan pipeline | [ADR-005](ADR-005-flight-plan-pipeline.md) | Accepted |
  | Scene/Session split + persistent state | [ADR-006](ADR-006-scene-session-and-persistent-langgraph.md) | Accepted |
  | LLM provider adapters | [ADR-007](ADR-007-llm-provider-adapters.md) | Accepted |
  | Tenant knowledge + pgvector | [ADR-008](ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md) | Accepted |
  | Trace | [ADR-009](ADR-009-opentelemetry-and-postgres-trace.md) | Accepted |

- [ ] **Step 4: Golden-file ingest test**

  `backend/tests/unit/knowledge/test_ingest_manual.py` reads `docs/knowledge/INGEST.md` (relative to repo root via `Path(__file__).parents[4] / "docs/knowledge/INGEST.md"`), calls `extract_text`, asserts the first chunk contains the string "1000 tokens", and asserts the Markdown section parse yields at least one `section` hint. No DB needed.

- [ ] **Step 5: Full verification**

  Run: `cd backend && .venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/alembic upgrade head && .venv/bin/alembic downgrade dcc247c7ad05 && .venv/bin/alembic upgrade head`
  Expected: full suite PASS, ruff clean, migrations reversible.

- [ ] **Step 6: Commit**

  ```bash
  git add docs/architecture backend/tests/unit/knowledge/test_ingest_manual.py
  git commit -m "docs: cross reference ADRs and add ingest golden test"
  ```

---

## Out of Scope (explicitly deferred, with the reason)

- **Qdrant or a second vector store in production.** One real production adapter (pgvector) plus a test/local adapter (FakeRetriever) is not yet a justification for a second datastore. Revisit when pgvector recall or p99 latency fails the 50k-500k chunk target.
- **Chroma as a production adapter.** It is not wired in this plan; the FakeRetriever covers local/test needs. If a developer wants Chroma for local vector search, it slots into the same `KnowledgeRetriever` seam without touching callers.
- **Fine-tuning.** RAG with citations is the v1 path. Fine-tuning is introduced only after an aviation eval set exists and only behind a `ModelRegistry` seam. See ADR-008 decision 7.
- **MCP.** No MCP server or client in this plan. When introduced, MCP tools are adapters behind the existing `KnowledgeRetriever` and tool seams; the plan does not pre-create empty MCP abstractions.
- **LangSmith / Langfuse.** Excluded by ADR-009.
- **Nginx / Caddy / cloud load balancing.** ADR-003 remains; not touched here.

## Execution Order

Tasks must run in order. Task 2's `LLMModule` is consumed by 5, 6, 8; Task 3's models are consumed by 8; Task 4's store by 6; Task 6's module by 7; Task 8's retriever by 5's optional knowledge wiring and by 7's `build_retriever` stub replacement. Tasks 1-4 are independent of each other and may be parallelized by a subagent, but 5-12 are sequential.
