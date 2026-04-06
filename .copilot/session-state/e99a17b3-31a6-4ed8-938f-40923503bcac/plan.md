# Horus MVP — NEXT.md Implementation Plan

## Problem Statement

The core platform (auth, basic scenarios, voice pipeline, admin) works. NEXT.md defines the missing pieces to make Horus a **complete aviation training platform**: student stats, knowledge content, enriched scenarios with waypoints, flight plan planning with AI agents, instructor tools, gamification, and a full LangGraph multi-agent architecture.

## Approach

Build in **7 phases**, each independently deployable. Use the Copilot Fleet agents for domain-specific work. LangGraph is the orchestration backbone — every training flow runs through a state graph with specialized reasoning nodes.

---

## Phase 1 — Data Layer Foundation

Expand the database to support all NEXT.md features. New models, migrations, and seed data.

### 1.1 — Student Stats Models
- **New models**: `StudentStats`, `FlightHourLog`, `ManeuverLog`, `KnowledgeAssessment`, `AssessmentResult`
- `StudentStats`: user_id (FK), total_flight_hours, total_maneuvers, total_scenarios_completed, total_assessments, overall_score, updated_at
- `FlightHourLog`: id, user_id, session_id, hours_logged, maneuvers_practiced (JSONB), phase, created_at
- `KnowledgeAssessment`: id, title, description, module_id (FK), questions (JSONB), passing_score, created_by, org_id
- `AssessmentResult`: id, user_id, assessment_id, score, answers (JSONB), passed, completed_at
- **Agent**: `database-expert`

### 1.2 — Flight Training Content Models
- **New models**: `ContentCategory`, `ContentArticle`
- `ContentCategory`: id, name, slug, description, parent_id (self-referential), sort_order, icon
- `ContentArticle`: id, category_id (FK), title, slug, content (TEXT — markdown), summary, difficulty_level, tags (JSONB), author_id, org_id (nullable = platform-wide), is_published, created_at, updated_at
- Categories map to NEXT.md topics: Aviation Theory, Aircraft Systems, Aerodynamics, ATC Procedures, Regulations, Safety
- **Agent**: `database-expert`

### 1.3 — Enhanced Scenarios & Waypoints Models
- **New models**: `Waypoint`, `ScenarioWaypoint`, `SessionTrack`, `FlightInsight`
- `Waypoint`: id, name, type (waypoint/airport/VOR/fix/NDB), lat, lng, frequency (nullable), elevation (nullable)
- `ScenarioWaypoint`: scenario_id, waypoint_id, sequence_order, altitude_constraint, speed_constraint, notes
- `SessionTrack`: id, session_id (FK), track_points (JSONB array of {lat, lng, alt, heading, speed, timestamp}), recorded_at
- `FlightInsight`: id, session_id, type (deviation/performance/communication), severity, description, timestamp_in_session, metadata (JSONB)
- Add to `Scenario` model: `scenario_type` (VFR/IFR/emergency/cross_country/night/weather), `waypoints` relationship, `flight_plan_template` (JSONB)
- **Agent**: `database-expert`

### 1.4 — Flight Plan Models
- **New models**: `FlightPlan`, `FlightPlanLeg`
- `FlightPlan`: id, user_id, scenario_id (nullable), org_id (nullable), departure_icao, arrival_icao, alternate_icao, route_string, fuel_required, fuel_reserve, total_weight, max_weight, cg_position, weather_briefing (JSONB), airspace_restrictions (JSONB), notes (TEXT), source_type (form/ocr/text/image), status (draft/validated/approved/active/completed), created_at, updated_at
- `FlightPlanLeg`: id, flight_plan_id (FK), sequence, from_waypoint_id, to_waypoint_id, distance_nm, heading, altitude, estimated_time_minutes, fuel_burn, wind (JSONB)
- **Agent**: `database-expert`

### 1.5 — Instructor & Gamification Models
- **New models**: `InstructorProfile`, `Badge`, `UserBadge`, `LeaderboardSnapshot`
- `InstructorProfile`: user_id (FK, unique), qualifications (JSONB), certifications (JSONB), bio, specializations (JSONB), availability (JSONB — schedule), rating (float)
- `Badge`: id, name, slug, description, icon, criteria (JSONB), category (flight/communication/knowledge/streak), tier (bronze/silver/gold/platinum)
- `UserBadge`: user_id, badge_id, earned_at, metadata (JSONB)
- `LeaderboardSnapshot`: id, org_id, period (daily/weekly/monthly), data (JSONB), generated_at
- **Agent**: `database-expert`

### 1.6 — Alembic Migration & Seed Data
- Single migration for all new models
- Seed data: sample content articles (aviation theory basics), waypoints (major US airports, common VORs), badges (First Flight, 10 Hours, Phraseology Master, etc.), sample flight plan
- **Agent**: `database-expert`

---

## Phase 2 — Backend API Layer

New API endpoints, repositories, schemas, and services for all new models.

### 2.1 — Student Stats API
- `GET /api/v1/stats/me` — current user stats summary
- `GET /api/v1/stats/{user_id}` — stats for specific user (instructor/admin only)
- `GET /api/v1/stats/me/flight-hours` — flight hour log with filters
- `GET /api/v1/stats/me/maneuvers` — maneuver history
- `GET /api/v1/stats/me/assessments` — assessment results
- `GET /api/v1/stats/me/transcript/{session_id}` — download session transcript (PDF/JSON)
- Repository: `StudentStatsRepository` — auto-aggregation from session/voice_log data
- **Agent**: `python-fastapi-expert`

### 2.2 — Flight Training Content API
- `GET /api/v1/content/categories` — tree of categories
- `GET /api/v1/content/categories/{slug}` — category with articles
- `GET /api/v1/content/articles/{slug}` — single article
- `POST /api/v1/content/articles` — create article (instructor/admin)
- `PUT /api/v1/content/articles/{id}` — update article
- `GET /api/v1/content/search?q=` — full-text search across articles (pg_tsvector)
- **Agent**: `python-fastapi-expert`

### 2.3 — Enhanced Scenarios API
- Extend `POST /api/v1/scenarios` with scenario_type, waypoints, flight_plan_template
- `GET /api/v1/scenarios/{id}/waypoints` — ordered waypoints for scenario
- `POST /api/v1/scenarios/{id}/waypoints` — add waypoints to scenario
- `GET /api/v1/sessions/{id}/track` — session flight track for map replay
- `GET /api/v1/sessions/{id}/insights` — AI-generated flight insights
- `GET /api/v1/waypoints?type=&near_lat=&near_lng=&radius=` — search waypoints
- **Agent**: `python-fastapi-expert`

### 2.4 — Flight Plan API
- `POST /api/v1/flight-plans` — create from form data
- `POST /api/v1/flight-plans/from-text` — create from plain text (AI parses)
- `POST /api/v1/flight-plans/from-image` — create from image/OCR (AI extracts)
- `GET /api/v1/flight-plans` — list user's flight plans
- `GET /api/v1/flight-plans/{id}` — full flight plan with legs
- `PUT /api/v1/flight-plans/{id}` — update
- `POST /api/v1/flight-plans/{id}/validate` — run validation (triggers Gatekeeper agent)
- `POST /api/v1/flight-plans/{id}/activate` — activate for training session
- **Agent**: `python-fastapi-expert`

### 2.5 — Instructor & Gamification API
- `GET /api/v1/instructors/{user_id}/profile` — instructor profile
- `PUT /api/v1/instructors/me/profile` — update own profile
- `GET /api/v1/instructors?org_id=&specialization=` — search instructors
- `GET /api/v1/gamification/badges` — all available badges
- `GET /api/v1/gamification/me/badges` — user's earned badges
- `GET /api/v1/gamification/leaderboard?period=&org_id=` — leaderboard
- `POST /api/v1/gamification/check` — trigger badge evaluation for user (internal)
- **Agent**: `python-fastapi-expert`

### 2.6 — Knowledge Assessment API
- `GET /api/v1/assessments` — list assessments for user's modules
- `GET /api/v1/assessments/{id}` — get assessment questions
- `POST /api/v1/assessments/{id}/submit` — submit answers, get score
- `POST /api/v1/assessments` — create assessment (instructor/admin)
- **Agent**: `python-fastapi-expert`

---

## Phase 3 — LangGraph Multi-Agent Architecture

The core intelligence layer. Refactor the existing 3-node ATC agent into a full multi-agent graph with specialized reasoning nodes.

### 3.1 — Agent State & Graph Orchestrator
- Refactor `AgentState` to support multi-agent routing
- New state fields: `flight_plan`, `weather_data`, `fuel_state`, `airspace_info`, `validation_errors`, `scoring`, `phase` (ingestion/validation/evaluation/live/debrief/scoring)
- Create `HorusOrchestrator` — top-level StateGraph that routes to sub-agents
- Pipeline: Ingestion → Validation → Evaluation → Live → Evaluation → Scoring
- Mermaid documentation for every graph
- **Agent**: `llm-expert`

### 3.2 — Gatekeeper Node
- Validates flight plan consistency: route continuity, fuel sufficiency, weight limits, airspace compliance
- Schema validation using Pydantic
- Returns structured validation errors with severity levels
- Runs before any live session starts
- **Agent**: `llm-expert`

### 3.3 — Reasoning Nodes (Weather, Fuel, Route, Airspace)
- **WeatherAgent**: Fetch/analyze weather data (METAR/TAF), determine flight category (VFR/MVFR/IFR/LIFR), suggest alternates. External API stub with mock data for dev.
- **FuelAgent**: Calculate fuel burn per leg, reserves, endurance. Factor wind, altitude, aircraft performance.
- **RouteAgent**: Optimize route, suggest alternates, calculate ETAs per leg. Use waypoint database.
- **AirspaceAgent**: Check route against airspace restrictions (Class A/B/C/D/E/G), TFRs, NOTAMs.
- Each agent: standalone function callable from graph, returns typed result, documented with mermaid
- **Agent**: `llm-expert`

### 3.4 — Reasoning Nodes (Aircraft Performance, Emergency, ATC)
- **AircraftPerformanceAgent**: V-speeds, climb/descent rates, service ceiling based on weight/altitude/temp
- **EmergencyProceduresAgent**: Detect emergency keywords, provide procedural guidance, track emergency state
- **ATCAgent**: Refactored from existing — now a sub-agent within orchestrator. Enhanced with conditional edges (readback verification, correction loops). Human-in-the-loop support.
- **Agent**: `llm-expert`

### 3.5 — Tier Nodes (Student Progression & Gamification)
- **StudentTierNode**: Evaluate student performance, adjust difficulty, track progression metrics
- **GamificationNode**: After each session — check badge criteria, update leaderboard, generate achievement notifications
- Scoring rubric: communication accuracy, decision quality, procedure adherence, response time
- **Agent**: `llm-expert`

### 3.6 — Session Pipeline (Ingestion → Scoring)
- **Ingestion**: Parse flight plan (form, text, or OCR image), normalize data, create session
- **Validation**: Run Gatekeeper + all reasoning agents on flight plan
- **Pre-flight Evaluation**: Weather briefing, fuel check, weight & balance
- **Live Stage**: Real-time ATC interaction with human-in-the-loop. Emulate flight phases, time lapse, waypoint progression. Rewind capability.
- **Post-flight Evaluation**: Analyze transcript, generate insights, black box replay data
- **Scoring & Feedback**: Aggregate scores, award badges, generate downloadable report
- **Agent**: `llm-expert`

---

## Phase 4 — Frontend: Student Stats & Content

### 4.1 — Student Stats Dashboard
- New page: `/stats` — comprehensive student statistics
- Flight hours chart (line/bar over time)
- Maneuvers practiced breakdown (pie/donut)
- Scenarios completed with difficulty distribution
- Assessment scores timeline
- Downloadable transcripts (link to PDF/JSON endpoint)
- Progress tracking widgets
- **Agent**: `nuxt-expert`

### 4.2 — Flight Training Content (Knowledge Base)
- New page: `/knowledge` — browsable knowledge base
- Category tree sidebar navigation
- Article viewer with markdown rendering
- Search bar with full-text results
- Difficulty badges on articles
- Breadcrumb navigation
- **Agent**: `nuxt-expert`

### 4.3 — Knowledge Assessments UI
- New page: `/assessments` — list available assessments
- Assessment taking interface (question by question)
- Results page with score, correct/incorrect breakdown
- Link from knowledge articles to related assessments
- **Agent**: `nuxt-expert`

---

## Phase 5 — Frontend: Enhanced Scenarios & Flight Plans

### 5.1 — Scenario Enhancement
- Extend scenario creation: scenario type selector (VFR/IFR/emergency/etc.)
- Waypoint editor on map (drag & drop)
- Scenario preview with full waypoint route on map
- Session history with track replay on map
- Flight insights timeline alongside track replay
- **Agent**: `nuxt-expert`

### 5.2 — Flight Plan Builder
- New page: `/flight-plan` — flight plan creation & management
- Three input modes: Form (structured fields), Text (paste plain text), Image (upload & OCR)
- Route visualization on map with legs
- Fuel calculator panel
- Weight & balance calculator (visual CG diagram)
- Weather integration panel (METAR/TAF display)
- Airspace overlay on map
- Validation status panel (Gatekeeper results)
- **Agent**: `nuxt-expert`

### 5.3 — Session History & Replay
- Enhance `/mission/[id]` for post-session review
- Track replay on map (animated aircraft marker along track points)
- Voice transcript timeline (synced with track)
- Insights annotations on map and timeline
- Scoring breakdown with radar chart
- Export session report (PDF)
- **Agent**: `nuxt-expert`

---

## Phase 6 — Frontend: Instructor Tools & Gamification

### 6.1 — Instructor Dashboard
- New page: `/instructor` — instructor-specific view
- Student roster with progress overview
- Scenario assignment interface
- Performance comparison across students
- Assessment creation wizard
- Feedback/notes per student
- **Agent**: `nuxt-expert`

### 6.2 — Gamification UI
- Badges gallery (all available badges with criteria)
- User badge showcase (earned badges with dates)
- Leaderboard page (daily/weekly/monthly, org-scoped)
- Achievement notifications (toast on badge earn)
- Progress bars toward next badge tier
- **Agent**: `nuxt-expert`

### 6.3 — Instructor Profile & Scheduling
- Instructor profile page (qualifications, specializations, bio)
- Availability calendar view
- Student communication interface (basic messaging or notes)
- **Agent**: `nuxt-expert`

---

## Phase 7 — Integration, Documentation & Seed Data

### 7.1 — End-to-End Integration
- Wire all frontend pages to backend APIs
- Ensure all LangGraph agents are callable from API endpoints
- WebSocket enhancements: live waypoint progression events, real-time scoring updates
- **Agent**: `python-fastapi-expert` + `nuxt-expert`

### 7.2 — Seed Data & Examples
- Comprehensive seed data: content articles for each category, sample waypoints (US major airports, VORs, fixes), sample flight plans, sample assessments, badges
- First-time startup shows populated platform with examples of everything
- **Agent**: `database-expert`

### 7.3 — Documentation
- ADR for LangGraph multi-agent architecture
- ADR for flight plan pipeline
- Mermaid diagrams for all LangGraph graphs
- Update development.md with new endpoints and features
- Update README.md with new features list
- API documentation (docstrings on all endpoints)
- **Agent**: `document-agent`

### 7.4 — External Service Stubs
- Weather API stub (mock METAR/TAF data for dev, interface ready for real API)
- Airspace API stub (mock airspace boundaries, interface ready for real API)
- OCR service stub (Tesseract or cloud OCR interface for flight plan images)
- **Agent**: `python-fastapi-expert`

---

## Agent Assignment Summary

| Agent | Phases |
|-------|--------|
| `database-expert` | 1.1–1.6, 7.2 |
| `python-fastapi-expert` | 2.1–2.6, 7.1, 7.4 |
| `llm-expert` | 3.1–3.6 |
| `nuxt-expert` | 4.1–4.3, 5.1–5.3, 6.1–6.3, 7.1 |
| `document-agent` | 7.3 |
| `security-expert` | Review after Phase 2 & 7 |

## Execution Order

Phase 1 → Phase 2 → Phase 3 (can parallel with Phase 2) → Phase 4 → Phase 5 → Phase 6 → Phase 7

## Notes

- **No tests during implementation** (per NEXT.md) — write test stubs but skip execution
- **LangGraph best practices**: StateGraph, typed state, conditional edges, human-in-the-loop checkpoints
- **Database**: Leverage pg_jsonb for flexible metadata, pg_tsvector for content search
- **GraphQL**: Consider for complex dashboard queries only if REST becomes unwieldy
- **External APIs**: Stub with mock data; design interfaces for real API plug-in later
- **OCR**: Flight plan from image via Tesseract locally — keep behind interface
