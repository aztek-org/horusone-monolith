# Horus MVP — Optimization & Architecture Plan

## Problem Statement

Full-stack analysis reveals that Horus works as an MVP but has **critical scalability bottlenecks**, **incorrect LangGraph usage**, **memory leak risks**, and **missing production patterns**. This plan addresses optimization across all 4 layers: LangGraph agents, backend API, frontend apps, and infrastructure — focusing on functional behavior (no test changes).

## Approach

Organize into **5 phases** by severity. Each phase is independently committable. Work proceeds from critical architectural fixes (LangGraph, audio pipeline) through backend optimization, frontend hardening, and documentation.

---

## Phase 1 — LangGraph Architecture Fix (Critical)

The LangGraph implementation has fundamental design flaws: `ATCAgent` wraps a linear 3-node chain in an unnecessary `StateGraph`, conversation history is duplicated across two systems, the audio pipeline bypasses the orchestrator entirely, and there's no state persistence.

### 1.1 — Remove ATCAgent StateGraph Wrapper
- **File**: `backend/app/services/llm/atc_agent.py`
- **Problem**: 3-node linear graph (`understand → respond → evaluate`) with no branches, no conditionals — doesn't need LangGraph at all. Graph state is thrown away after each `ainvoke()`, conversation stored externally in a list.
- **Fix**: Replace with a simple async service class. Keep the `_understand`, `_respond`, `_evaluate` methods as plain async functions. Remove `StateGraph` import and compilation.
- **Example**:
  ```python
  class ATCService:
      async def generate_response(self, pilot_message, context, language):
          notes = self._understand(pilot_message)
          response = await self._respond(pilot_message, notes, context, language)
          metrics = self._evaluate(pilot_message, response, context)
          self.conversation_history.append({...})
          return response
  ```

### 1.2 — Unify Conversation History
- **Files**: `backend/app/services/llm/atc_agent.py`, `backend/app/services/llm/state.py`, `backend/app/services/llm/graphs/live_session_graph.py`
- **Problem**: Two independent conversation systems: `ATCAgent.conversation_history` (plain list) and `HorusState.messages` (LangGraph `add_messages` reducer). They never sync.
- **Fix**: Use `HorusState.messages` as the single source of truth. The new `ATCService` should read/write through the orchestrator's session state. Remove the standalone `conversation_history` list.

### 1.3 — Integrate Audio Pipeline with Orchestrator
- **Files**: `backend/app/core/audio_pipeline.py`, `backend/app/api/routes/voice.py`
- **Problem**: Voice pipeline creates its own `ATCAgent` instance (line 42), completely bypassing `HorusOrchestrator`. Flight plan validation results, scoring accumulation, HITL interrupts — none of these reach the voice path.
- **Fix**: Inject `HorusOrchestrator` into `AudioPipeline`. Route all `generate_response()` calls through `orchestrator.process_message(session_id, pilot_text)`. WebSocket handler passes `session_id` context.

### 1.4 — Add LLM Retry Logic & Timeouts
- **Files**: `backend/app/services/llm/graphs/live_session_graph.py`, `backend/app/core/audio_pipeline.py`
- **Problem**: Single LLM call attempt (line 113-131), immediate fallback on any error. No timeout — if Ollama hangs, WebSocket hangs forever.
- **Fix**: Add `tenacity` retry with exponential backoff (3 attempts, 2-10s wait). Wrap all LLM calls with `asyncio.wait_for(timeout=30)`. Add circuit breaker pattern for repeated failures.

### 1.5 — Parallelize Validation Graph
- **File**: `backend/app/services/llm/graphs/validation_graph.py`
- **Problem**: 6 validation agents run sequentially (`gatekeeper → weather → fuel → route → airspace → performance`) even though they're independent after the gatekeeper node. Currently ~60ms sequential; could be ~15ms parallel.
- **Fix**: Fan-out pattern — gatekeeper feeds all 5 validators concurrently, all 5 feed into `check_all_passed`.

### 1.6 — Add Session State Persistence
- **File**: `backend/app/services/llm/orchestrator.py`
- **Problem**: `self._sessions: dict[str, HorusState] = {}` — all session state lost on process restart. Can't scale horizontally.
- **Fix**: Replace in-memory dict with LangGraph's `PostgresCheckpointer` or `AsyncPostgresSaver`. Compile graphs with `checkpointer=`. Pass `thread_id=session_id` in all `ainvoke()` calls.

### 1.7 — Fix Module-Level LLM Global
- **File**: `backend/app/services/llm/graphs/live_session_graph.py`
- **Problem**: `_llm: Ollama | None = None` as module-level global (line 41-42). Not thread-safe if multiple workers access concurrently.
- **Fix**: Pass LLM instance via LangGraph `RunnableConfig` or inject through `build_live_session_graph()` parameters.

---

## Phase 2 — Backend Performance Optimization

### 2.1 — Increase DB Connection Pool
- **File**: `backend/app/db/session.py`
- **Problem**: `pool_size=10, max_overflow=20` (30 total). With WebSocket + REST serving 100+ users, pool exhausts fast.
- **Fix**: `pool_size=30, max_overflow=50, pool_recycle=3600`.

### 2.2 — Add Missing Database Indexes
- Alembic migration for `training_sessions(status)`, `training_sessions(scenario_id)`.

### 2.3 — Optimize Stats Aggregate Query
- **File**: `backend/app/db/repositories/student_stats_repository.py`
- **Problem**: `update_aggregates()` fires 3 separate queries per session completion.
- **Fix**: Combine into single query with `func.sum`, `func.count`, `func.avg`.

### 2.4 — Fix Blocking I/O in STT Service
- **File**: `backend/app/services/stt/whisper_service.py`
- **Problem**: `async def transcribe()` does blocking file writes and Whisper inference. Locks event loop.
- **Fix**: Wrap in `loop.run_in_executor()`. Use `aiofiles` for temp file I/O.

### 2.5 — Add Audio Pipeline Concurrency Control
- **Files**: `backend/app/core/audio_pipeline.py`, `backend/app/api/routes/voice.py`
- **Problem**: Single instance serves ALL users sequentially. 10 concurrent users = 10-minute queue.
- **Fix**: `asyncio.Semaphore(5)` to gate concurrent processing.

### 2.6 — Reduce TTS Format Conversions
- **File**: `backend/app/services/tts/tts_service.py`
- **Problem**: 4 format conversions per TTS call (gTTS→MP3→AudioSegment→WAV→numpy→WAV bytes).
- **Fix**: Stream MP3 bytes from `gTTS.write_to_fp()`, single pydub conversion to WAV.

### 2.7 — Cache Org Context per Request
- **File**: `backend/app/middleware/org_context.py`
- **Problem**: Every request does 2 DB calls (user lookup + seat lookup).
- **Fix**: Store in `request.state` for request-scoped caching.

### 2.8 — Add JWKS Cache TTL
- **File**: `backend/app/middleware/auth.py`
- **Problem**: `_jwks_cache` has no TTL. Stale keys after Keycloak rotation.
- **Fix**: Add `fetched_at` timestamp, re-fetch after 1 hour.

### 2.9 — Extract Duplicated Permission Logic
- **Files**: `backend/app/api/v1/sessions.py`, `backend/app/api/v1/stats.py`
- **Problem**: Same RBAC pattern duplicated across routes.
- **Fix**: Create `get_access_scope()` dependency returning `AccessScope(scope, org_id, user_id)`.

---

## Phase 3 — Frontend Optimization

### 3.1 — Fix useVoiceComm Memory Leaks
- **File**: `frontend/packages/core/app/composables/useVoiceComm.ts`
- **Problem**: `audioChunks` never cleared, `audioContext` no guaranteed cleanup, URL not revoked on error.
- **Fix**: Clear chunks after Blob creation. Add `onUnmounted()` cleanup. try/finally for stream cleanup.

### 3.2 — Add Request Timeout to useApi
- **File**: `frontend/packages/core/app/composables/useApi.ts`
- **Problem**: No timeout. Backend hang = frozen UI.
- **Fix**: `AbortSignal.timeout(15000)` default on all fetch calls.

### 3.3 — Create useFetch Composable
- **File**: Create `frontend/packages/core/app/composables/useFetch.ts`
- **Problem**: Every page duplicates `isLoading/error/try-catch-finally` pattern.
- **Fix**: `useFetch<T>(url)` returning `{ data, isLoading, error, refetch }`.

### 3.4 — Extract Large Page Logic into Composables
- **Files**: `assessments.vue` (877L), `stats.vue` (824L), `dashboard.vue` (569L)
- **Problem**: Pages have too much business logic (13+ refs, inline API calls).
- **Fix**: Extract to `useAssessmentSession.ts`, `useStatsData.ts`, `useDashboardData.ts`.

### 3.5 — Split God Components
- **Files**: `AppSettingsWorkspace.vue` (374L), `AppSidebar.vue` (370L), `StudentRoster.vue` (337L), `VoiceCommBubble.vue` (305L)
- **Fix**: Split each into 2-3 focused sub-components.

### 3.6 — Fix useAuth Timer Cleanup
- **File**: `frontend/packages/core/app/composables/useAuth.ts`
- **Problem**: `refreshTimer` not cleared in all logout paths.
- **Fix**: Clear in every logout/disconnect path. Guard callback with mounted check.

### 3.7 — Centralize Shared TypeScript Types
- **Create**: `frontend/packages/types/` package
- **Problem**: Types duplicated in composables and pages.
- **Fix**: Shared types package with all API response interfaces.

---

## Phase 4 — Infrastructure & DevOps

### 4.1 — Add Docker Resource Limits (all services)
### 4.2 — Fix Database Health Check Race Condition (add `start_period: 15s`)
### 4.3 — Deduplicate Keycloak Realm Files
### 4.4 — Remove Committed .env from Git

---

## Phase 5 — Documentation

### 5.1 — Update ADR-004 with actual LangGraph architecture
### 5.2 — Create production deployment runbook (`docs/deployment.md`)
### 5.3 — Add security documentation (`docs/security.md`)
### 5.4 — Sync development guide with actual state

---

## Score Summary

| Layer | Current | After Plan | Key Blocker |
|-------|---------|------------|-------------|
| LangGraph | 40/100 | 80/100 | Persistence, orchestrator integration |
| Backend | 65/100 | 85/100 | Audio pipeline bottleneck, blocking I/O |
| Frontend | 70/100 | 85/100 | Memory leaks, page complexity |
| Infra | 65/100 | 80/100 | Resource limits, health checks |
| Docs | 60/100 | 80/100 | Deployment, security docs |
