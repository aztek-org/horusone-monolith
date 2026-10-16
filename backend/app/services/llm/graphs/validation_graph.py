"""Validation graph — pre-flight flight-plan validation pipeline.

```mermaid
graph TD
    START([START]) --> gatekeeper
    gatekeeper --> weather_agent
    weather_agent --> fuel_agent
    fuel_agent --> route_agent
    route_agent --> airspace_agent
    airspace_agent --> performance_agent
    performance_agent --> check_all_passed{All passed?}
    check_all_passed -->|Yes| validation_ok[END ✅]
    check_all_passed -->|No - critical| validation_fail[END ❌]
```

The graph runs each validation agent in sequence so that later agents
can reference earlier results (e.g. the fuel agent can see the route
distances computed by the route agent — though in this version each
agent independently reads the flight plan state).

The final ``check_all_passed`` conditional node inspects all
``validation_results`` and sets ``validation_passed`` accordingly.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from typing import Any, Protocol

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.knowledge.types import RetrievalQuery
from app.services.llm.agents.airspace_agent import check_airspace_restrictions
from app.services.llm.agents.fuel_agent import calculate_fuel
from app.services.llm.agents.gatekeeper import validate_flight_plan
from app.services.llm.agents.performance_agent import analyze_performance
from app.services.llm.agents.route_agent import optimize_route
from app.services.llm.agents.weather_agent import analyze_weather
from app.services.llm.state import HorusState, SessionPhase, Severity

logger = logging.getLogger(__name__)


class KnowledgeRetriever(Protocol):
    """Structural knowledge-search dependency consumed by the graph."""

    async def search(self, query: Any) -> list[Any]: ...


class WeatherReports(Protocol):
    """Structural weather-fetch dependency consumed by the graph."""

    async def get_metar(self, icao: str) -> dict[str, Any]: ...

    async def get_taf(self, icao: str) -> dict[str, Any]: ...


def state_org_id(state: HorusState) -> uuid.UUID | None:
    """Return the tenant that owns the session, or ``None`` when none does.

    ``org_id`` is carried as a string because ``HorusState`` is persisted
    through LangGraph's JSON checkpointer, so it is parsed back here.  Returning
    ``None`` — rather than a placeholder tenant — is what keeps retrieval
    fail-closed: the retriever's predicate is
    ``org_id IS NULL OR org_id == <this value>``, so no tenant sees another
    tenant's chunks.
    """
    org_id = state.get("org_id")
    if not org_id:
        return None
    return org_id if isinstance(org_id, uuid.UUID) else uuid.UUID(str(org_id))


def _weather_node_factory(
    knowledge: KnowledgeRetriever | None,
    weather: WeatherReports | None,
) -> Any:
    """Add provider fetching and provenance retrieval to the weather analysis."""
    if knowledge is None and weather is None:
        return analyze_weather

    async def weather_node(state: HorusState) -> dict[str, Any]:
        fetched = None
        if weather is not None:
            fetched = await _fetch_weather_reports(weather, state.get("flight_plan") or {})
        result = analyze_weather(state, fetched)
        if knowledge is None:
            return result
        flight_plan = state.get("flight_plan") or {}
        query = RetrievalQuery(
            query=(
                f"departure_icao {flight_plan.get('departure_icao', '')} "
                f"arrival_icao {flight_plan.get('arrival_icao', '')} "
                f"flight_rules {flight_plan.get('flight_rules', 'VFR')}"
            ),
            org_id=state_org_id(state),
            top_k=5,
            knowledge_refs=list(state.get("knowledge_refs") or []),
            mode="hybrid",
        )
        chunks = await knowledge.search(query)
        return {
            **result,
            "retrieved_chunk_ids": [str(getattr(chunk, "chunk_id", chunk)) for chunk in chunks],
        }

    return weather_node


async def _fetch_weather_reports(
    weather: WeatherReports, flight_plan: Mapping[str, Any]
) -> dict[str, str]:
    """Fetch raw METAR/TAF text for a flight plan through a weather service."""
    dep_icao = flight_plan.get("departure_icao", "") or ""
    arr_icao = flight_plan.get("arrival_icao", "") or ""
    alt_icao = flight_plan.get("alternate_icao") or ""

    async def metar(icao: str) -> str:
        if not icao:
            return ""
        return str((await weather.get_metar(icao)).get("raw", ""))

    async def taf(icao: str) -> str:
        if not icao:
            return ""
        return str((await weather.get_taf(icao)).get("raw", ""))

    return {
        "departure_metar": await metar(dep_icao),
        "arrival_metar": await metar(arr_icao),
        "alternate_metar": await metar(alt_icao),
        "departure_taf": await taf(dep_icao),
        "arrival_taf": await taf(arr_icao),
    }


def _check_all_passed(state: HorusState) -> dict[str, Any]:
    """Inspect all validation results and set the final verdict.

    Returns:
        Partial state with ``validation_passed`` and ``phase``.
    """
    results = state.get("validation_results") or []

    has_critical = any(
        r.get("severity") == Severity.CRITICAL.value and not r.get("passed", True) for r in results
    )

    passed = not has_critical

    logger.info(
        "Validation verdict: %s (%d results, %s critical failures)",
        "PASSED" if passed else "FAILED",
        len(results),
        "with" if has_critical else "no",
    )

    return {
        "validation_passed": passed,
        "phase": SessionPhase.PRE_FLIGHT.value if passed else SessionPhase.VALIDATION.value,
    }


def build_validation_graph(
    knowledge: KnowledgeRetriever | None = None,
    weather: WeatherReports | None = None,
) -> CompiledStateGraph:
    """Build and compile the validation sub-graph.

    Args:
        knowledge: Optional retriever used to record weather citation IDs.
        weather: Optional async weather service used to fetch real METAR/TAF.
    """
    graph = StateGraph(HorusState)

    # ── Add nodes ─────────────────────────────────────────────────
    graph.add_node("gatekeeper", validate_flight_plan)
    graph.add_node("weather_agent", _weather_node_factory(knowledge, weather))
    graph.add_node("fuel_agent", calculate_fuel)
    graph.add_node("route_agent", optimize_route)
    graph.add_node("airspace_agent", check_airspace_restrictions)
    graph.add_node("performance_agent", analyze_performance)
    graph.add_node("check_all_passed", _check_all_passed)

    # ── Linear pipeline edges ─────────────────────────────────────
    graph.set_entry_point("gatekeeper")
    graph.add_edge("gatekeeper", "weather_agent")
    graph.add_edge("weather_agent", "fuel_agent")
    graph.add_edge("fuel_agent", "route_agent")
    graph.add_edge("route_agent", "airspace_agent")
    graph.add_edge("airspace_agent", "performance_agent")
    graph.add_edge("performance_agent", "check_all_passed")
    graph.add_edge("check_all_passed", END)

    compiled = graph.compile()
    logger.info("Validation graph compiled (%d nodes)", 7)
    return compiled
