# ADR-007: LLM Provider Adapters

**Status**: Accepted
**Date**: 2026-09-25

## Context

Horus currently constructs Ollama clients in two places with conflicting
hardcoded parameters: `temperature=0.7` in
`backend/app/services/llm/atc_agent.py` and `temperature=0.3` in
`backend/app/services/llm/graphs/live_session_graph.py`, plus
`num_predict=150` and a module-level `_llm` global.

The product wants to run on self-hosted Ollama today, on Groq for speed, and
eventually on NVIDIA NIM for self-hosted GPUs. Choosing a provider by editing
call sites or adding `if provider == ...` branches inside graph nodes would
scatter the decision across the whole pipeline and make it untestable.

## Decision

We introduce one LLM module with two operations:

```python
class LLMModule(Protocol):
    async def generate(self, request: GenerationRequest) -> GenerationResult: ...
    async def embed(self, texts: list[str]) -> EmbeddingResult: ...
```

`GenerationRequest` carries `prompt`, `purpose` (`atc_response`,
`weather_briefing`, `student_evaluation`, `flight_plan_parse`,
`readback_evaluation`, `embedding_doc`), `max_output_tokens`, and
`scene_overrides`. `scene_overrides` is the only place a Scene may change
`temperature` or `max_output_tokens`.

Adapters implemented in v1:

| Adapter | Generate | Embed | Role |
|---------|----------|-------|------|
| `ollama` | yes | yes | default, self-hosted, works offline |
| `groq` | yes | no | fallback for latency; requires `GROQ_API_KEY` |
| `fake` | deterministic | deterministic | tests only |
| `nvidia-nim` | yes | yes | config-only, built when the endpoint is supplied |

Routing policy, in config:

- `LLM_PROVIDER` selects the primary adapter (`ollama` by default).
- On timeout or transient provider error, the `FallbackRouter` tries
  `LLM_FALLBACK_PROVIDER` (`groq`) once, then raises.
- Provider choice is a startup concern. No graph node contains provider logic.
- The embedding dimension returned by the primary embed adapter is recorded at
  ingest time and validated on every ingest. A dimension mismatch is a hard
  failure, not a silent re-embed.
- `nomic-embed-text` (768 dimensions) is the canonical embedding for v1.
  Swapping embedding models requires a new Alembic migration and a re-ingest,
  which is why the dimension is stored alongside the vector column.

## Consequences

### Positive

- Provider choice moves from call sites to one config field.
- Fake adapter makes the whole pipeline testable without Ollama or a network.
- The `FallbackRouter` keeps the live path working when Ollama is down.
- Scene-level temperature and token limits are versioned with the Scene, not
  hardcoded in a graph.

### Negative

- One extra interface to learn in every place that generates text.
- Groq sends prompts off the VPS; tenant data leaves the deployment. Scenes
  marked private must forbid fallback to Groq, enforced by
  `LLM_ALLOW_EXTERNAL_FALLBACK=false` in production.

### Neutral

- `langchain_community.Ollama` stays in use; only construction moves.
- `langchain-groq` is a new dependency.

## References

- [ADR-004: LangGraph Multi-Agent Architecture](./ADR-004-langgraph-multi-agent.md)
- [ADR-006: Scene/Session Split and Persistent LangGraph State](./ADR-006-scene-session-and-persistent-langgraph.md)
- [ADR-008: Tenant-Scoped Knowledge and pgvector Retrieval](./ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md)
