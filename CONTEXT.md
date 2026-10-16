# Horus Aviation Training

Horus is a multi-tenant aviation training platform. It runs realistic ATC scenarios for student pilots and preserves every decision, exchange, and professional context for later review.

## Language

**Scene**:
A reusable training plan and initial context: aircraft, airports, route, weather preset, objectives, difficulty, and the knowledge a session may cite. A Scene is authored once and versioned; many Sessions run from it.
_Avoid_: Scenario template, flight plan (a Flight Plan is the pilot's own plan, not the Scene), session

**Session**:
One user's interaction with a Scene: transmissions, ATC responses, the decisions taken, the resulting debrief, and the provenance of every step. A Session is tenant-scoped and fully traceable after it ends.
_Not part of a Session today_: instructor overrides. The capability is built and tested but switched off in every deployment — no config field arms it and no route releases a held exchange, so `instructor_overridden` is always false. See [ADR-004](docs/architecture/ADR-004-langgraph-multi-agent.md#human-in-the-loop-hitl--built-not-exposed) and issue [#3](https://github.com/martinsgmx/horusone-mvp/issues/3).
_Avoid_: conversation, chat, run, session state (state is an implementation detail of a Session)

**Flight Plan**:
The pilot's own submitted plan for a particular flight (route, fuel, weight, aircraft). A Flight Plan can become the basis for a Session; it is not the same as a Scene.
_Avoid_: Scene, scenario

**Knowledge Document**:
An authored, versioned source of professional context (manual, SOP, regulation excerpt, FAQ) owned by a tenant or published platform-wide.
_Avoid_: article (an article is the human-readable presentation of a document), chunk

**Knowledge Chunk**:
A retrievable span of a Knowledge Document, carrying its embedding and citation coordinates. Chunks are the unit of retrieval, never authored by hand.
_Avoid_: embedding, vector (a vector is the numeric representation, not the content)

**Citation**:
A link from a Session exchange back to the exact Knowledge Chunk that informed it. Every live ATC exchange retrieves once — scoped to the tenant and the Scene's `knowledge_refs` — grounds the prompt on the retrieved text, and returns the matched chunks as `ExchangeResult.citations` (chunk, document, title, page, section, snippet). Provenance (`retrieved_chunk_ids` on the Session event) still records what each step used. See [ADR-008](docs/architecture/ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md).
_Avoid_: source, reference, provenance (provenance is the broader trace record; a Citation is one pointer inside it)

**Provenance**:
The durable record of which Scene version, prompt version, knowledge chunks, and model a Session used at each step. Provenance lives in Session events, not in application logs.
_Avoid_: log, trace span (logs and spans are operational; provenance is product data)

**Collaborator**:
A person with an active seat in a tenant who may author and manage that tenant's private knowledge. Collaborators do not automatically gain platform-wide publishing rights.
_Avoid_: staff, member, admin (a Collaborator may hold the `instructor`, `org-admin`, or `staff` seat role; the seat role is the authorization, the Collaborator is the person)

**Platform-Wide Knowledge**:
Knowledge Document whose owner is the platform itself and which every tenant may cite.
_Avoid_: global content, public content
