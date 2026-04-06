# ADR-004: LangGraph Multi-Agent Architecture

**Status**: Accepted
**Date**: 2025-07-14

## Context

Horus is an aviation training platform where student pilots practice ATC communication
against AI controllers. The initial MVP used a single Ollama LLM call per exchange — a
stateless prompt-in / response-out design. As the platform grew to include flight plan
validation, real-time emergency detection, post-session scoring, and gamification, a
single LLM call could no longer handle the breadth of reasoning required.

We needed an architecture that:

1. Decomposes aviation reasoning into **specialist domains** (weather, fuel, airspace, …)
   so each concern is independently testable and evolvable.
2. Supports a **multi-phase training lifecycle** — ingestion, validation, live ATC
   session, post-flight evaluation, and scoring.
3. Allows **human-in-the-loop (HITL)** so instructors can override AI-generated ATC
   responses before they reach the student.
4. Keeps state in a single, typed object so every agent can read context set by earlier
   agents (e.g., the fuel agent can reference route distances from the route agent).

## Decision

We adopt **LangGraph `StateGraph`** as the orchestration framework, with a top-level
`HorusOrchestrator` class that composes **three compiled sub-graphs** and **nine
specialized reasoning agents**.

### Orchestrator

The `HorusOrchestrator` (`backend/app/services/llm/orchestrator.py`) exposes three
lifecycle methods:

| Method | Pipeline phase | Sub-graph invoked |
|--------|---------------|-------------------|
| `start_session()` | Ingestion → Validation → Pre-flight | `validation_graph` |
| `process_message()` | Live ATC exchange | `live_session_graph` |
| `end_session()` | Post-flight → Scoring → Badges | `scoring_graph` |

Each session's state is a single `HorusState` TypedDict that flows through every node.

```mermaid
graph LR
    subgraph Ingestion
        A[start_session] --> B[validation_graph]
    end
    subgraph Live
        C[process_message] --> D[live_session_graph]
    end
    subgraph Scoring
        E[end_session] --> F[scoring_graph]
    end
    B --> C
    D --> E
```

### Shared State

All agents share one `HorusState` TypedDict (`backend/app/services/llm/state.py`).
Sub-states are nested TypedDicts so each agent reads and writes only its slice:

| State slice | Owner agent(s) | Key fields |
|-------------|---------------|------------|
| `flight_plan` | Input / Gatekeeper | `departure_icao`, `arrival_icao`, `route`, `fuel_on_board`, … |
| `weather` | Weather | `departure_metar`, `flight_category`, `hazards`, `briefing_text` |
| `fuel_state` | Fuel | `total_burn`, `reserve_available`, `sufficient`, per-leg breakdown |
| `route_info` | Route | `total_distance_nm`, per-leg heading/ETE, `suggestions` |
| `airspace_info` | Airspace | `intersections`, `required_clearances`, `required_equipment` |
| `aircraft_performance` | Performance | `v_speeds`, `density_altitude`, `altitude_ok` |
| `validation_results` | All validation agents | List of `{agent, passed, severity, message}` |
| `pilot_message` / `atc_response` | Live session | Current exchange text |
| `scoring` | StudentTier | `communication_score`, `overall_score`, `grade`, … |
| `badges_earned` | Gamification | List of badge slugs |

The `messages` field uses LangGraph's `add_messages` reducer for automatic merge of
conversation history.

### Session Phases

The pipeline progresses through seven phases defined in `SessionPhase`:

```
INGESTION → VALIDATION → PRE_FLIGHT → ACTIVE → POST_FLIGHT → SCORING → COMPLETE
```

### Sub-Graph 1: Validation Graph

**File**: `backend/app/services/llm/graphs/validation_graph.py`

Runs at session start to validate the student's flight plan before entering the live
ATC simulation. Six agents execute in sequence so later agents can reference earlier
results.

```mermaid
graph TD
    START([START]) --> gatekeeper
    gatekeeper --> weather_agent
    weather_agent --> fuel_agent
    fuel_agent --> route_agent
    route_agent --> airspace_agent
    airspace_agent --> performance_agent
    performance_agent --> check_all_passed{All passed?}
    check_all_passed -->|Yes| validation_ok([END ✅])
    check_all_passed -->|No — critical| validation_fail([END ❌])
```

| Node | Agent | Responsibility |
|------|-------|---------------|
| `gatekeeper` | Gatekeeper | Structural validation: ICAO codes, route continuity, fuel > 0, weight limits, IFR alternate |
| `weather_agent` | Weather | Fetch METAR/TAF, determine flight category, extract hazards, generate briefing |
| `fuel_agent` | Fuel | Per-leg fuel burn, legal reserve check (VFR 30 min / IFR 45 min) |
| `route_agent` | Route | Distance, heading, ETE per leg; detect route inefficiency |
| `airspace_agent` | Airspace | Airspace class intersections, required clearances/equipment |
| `performance_agent` | Performance | V-speeds, density altitude, service ceiling check |
| `check_all_passed` | (built-in) | Aggregates all `validation_results`; fails on any `CRITICAL` severity |

### Sub-Graph 2: Live Session Graph

**File**: `backend/app/services/llm/graphs/live_session_graph.py`

Handles a **single pilot → ATC exchange**. The orchestrator invokes this once per pilot
transmission; conversation history accumulates in `HorusState.messages`.

```mermaid
graph TD
    START([START]) --> understand_input
    understand_input --> check_emergency{Emergency?}
    check_emergency -->|Yes| emergency_handler
    check_emergency -->|No| generate_atc_response
    emergency_handler --> evaluate_exchange
    generate_atc_response --> evaluate_exchange
    evaluate_exchange --> END([END])
```

| Node | Responsibility |
|------|---------------|
| `understand_input` | Classify pilot transmission: detect phraseology errors, positive patterns, and emergency keywords |
| `emergency_handler` | Classify emergency type (MAYDAY, PAN PAN, engine failure, etc.) and generate procedural ATC response from templates |
| `generate_atc_response` | Build context-aware prompt and invoke Ollama LLM for standard ATC response |
| `evaluate_exchange` | Increment exchange counter, update session phase detail (taxi → takeoff → cruise → …) |

#### Human-in-the-Loop (HITL)

When compiled with `interrupt_before=["generate_atc_response"]`, the graph pauses
before the ATC response node. An instructor can inspect and modify the state, then
resume the graph. This is controlled by the `enable_hitl` flag on `HorusOrchestrator`.

### Sub-Graph 3: Scoring Graph

**File**: `backend/app/services/llm/graphs/scoring_graph.py`

Runs after the session ends to evaluate performance and award badges.

```mermaid
graph TD
    START([START]) --> student_eval["StudentTier: evaluate_student"]
    student_eval --> badge_check["Gamification: check_badges"]
    badge_check --> generate_report["Generate report"]
    generate_report --> END([END])
```

| Node | Agent | Responsibility |
|------|-------|---------------|
| `student_eval` | StudentTier | Heuristic scoring: communication (35%), decisions (25%), procedures (25%), engagement (15%). Outputs grade A–F. |
| `badge_check` | Gamification | Evaluates 12 badge criteria against session scoring + cumulative student stats. Awards new badges. |
| `generate_report` | (built-in) | Assembles a formatted post-flight report with scores, strengths, improvements, badges, and session notes. |

### Agent Summary

| # | Agent | Graph | LLM required? | Description |
|---|-------|-------|---------------|-------------|
| 1 | **Gatekeeper** | Validation | No | Structural flight plan validation (ICAO codes, fuel, weight, route) |
| 2 | **Weather** | Validation | No (stub) | METAR/TAF fetch, flight category, hazard detection |
| 3 | **Fuel** | Validation | No | Per-leg fuel burn, reserve calculation |
| 4 | **Route** | Validation | No | Distance, heading, ETE, route optimization suggestions |
| 5 | **Airspace** | Validation | No | Airspace class intersections, clearance/equipment requirements |
| 6 | **Performance** | Validation | No | V-speeds, density altitude, service ceiling |
| 7 | **Emergency** | Live session | No | Emergency keyword detection, procedural response templates |
| 8 | **StudentTier** | Scoring | No | Heuristic performance evaluation (communication, decisions, procedures) |
| 9 | **Gamification** | Scoring | No | Badge criteria evaluation (12 badges across 4 categories) |

> The `generate_atc_response` node in the live session graph is the **only node that
> calls the LLM** (Ollama). All other agents use deterministic logic, calculation tools,
> or stub data — making them fast, predictable, and independently testable.

### Full Pipeline Overview

```mermaid
sequenceDiagram
    participant Student
    participant API as FastAPI
    participant Orch as HorusOrchestrator
    participant VG as Validation Graph
    participant LG as Live Session Graph
    participant SG as Scoring Graph

    Student->>API: POST /flight-plans (create plan)
    Student->>API: POST /sessions (start session)
    API->>Orch: start_session(flight_plan)
    Orch->>VG: ainvoke(state)
    Note over VG: Gatekeeper → Weather → Fuel<br/>→ Route → Airspace → Performance
    VG-->>Orch: validated state
    Orch-->>API: session_id + validation results

    loop Each radio exchange
        Student->>API: WebSocket pilot_message
        API->>Orch: process_message(session_id, text)
        Orch->>LG: ainvoke(state)
        Note over LG: Understand → Emergency?<br/>→ ATC Response → Evaluate
        LG-->>Orch: atc_response
        Orch-->>API: ATC audio response
        API-->>Student: WebSocket audio
    end

    Student->>API: End session
    API->>Orch: end_session(session_id)
    Orch->>SG: ainvoke(state)
    Note over SG: StudentTier → Badges → Report
    SG-->>Orch: scoring + badges + report
    Orch-->>API: post-flight report
    API-->>Student: Session results
```

## Consequences

### Positive

- **Separation of concerns** — each agent is a standalone function with clear
  inputs/outputs. New agents (e.g., NOTAMs, weight-and-balance) can be added by
  writing a function and inserting a node in the graph.
- **Independent testability** — agents are pure functions of `HorusState` → partial
  state dict. Unit tests don't need the LLM or any external service.
- **Human-in-the-loop** — the live session graph natively supports instructor override
  via LangGraph's `interrupt_before` mechanism.
- **Deterministic validation** — 8 of 9 agents use no LLM, making pre-flight checks
  fast (~50ms) and reproducible.
- **Typed state** — `HorusState` TypedDict catches field-name typos at type-check time.
- **Extensible pipeline** — the `SessionPhase` enum and graph structure map directly
  to real-world flight training phases, making the system intuitive for aviation
  domain experts.

### Negative

- **In-memory session store** — session state is stored in a Python dict. This limits
  the system to a single process. Production deployment should swap this for Redis or
  PostgreSQL-backed state.
- **Sequential validation** — validation agents run in series. If agents don't depend
  on each other's output, they could be parallelized with LangGraph fan-out nodes.
- **Module-level LLM reference** — the live session graph uses a global `_llm` variable
  set at build time. This works for single-model deployments but would need refactoring
  for multi-model setups.

### Neutral

- **LangGraph dependency** — adds ~5 MB to the Python environment. The library is
  actively maintained by LangChain and well-suited for stateful agent pipelines.
- **Agent count will grow** — as the platform adds NOTAM checks, international
  procedures, and multi-crew scenarios, the graph will accumulate more nodes. This is
  manageable as long as each agent remains a focused, single-responsibility function.

## References

- [LangGraph documentation](https://langchain-ai.github.io/langgraph/)
- [LangGraph StateGraph API](https://langchain-ai.github.io/langgraph/reference/graphs/#langgraph.graph.StateGraph)
- Related ADR: [ADR-001: Monorepo Structure](./ADR-001-monorepo-structure.md)
- Related ADR: [ADR-005: Flight Plan Pipeline](./ADR-005-flight-plan-pipeline.md)
