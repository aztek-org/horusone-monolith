"""Reasoning agents for the Horus multi-agent system.

Each module exposes one or more **node functions** that accept
``HorusState`` and return a partial state update dict.  They can be
wired directly into a LangGraph ``StateGraph`` or called standalone
for unit-testing.

Modules
-------
gatekeeper
    Flight plan structural validation (route continuity, fuel, weight).
weather_agent
    METAR/TAF fetch, hazard identification, LLM briefing.
fuel_agent
    Per-leg fuel burn calculation and legal-reserve check.
route_agent
    Distance, heading, ETE computation; route optimisation suggestions.
airspace_agent
    Airspace class identification and requirement checks.
performance_agent
    Aircraft V-speeds, density altitude, service-ceiling validation.
emergency_agent
    Emergency keyword detection and procedural response generation.
student_tier
    Post-session student performance evaluation.
gamification
    Badge criteria evaluation and award.
"""
