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

`GenerationRequest` (`backend/app/llm/types.py`) carries `prompt`, `purpose`
(`atc_response`, `weather_briefing`, `student_evaluation`, `flight_plan_parse`,
`readback_evaluation`, `knowledge_embedding`), `scene_constraints`
(`SceneConstraints`: an optional `temperature` and an optional
`max_output_tokens`), and `language`.

> **Correction.** An earlier version of this text listed `GenerationRequest`
> fields as `prompt`, `purpose`, `max_output_tokens` and `scene_overrides`. Only
> `prompt` and `purpose` are fields of `GenerationRequest`. `max_output_tokens`
> and `temperature` live one level down, inside `scene_constraints`, and are
> optional overrides rather than request attributes; the purpose literal is
> `knowledge_embedding`, not `embedding_doc`. A `max_output_tokens` that is not an
> override is a deployment default: `LLM_MAX_OUTPUT_TOKENS` on
> `LLMSettings` (`app/config.py`).

`SceneConstraints` is the only place a Scene may change `temperature` or
`max_output_tokens`.

Adapters implemented in v1:

| Adapter | Generate | Embed | Role |
|---------|----------|-------|------|
| `ollama` | yes | yes | default, self-hosted, works offline |
| `groq` | yes | no | fallback for latency; requires `GROQ_API_KEY` |
| `fake` | deterministic | deterministic | tests only |
| `nvidia-nim` | yes | yes | config-only, built when the endpoint is supplied |

Routing policy, in config:

- `LLM_PROVIDER` selects the primary adapter (`ollama` by default).
- On timeout or transient provider error (`LLMTransientError`), the
  `FallbackLLM` wrapper tries `LLM_FALLBACK_PROVIDER` once, then raises. It is
  tried **at most** once, and only when the fallback is permitted — see the
  constraint below, which is stricter than this line used to suggest.
- Provider choice is a startup concern. No graph node contains provider logic.
- The embedding dimension returned by the primary embed adapter is recorded at
  ingest time and validated on every ingest. A dimension mismatch is a hard
  failure, not a silent re-embed.
- `nomic-embed-text` (768 dimensions) is the canonical embedding for v1.
  Swapping embedding models requires a new Alembic migration and a re-ingest,
  which is why the dimension is stored alongside the vector column.

### The external-fallback gate is narrower than the flag suggests

`FallbackLLM._fallback_is_permitted()` (`backend/app/llm/routing.py`) returns
`True` only when **both** of these hold:

1. `LLM_ALLOW_EXTERNAL_FALLBACK` is `true`; and
2. it is not the case that the fallback is external while the primary is
   internal.

So `LLM_ALLOW_EXTERNAL_FALLBACK` is a necessary condition, not a sufficient one.
With the pairing the templates ship — `LLM_PROVIDER=ollama` (internal) with
`LLM_FALLBACK_PROVIDER=groq` (external), which is what
`backend/.env.docker.example` declares — condition 2 fails, and **no value of
the flag can ever enable the fallback.** Setting
`LLM_ALLOW_EXTERNAL_FALLBACK=true` in that configuration changes nothing.

`provider_is_external` is `True` for `groq` and `nvidia-nim` and `False` for
`ollama` and `fake`. The gate therefore permits exactly two fallbacks: internal
to internal (the live availability case, e.g. `ollama` → another `ollama`
endpoint) and external to external (`groq` → `nvidia-nim`, where a failure of
one off-VPS provider may still reach another). It forbids the case the flag's
name implies it governs: escalating from a self-hosted primary to a hosted one.

This is stricter than the earlier text, not looser, and the stricter reading is
the safe one: private tenant data must not leave the deployment because someone
flipped a flag. But it means the flag is not the control an operator would
assume it is, and that is worth stating rather than leaving to be discovered.
The Consequence below is the real guarantee; the flag is the secondary one.

## Consequences

> **Standing rule.** A shipped default that contradicts an accepted decision is a
> defect, even when nothing errors — including the defaults this ADR introduced.
> The remedy is a regression test that asserts the **concrete value**, not
> merely that a value exists, and that covers **every surface that ships the
> value**, not only the code path. The rule, the four defaults that motivated it,
> and the tests that now guard them are recorded in
> [ADR-009](./ADR-009-opentelemetry-and-postgres-trace.md#shipped-defaults-are-part-of-the-contract).

### Positive

- Provider choice moves from call sites to one config field.
- Fake adapter makes the whole pipeline testable without Ollama or a network.
- The `FallbackLLM` wrapper keeps the live path working when a fallback that is
  permitted actually exists — for an internal→internal or external→external
  pairing. With the shipped `ollama` → `groq` pairing it does not, and says so
  by raising `LLMUnavailableError` with `fallback_attempted=False`.
- Scene-level temperature and token limits are versioned with the Scene, not
  hardcoded in a graph.

### Negative

- One extra interface to learn in every place that generates text.
- Groq sends prompts off the VPS; tenant data leaves the deployment. The
  internal→external escalation is refused structurally by
  `_fallback_is_permitted()`, and `LLM_ALLOW_EXTERNAL_FALLBACK=false` in
  production is the second, redundant guard. Neither is a Scene-level privacy
  setting: there is no per-Scene fallback switch today, so a Scene has no way to
  opt *in* to an external fallback.

### Neutral

- `langchain_community.Ollama` stays in use; only construction moves.
- `langchain-groq` is a new dependency.

## References

- [ADR-004: LangGraph Multi-Agent Architecture](./ADR-004-langgraph-multi-agent.md)
- [ADR-006: Scene/Session Split and Persistent LangGraph State](./ADR-006-scene-session-and-persistent-langgraph.md)
- [ADR-008: Tenant-Scoped Knowledge and pgvector Retrieval](./ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md)
- Index: [ARCHITECTURE-INDEX.md](./ARCHITECTURE-INDEX.md)
