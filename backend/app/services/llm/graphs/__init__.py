"""Composed LangGraph sub-graphs for the Horus training pipeline.

Modules
-------
validation_graph
    Pre-flight validation pipeline (gatekeeper → weather → fuel → route →
    airspace → performance → pass/fail decision).
live_session_graph
    Real-time ATC interaction graph with emergency detection and
    human-in-the-loop support.
scoring_graph
    Post-session evaluation and badge award pipeline.
"""
