"""Gamification agent — badge criteria evaluation and award.

Evaluates the current session results and cumulative student stats
against badge criteria.  Returns a list of newly-earned badge slugs.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.llm.state import HorusState

logger = logging.getLogger(__name__)

# ── Badge definitions ─────────────────────────────────────────────────
# Each badge has a slug, display name, description, category, tier,
# and an evaluation function that takes (scoring, context) → bool.

BADGE_DEFINITIONS: list[dict[str, Any]] = [
    {
        "slug": "first-flight",
        "name": "First Flight",
        "description": "Completed your first training session.",
        "category": "flight",
        "tier": "bronze",
        "evaluate": lambda scoring, ctx: ctx.get("total_sessions", 0) >= 1,
    },
    {
        "slug": "10-hour-pilot",
        "name": "10 Hour Pilot",
        "description": "Logged 10+ hours of flight training.",
        "category": "flight",
        "tier": "silver",
        "evaluate": lambda scoring, ctx: ctx.get("total_flight_hours", 0) >= 10.0,
    },
    {
        "slug": "50-hour-pilot",
        "name": "50 Hour Pilot",
        "description": "Logged 50+ hours of flight training.",
        "category": "flight",
        "tier": "gold",
        "evaluate": lambda scoring, ctx: ctx.get("total_flight_hours", 0) >= 50.0,
    },
    {
        "slug": "phraseology-master",
        "name": "Phraseology Master",
        "description": "Scored 95%+ on communication in a session.",
        "category": "communication",
        "tier": "gold",
        "evaluate": lambda scoring, ctx: scoring.get("communication_score", 0) >= 95,
    },
    {
        "slug": "clear-communicator",
        "name": "Clear Communicator",
        "description": "Scored 80%+ on communication in 3 consecutive sessions.",
        "category": "communication",
        "tier": "silver",
        "evaluate": lambda scoring, ctx: (
            scoring.get("communication_score", 0) >= 80
            and ctx.get("consecutive_comm_80", 0) >= 2  # this is the 3rd
        ),
    },
    {
        "slug": "perfect-session",
        "name": "Perfect Session",
        "description": "Achieved an overall score of 95+ in a single session.",
        "category": "flight",
        "tier": "platinum",
        "evaluate": lambda scoring, ctx: scoring.get("overall_score", 0) >= 95,
    },
    {
        "slug": "streak-3",
        "name": "3-Day Streak",
        "description": "Trained for 3 consecutive days.",
        "category": "engagement",
        "tier": "bronze",
        "evaluate": lambda scoring, ctx: ctx.get("current_streak", 0) >= 3,
    },
    {
        "slug": "streak-7",
        "name": "Weekly Warrior",
        "description": "Trained for 7 consecutive days.",
        "category": "engagement",
        "tier": "silver",
        "evaluate": lambda scoring, ctx: ctx.get("current_streak", 0) >= 7,
    },
    {
        "slug": "streak-30",
        "name": "Monthly Dedication",
        "description": "Trained for 30 consecutive days.",
        "category": "engagement",
        "tier": "gold",
        "evaluate": lambda scoring, ctx: ctx.get("current_streak", 0) >= 30,
    },
    {
        "slug": "emergency-handler",
        "name": "Emergency Handler",
        "description": "Successfully handled an emergency scenario.",
        "category": "procedures",
        "tier": "silver",
        "evaluate": lambda scoring, ctx: ctx.get("emergency_handled", False),
    },
    {
        "slug": "ace-grade",
        "name": "Ace",
        "description": "Earned an A grade in 5 sessions.",
        "category": "flight",
        "tier": "gold",
        "evaluate": lambda scoring, ctx: ctx.get("a_grade_count", 0) >= 5,
    },
    {
        "slug": "night-owl",
        "name": "Night Owl",
        "description": "Completed a session between 10 PM and 5 AM local time.",
        "category": "engagement",
        "tier": "bronze",
        "evaluate": lambda scoring, ctx: ctx.get("is_night_session", False),
    },
]


def check_badges(state: HorusState) -> dict[str, Any]:
    """Evaluate all badge criteria and return newly-earned badges.

    The ``context`` dict in state should contain cumulative student
    stats (total_sessions, total_flight_hours, current_streak, etc.)
    so badge criteria can reference historical data.

    Returns:
        Partial state update with ``badges_earned``.
    """
    scoring = state.get("scoring") or {}
    context = state.get("context") or {}
    already_earned: list[str] = list(state.get("badges_earned") or [])

    # Add emergency_handled flag from state
    if state.get("is_emergency", False):
        context = {**context, "emergency_handled": True}

    # Increment total_sessions (the current session counts)
    context = {**context, "total_sessions": context.get("total_sessions", 0) + 1}

    # Track A grades
    if scoring.get("grade") == "A":
        context = {**context, "a_grade_count": context.get("a_grade_count", 0) + 1}

    newly_earned: list[str] = []

    for badge_def in BADGE_DEFINITIONS:
        slug = badge_def["slug"]
        if slug in already_earned:
            continue  # Don't re-award

        try:
            if badge_def["evaluate"](scoring, context):
                newly_earned.append(slug)
                logger.info("Badge earned: %s (%s)", badge_def["name"], slug)
        except Exception as e:
            logger.warning("Error evaluating badge %s: %s", slug, e)

    all_badges = already_earned + newly_earned

    logger.info(
        "Gamification agent: %d new badges, %d total",
        len(newly_earned),
        len(all_badges),
    )

    return {"badges_earned": all_badges}
