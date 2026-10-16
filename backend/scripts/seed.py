"""Seed script for Horus ATC Voice Communication Platform.

Populates the database with realistic aviation training data for local
development.  The script is **idempotent** — it checks for existing rows
before inserting and can safely be run multiple times.

Usage:
    cd backend
    python -m scripts.seed            # seed (skip existing)
    python -m scripts.seed --reset    # truncate all tables, then seed
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

# ── Bootstrap logging before anything else ────────────────────────────────
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("scripts.seed")

# ── Ensure the app package is importable ──────────────────────────────────
# When invoked with `python -m scripts.seed` from `backend/`, the CWD is
# already on sys.path, but we guard against edge-cases.
from app.config import get_settings  # noqa: E402
from app.core.org_ids import org_id_for_slug  # noqa: E402
from app.db.session import get_engine, get_session_factory  # noqa: E402
from app.models.assessment import KnowledgeAssessment  # noqa: E402
from app.models.content import ContentArticle, ContentCategory  # noqa: E402
from app.models.flight_plan import FlightPlan, FlightPlanLeg  # noqa: E402
from app.models.gamification import Badge  # noqa: E402
from app.models.organization import Organization  # noqa: E402
from app.models.scenario import Scenario  # noqa: E402
from app.models.seat import Seat  # noqa: E402
from app.models.training_session import TrainingSession  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.voice_log import VoiceLog  # noqa: E402
from app.models.waypoint import Waypoint  # noqa: E402

# ── ANSI colour helpers (no external deps) ────────────────────────────────
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
RESET = "\033[0m"
CHECK = f"{GREEN}✔{RESET}"
CROSS = f"{RED}✘{RESET}"
ARROW = f"{CYAN}→{RESET}"


def _header(msg: str) -> None:
    print(f"\n{BOLD}{CYAN}{'═' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {msg}{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 60}{RESET}\n")


def _step(msg: str) -> None:
    print(f"  {ARROW} {msg}")


def _ok(msg: str) -> None:
    print(f"  {CHECK} {msg}")


def _skip(msg: str) -> None:
    print(f"  {DIM}  ⏭  {msg}{RESET}")


def _warn(msg: str) -> None:
    print(f"  {YELLOW}⚠  {msg}{RESET}")


def _fail(msg: str) -> None:
    print(f"  {CROSS} {RED}{msg}{RESET}")


# ══════════════════════════════════════════════════════════════════════════
#  Deterministic IDs
# ══════════════════════════════════════════════════════════════════════════

ORG_SLUG = "skybridge"
ORG_ID = org_id_for_slug(ORG_SLUG)

USERS_DATA: list[dict[str, str]] = [
    {
        "email": "admin@horusone.app",
        "display_name": "Horus Admin",
        "role": "platform-admin",
    },
    {
        "email": "sarah.mitchell@skybridge.aero",
        "display_name": "Captain Sarah Mitchell",
        "role": "admin",
    },
    {
        "email": "james.chen@skybridge.aero",
        "display_name": "First Officer James Chen",
        "role": "instructor",
    },
    {
        "email": "maria.santos@skybridge.aero",
        "display_name": "Cadet Maria Santos",
        "role": "student",
    },
    {
        "email": "alex.turner@skybridge.aero",
        "display_name": "Cadet Alex Turner",
        "role": "student",
    },
]


def _user_uuid(email: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, email)


# ══════════════════════════════════════════════════════════════════════════
#  Scenario definitions
# ══════════════════════════════════════════════════════════════════════════

SCENARIOS_DATA: list[dict[str, str | int]] = [
    {
        "name": "KJFK Ground Operations",
        "description": (
            "Practice ground movement and taxi clearances at John F. Kennedy "
            "International Airport. Handle runway crossings, hold-short instructions, "
            "and progressive taxi routing on one of the world's busiest airfields."
        ),
        "difficulty": 1,
        "airport_icao": "KJFK",
        "runway": "31L",
        "weather_preset": "VFR",
        "phase": "ground",
        "scenario_type": "VFR",
    },
    {
        "name": "KLAX ILS Approach 25L",
        "description": (
            "Execute a full ILS approach into Los Angeles International runway 25L. "
            "Manage speed restrictions, descend via the SADDE arrival, and configure "
            "for landing in instrument meteorological conditions."
        ),
        "difficulty": 3,
        "airport_icao": "KLAX",
        "runway": "25L",
        "weather_preset": "IFR",
        "phase": "approach",
        "scenario_type": "IFR",
    },
    {
        "name": "EGLL Standard Departure",
        "description": (
            "Depart London Heathrow via the WOBUN3F standard instrument departure "
            "from runway 27R. Comply with noise-abatement procedures and initial "
            "climb restrictions while transitioning to London Control."
        ),
        "difficulty": 2,
        "airport_icao": "EGLL",
        "runway": "27R",
        "weather_preset": "VFR",
        "phase": "departure",
        "scenario_type": "IFR",
    },
    {
        "name": "KATL Enroute Handoff",
        "description": (
            "Manage a sector-to-sector handoff over the Atlanta ARTCC airspace. "
            "Practice frequency changes, altitude assignments, and traffic advisories "
            "with multiple aircraft on frequency."
        ),
        "difficulty": 2,
        "airport_icao": "KATL",
        "runway": "08L",
        "weather_preset": "VFR",
        "phase": "enroute",
        "scenario_type": "VFR",
    },
    {
        "name": "OMDB Emergency Landing",
        "description": (
            "Handle a simulated single-engine failure during approach into Dubai "
            "International. Declare an emergency, receive priority vectors, and "
            "execute an ILS approach to runway 30R under degraded conditions."
        ),
        "difficulty": 4,
        "airport_icao": "OMDB",
        "runway": "30R",
        "weather_preset": "IFR",
        "phase": "approach",
        "scenario_type": "emergency",
    },
    {
        "name": "LFPG Pattern Work",
        "description": (
            "Fly the traffic pattern at Paris Charles de Gaulle on runway 09R. "
            "Practice position reports, sequencing behind traffic, and touch-and-go "
            "clearances in a high-density environment."
        ),
        "difficulty": 1,
        "airport_icao": "LFPG",
        "runway": "09R",
        "weather_preset": "VFR",
        "phase": "ground",
        "scenario_type": "VFR",
    },
]

# ══════════════════════════════════════════════════════════════════════════
#  Voice-log phraseology  (realistic ATC <-> Pilot exchanges)
# ══════════════════════════════════════════════════════════════════════════

# Session 1 — Maria on KJFK Ground (completed, 4 logs)
VOICE_LOGS_SESSION_1: list[dict[str, str | int]] = [
    {
        "role": "pilot",
        "transcript": (
            "Kennedy Ground, SkyBridge four-two-seven, at gate Bravo-seven, "
            "information Tango, request taxi to runway three-one left."
        ),
        "audio_duration_ms": 5200,
    },
    {
        "role": "atc",
        "transcript": (
            "SkyBridge four-two-seven, Kennedy Ground, taxi to runway three-one left "
            "via Bravo, Alpha, hold short of runway two-two right."
        ),
        "audio_duration_ms": 6100,
    },
    {
        "role": "pilot",
        "transcript": (
            "Taxi to runway three-one left via Bravo, Alpha, hold short "
            "two-two right, SkyBridge four-two-seven."
        ),
        "audio_duration_ms": 4800,
    },
    {
        "role": "atc",
        "transcript": (
            "SkyBridge four-two-seven, cross runway two-two right, continue taxi "
            "to runway three-one left via Alpha."
        ),
        "audio_duration_ms": 4500,
    },
]

# Session 2 — Alex on KLAX ILS (active, 2 logs)
VOICE_LOGS_SESSION_2: list[dict[str, str | int]] = [
    {
        "role": "pilot",
        "transcript": (
            "SoCal Approach, SkyBridge eight-one-niner, level flight level "
            "two-four-zero, SADDE arrival runway two-five left, information Romeo."
        ),
        "audio_duration_ms": 6400,
    },
    {
        "role": "atc",
        "transcript": (
            "SkyBridge eight-one-niner, SoCal Approach, descend and maintain "
            "seven thousand, expect ILS runway two-five left approach, reduce speed "
            "two-one-zero knots."
        ),
        "audio_duration_ms": 7800,
    },
]

# Session 3 — Maria on EGLL Departure (completed, 6 logs)
VOICE_LOGS_SESSION_3: list[dict[str, str | int]] = [
    {
        "role": "pilot",
        "transcript": (
            "Heathrow Tower, SkyBridge one-five-three, ready for departure runway two-seven right."
        ),
        "audio_duration_ms": 3800,
    },
    {
        "role": "atc",
        "transcript": (
            "SkyBridge one-five-three, Heathrow Tower, wind two-four-zero degrees "
            "eight knots, runway two-seven right, cleared for take-off."
        ),
        "audio_duration_ms": 5500,
    },
    {
        "role": "pilot",
        "transcript": ("Cleared for take-off runway two-seven right, SkyBridge one-five-three."),
        "audio_duration_ms": 3200,
    },
    {
        "role": "atc",
        "transcript": (
            "SkyBridge one-five-three, contact London Control one-two-seven "
            "decimal nine-two-five, good day."
        ),
        "audio_duration_ms": 4100,
    },
    {
        "role": "pilot",
        "transcript": (
            "London Control one-two-seven decimal nine-two-five, "
            "SkyBridge one-five-three, good day."
        ),
        "audio_duration_ms": 3900,
    },
    {
        "role": "atc",
        "transcript": (
            "SkyBridge one-five-three, London Control, radar contact, climb "
            "flight level one-eight-zero, WOBUN three-foxtrot departure."
        ),
        "audio_duration_ms": 5800,
    },
]


# ══════════════════════════════════════════════════════════════════════════
#  Database helpers
# ══════════════════════════════════════════════════════════════════════════

ORDERED_TABLES = [
    "assessment_results",
    "knowledge_assessments",
    "flight_plan_legs",
    "flight_plans",
    "flight_insights",
    "session_tracks",
    "maneuver_logs",
    "flight_hour_logs",
    "student_stats",
    "user_badges",
    "badges",
    "leaderboard_snapshots",
    "instructor_profiles",
    "content_articles",
    "content_categories",
    "scenario_waypoints",
    "waypoints",
    "user_preferences",
    "voice_logs",
    "training_sessions",
    "module_scenarios",
    "training_modules",
    "scenarios",
    "seats",
    "users",
    "organizations",
]


async def _reset_tables(session: AsyncSession) -> None:
    """Truncate all seeded tables in dependency order with CASCADE."""
    _step("Truncating tables …")
    table_list = ", ".join(ORDERED_TABLES)
    await session.execute(text(f"TRUNCATE TABLE {table_list} CASCADE"))
    await session.commit()
    _ok(f"Truncated: {', '.join(ORDERED_TABLES)}")


# ══════════════════════════════════════════════════════════════════════════
#  Seed functions
# ══════════════════════════════════════════════════════════════════════════


async def _seed_organization(session: AsyncSession) -> Organization:
    """Seed the demo organization, returning the (possibly existing) row."""
    result = await session.execute(select(Organization).where(Organization.slug == ORG_SLUG))
    existing = result.scalar_one_or_none()
    if existing:
        _skip(f"Organization '{existing.name}' already exists (slug={ORG_SLUG})")
        return existing

    org = Organization(
        id=ORG_ID,
        name="SkyBridge Flight Academy",
        slug=ORG_SLUG,
        logo_url=None,
        is_active=True,
        max_seats=25,
    )
    session.add(org)
    await session.flush()
    _ok(f"Organization: {BOLD}{org.name}{RESET}  (id={org.id})")
    return org


async def _seed_users(
    session: AsyncSession,
    org: Organization,
) -> dict[str, User]:
    """Seed demo users and their seats. Returns a mapping of email → User.

    The platform-admin user is created without an organization seat.
    All other users get a seat in the provided organization.

    Keycloak IDs use the format ``kc-{deterministic_uuid}`` so they can be
    updated later when the real Keycloak ``sub`` claim is known (after first
    login).  For local development the backend ``auth_enabled=False`` mode
    returns a dev user and these IDs are never checked.
    """
    users: dict[str, User] = {}

    for u_data in USERS_DATA:
        email = u_data["email"]
        uid = _user_uuid(email)

        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            _skip(f"User '{existing.display_name}' already exists ({email})")
            users[email] = existing
            continue

        user = User(
            id=uid,
            keycloak_id=f"kc-{uid}",
            email=email,
            display_name=u_data["display_name"],
            avatar_url=None,
            is_active=True,
        )
        session.add(user)
        await session.flush()

        role = u_data["role"]

        # Platform-admin is not tied to any organization
        if role != "platform-admin":
            seat_role = role  # admin | instructor | student
            seat = Seat(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, f"seat-{email}"),
                user_id=user.id,
                organization_id=org.id,
                role=seat_role,
                is_active=True,
            )
            session.add(seat)
            await session.flush()

        role_badge = {
            "platform-admin": f"{MAGENTA}platform-admin{RESET}",
            "admin": f"{RED}admin{RESET}",
            "instructor": f"{YELLOW}instructor{RESET}",
            "student": f"{GREEN}student{RESET}",
        }.get(role, role)

        org_info = "" if role == "platform-admin" else f"  org={ORG_SLUG}"
        _ok(f"User: {BOLD}{user.display_name}{RESET}  [{role_badge}]  ({email}){org_info}")
        users[email] = user

    return users


async def _seed_scenarios(
    session: AsyncSession,
    org: Organization,
    instructor: User,
) -> list[Scenario]:
    """Seed training scenarios. Returns the list of created/existing rows."""
    scenarios: list[Scenario] = []

    for s_data in SCENARIOS_DATA:
        name = str(s_data["name"])
        result = await session.execute(
            select(Scenario).where(
                Scenario.name == name,
                Scenario.org_id == org.id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            _skip(f"Scenario '{existing.name}' already exists")
            scenarios.append(existing)
            continue

        scenario = Scenario(
            name=name,
            description=str(s_data["description"]),
            difficulty=int(s_data["difficulty"]),
            airport_icao=str(s_data["airport_icao"]),
            runway=str(s_data["runway"]),
            weather_preset=str(s_data["weather_preset"]),
            phase=str(s_data["phase"]),
            scenario_type=str(s_data.get("scenario_type", "")),
            org_id=org.id,
            created_by=instructor.id,
        )
        session.add(scenario)
        await session.flush()

        diff_colour = {1: GREEN, 2: YELLOW, 3: MAGENTA, 4: RED}.get(scenario.difficulty, RESET)
        _ok(
            f"Scenario: {BOLD}{scenario.name}{RESET}  "
            f"[{scenario.airport_icao} / {scenario.runway}]  "
            f"difficulty={diff_colour}{scenario.difficulty}{RESET}"
        )
        scenarios.append(scenario)

    return scenarios


async def _seed_sessions_and_logs(
    session: AsyncSession,
    scenarios: list[Scenario],
    users: dict[str, User],
    org: Organization,
) -> tuple[int, int]:
    """Seed training sessions and voice logs. Returns (session_count, log_count)."""

    maria = users["maria.santos@skybridge.aero"]
    alex = users["alex.turner@skybridge.aero"]

    # Map scenarios by ICAO for easy lookup
    scenario_by_icao: dict[str, Scenario] = {s.airport_icao: s for s in scenarios}

    now = datetime.now(tz=timezone.utc)
    session_count = 0
    log_count = 0

    session_defs: list[
        tuple[
            User,
            str,
            str,
            str,
            datetime | None,
            list[dict[str, str | int]],
        ]
    ] = [
        # (user, icao, status, language, ended_at, voice_logs)
        (
            maria,
            "KJFK",
            "completed",
            "en",
            now - timedelta(hours=2),
            VOICE_LOGS_SESSION_1,
        ),
        (
            alex,
            "KLAX",
            "active",
            "en",
            None,
            VOICE_LOGS_SESSION_2,
        ),
        (
            maria,
            "EGLL",
            "completed",
            "en",
            now - timedelta(minutes=45),
            VOICE_LOGS_SESSION_3,
        ),
    ]

    for user, icao, status, lang, ended_at, logs_data in session_defs:
        scenario = scenario_by_icao.get(icao)
        if scenario is None:
            _warn(f"Scenario for {icao} not found — skipping session")
            continue

        # Check if a session already exists for this user + scenario + status
        result = await session.execute(
            select(TrainingSession).where(
                TrainingSession.user_id == user.id,
                TrainingSession.scenario_id == scenario.id,
                TrainingSession.status == status,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            _skip(f"Session for {user.display_name} on {scenario.name} ({status}) already exists")
            continue

        ts = TrainingSession(
            scenario_id=scenario.id,
            language=lang,
            status=status,
            user_id=user.id,
            org_id=org.id,
            ended_at=ended_at,
        )
        session.add(ts)
        await session.flush()
        session_count += 1

        status_badge = (
            f"{GREEN}{status}{RESET}" if status == "completed" else f"{YELLOW}{status}{RESET}"
        )
        _ok(f"Session: {BOLD}{user.display_name}{RESET} → {scenario.name}  [{status_badge}]")

        # Seed voice logs for this session
        for vl_data in logs_data:
            vl = VoiceLog(
                session_id=ts.id,
                role=str(vl_data["role"]),
                transcript=str(vl_data["transcript"]),
                audio_duration_ms=int(vl_data["audio_duration_ms"]),
            )
            session.add(vl)
            log_count += 1

        await session.flush()
        role_label = lambda r: (  # noqa: E731
            f"{CYAN}ATC{RESET}" if r == "atc" else f"{MAGENTA}PLT{RESET}"
        )
        for vl_data in logs_data:
            role_tag = role_label(vl_data["role"])
            transcript_preview = str(vl_data["transcript"])[:72]
            if len(str(vl_data["transcript"])) > 72:
                transcript_preview += "…"
            print(
                f"      {role_tag}  {DIM}{transcript_preview}{RESET}  "
                f"({vl_data['audio_duration_ms']}ms)"
            )

    return session_count, log_count


# ══════════════════════════════════════════════════════════════════════════
#  Content Categories & Articles
# ══════════════════════════════════════════════════════════════════════════

CONTENT_CATEGORIES: list[dict[str, str | int]] = [
    {
        "name": "Aviation Theory",
        "slug": "aviation-theory",
        "description": "Fundamental principles of flight and aviation.",
        "icon": "BookOpen",
        "sort_order": 0,
    },
    {
        "name": "Aircraft Systems",
        "slug": "aircraft-systems",
        "description": "Engine, electrical, hydraulic, and avionics systems.",
        "icon": "Settings",
        "sort_order": 1,
    },
    {
        "name": "Aerodynamics",
        "slug": "aerodynamics",
        "description": "Lift, drag, thrust, and the physics of flight.",
        "icon": "Wind",
        "sort_order": 2,
    },
    {
        "name": "ATC Procedures",
        "slug": "atc-procedures",
        "description": "Air traffic control communication and procedures.",
        "icon": "Radio",
        "sort_order": 3,
    },
    {
        "name": "Regulations & Safety",
        "slug": "regulations-safety",
        "description": "FAR/AIM, ICAO standards, and safety management.",
        "icon": "Shield",
        "sort_order": 4,
    },
    {
        "name": "Weather & Meteorology",
        "slug": "weather-meteorology",
        "description": "Aviation weather, METARs, TAFs, and hazards.",
        "icon": "Cloud",
        "sort_order": 5,
    },
]

CONTENT_ARTICLES: list[dict[str, str | int | list[str] | bool]] = [
    # Aviation Theory
    {
        "category_slug": "aviation-theory",
        "title": "The Four Forces of Flight",
        "slug": "four-forces-of-flight",
        "summary": "Understanding lift, weight, thrust, and drag.",
        "content": (
            "# The Four Forces of Flight\n\n"
            "Every aircraft in flight is acted upon by four fundamental forces:\n\n"
            "1. **Lift** — generated by the wings, acts perpendicular to the "
            "relative wind\n"
            "2. **Weight** — the force of gravity pulling the aircraft downward\n"
            "3. **Thrust** — produced by the engine(s), propels the aircraft "
            "forward\n"
            "4. **Drag** — aerodynamic resistance opposing forward motion\n\n"
            "In unaccelerated, level flight these four forces are in equilibrium."
        ),
        "difficulty_level": 1,
        "tags": ["theory", "fundamentals", "forces"],
        "is_published": True,
    },
    {
        "category_slug": "aviation-theory",
        "title": "Principles of Controlled Flight",
        "slug": "principles-controlled-flight",
        "summary": "How control surfaces manage pitch, roll, and yaw.",
        "content": (
            "# Principles of Controlled Flight\n\n"
            "Aircraft are controlled around three axes:\n\n"
            "- **Lateral axis** — pitch (elevator)\n"
            "- **Longitudinal axis** — roll (ailerons)\n"
            "- **Vertical axis** — yaw (rudder)\n\n"
            "The pilot uses the flight controls to deflect control surfaces, "
            "changing the aerodynamic forces and moments."
        ),
        "difficulty_level": 1,
        "tags": ["theory", "control-surfaces", "axes"],
        "is_published": True,
    },
    # Aircraft Systems
    {
        "category_slug": "aircraft-systems",
        "title": "Piston Engine Fundamentals",
        "slug": "piston-engine-fundamentals",
        "summary": "How reciprocating engines power light aircraft.",
        "content": (
            "# Piston Engine Fundamentals\n\n"
            "Most light aircraft use horizontally-opposed, air-cooled piston "
            "engines. Key components include:\n\n"
            "- **Cylinders** — where combustion occurs\n"
            "- **Crankshaft** — converts linear motion to rotational\n"
            "- **Magnetos** — provide ignition independent of electrical system\n"
            "- **Carburetor/Fuel Injection** — meters fuel/air mixture\n\n"
            "The four-stroke cycle: intake, compression, power, exhaust."
        ),
        "difficulty_level": 2,
        "tags": ["systems", "engine", "piston"],
        "is_published": True,
    },
    {
        "category_slug": "aircraft-systems",
        "title": "Electrical System Overview",
        "slug": "electrical-system-overview",
        "summary": "Battery, alternator, bus, and circuit protection.",
        "content": (
            "# Electrical System Overview\n\n"
            "A typical light aircraft electrical system includes:\n\n"
            "- **Battery** — 12V or 24V, provides power for engine start\n"
            "- **Alternator** — driven by the engine, charges the battery\n"
            "- **Bus bar** — distributes power to avionics and instruments\n"
            "- **Circuit breakers** — protect against overloads\n\n"
            "Always monitor ammeter and voltmeter for system health."
        ),
        "difficulty_level": 2,
        "tags": ["systems", "electrical", "avionics"],
        "is_published": True,
    },
    # Aerodynamics
    {
        "category_slug": "aerodynamics",
        "title": "Angle of Attack and Stalls",
        "slug": "angle-of-attack-stalls",
        "summary": "Understanding critical angle of attack and stall behaviour.",
        "content": (
            "# Angle of Attack and Stalls\n\n"
            "The **angle of attack (AoA)** is the angle between the chord line "
            "and the relative wind.\n\n"
            "A stall occurs when the AoA exceeds the **critical angle** "
            "(typically 15-18°), causing airflow separation over the wing.\n\n"
            "Key points:\n"
            "- A stall can occur at **any airspeed and any attitude**\n"
            "- Recovery: reduce AoA, add power, level wings\n"
            "- Stall warning systems provide advance notice"
        ),
        "difficulty_level": 2,
        "tags": ["aerodynamics", "stall", "angle-of-attack"],
        "is_published": True,
    },
    {
        "category_slug": "aerodynamics",
        "title": "Lift Generation: Bernoulli and Newton",
        "slug": "lift-generation-bernoulli-newton",
        "summary": "Two complementary explanations for how wings produce lift.",
        "content": (
            "# Lift Generation\n\n"
            "Lift is explained by two complementary principles:\n\n"
            "## Bernoulli's Principle\n"
            "Air accelerating over the curved upper surface creates lower "
            "pressure above the wing.\n\n"
            "## Newton's Third Law\n"
            "The wing deflects air downward; the equal and opposite reaction "
            "pushes the wing upward.\n\n"
            "Both effects contribute to total lift generation."
        ),
        "difficulty_level": 1,
        "tags": ["aerodynamics", "lift", "bernoulli"],
        "is_published": True,
    },
    # ATC Procedures
    {
        "category_slug": "atc-procedures",
        "title": "Radio Communication Basics",
        "slug": "radio-communication-basics",
        "summary": "Standard phraseology and communication flow.",
        "content": (
            "# Radio Communication Basics\n\n"
            "Standard radio communication follows the pattern:\n\n"
            "1. **Who you're calling** — facility name\n"
            "2. **Who you are** — callsign\n"
            "3. **Where you are** — position/altitude\n"
            "4. **What you want** — request\n\n"
            "Example: *\"Kennedy Ground, SkyBridge 427, at gate B7, "
            "information Tango, request taxi to runway 31L.\"*\n\n"
            "Always read back hold-short instructions and runway assignments."
        ),
        "difficulty_level": 1,
        "tags": ["atc", "communication", "phraseology"],
        "is_published": True,
    },
    {
        "category_slug": "atc-procedures",
        "title": "IFR Clearance Delivery",
        "slug": "ifr-clearance-delivery",
        "summary": "Obtaining and reading back IFR clearances using CRAFT.",
        "content": (
            "# IFR Clearance Delivery\n\n"
            "Use the **CRAFT** acronym to copy IFR clearances:\n\n"
            "- **C**learance limit (usually destination)\n"
            "- **R**oute\n"
            "- **A**ltitude (initial and expected)\n"
            "- **F**requency (departure frequency)\n"
            "- **T**ransponder code (squawk)\n\n"
            "Always read back the full clearance and verify the squawk code."
        ),
        "difficulty_level": 3,
        "tags": ["atc", "IFR", "clearance", "CRAFT"],
        "is_published": True,
    },
    # Regulations & Safety
    {
        "category_slug": "regulations-safety",
        "title": "VFR Weather Minimums",
        "slug": "vfr-weather-minimums",
        "summary": "Visibility and cloud clearance requirements for VFR flight.",
        "content": (
            "# VFR Weather Minimums\n\n"
            "VFR weather minimums vary by airspace (FAR 91.155):\n\n"
            "| Airspace | Visibility | Cloud Clearance |\n"
            "|----------|-----------|----------------|\n"
            "| Class B | 3 SM | Clear of clouds |\n"
            "| Class C/D | 3 SM | 500'/1000'/2000' |\n"
            "| Class E (day) | 3 SM | 500'/1000'/2000' |\n"
            "| Class G (day, <1200 AGL) | 1 SM | Clear of clouds |\n\n"
            "When conditions are below VFR minimums, IFR is required."
        ),
        "difficulty_level": 2,
        "tags": ["regulations", "VFR", "weather", "FAR"],
        "is_published": True,
    },
    {
        "category_slug": "regulations-safety",
        "title": "Pilot Currency Requirements",
        "slug": "pilot-currency-requirements",
        "summary": "Staying current: recent experience and medical requirements.",
        "content": (
            "# Pilot Currency Requirements\n\n"
            "To carry passengers (FAR 61.57):\n\n"
            "- **3 takeoffs and landings** in preceding 90 days\n"
            "- For night: 3 full-stop landings at night\n"
            "- **Flight review** every 24 calendar months\n"
            "- Valid **medical certificate**\n\n"
            "Currency ≠ proficiency. Regular practice is essential."
        ),
        "difficulty_level": 2,
        "tags": ["regulations", "currency", "FAR", "safety"],
        "is_published": True,
    },
    # Weather & Meteorology
    {
        "category_slug": "weather-meteorology",
        "title": "Reading METARs",
        "slug": "reading-metars",
        "summary": "How to decode routine aviation weather observations.",
        "content": (
            "# Reading METARs\n\n"
            "A METAR follows a standard format:\n\n"
            "```\nMETAR KJFK 231456Z 31012G18KT 10SM "
            "FEW040 SCT120 24/18 A3012\n```\n\n"
            "- **KJFK** — station identifier\n"
            "- **231456Z** — day/time (Zulu)\n"
            "- **31012G18KT** — wind 310° at 12 kt, gusting 18\n"
            "- **10SM** — visibility 10 statute miles\n"
            "- **FEW040 SCT120** — clouds at 4000 and 12000 ft\n"
            "- **24/18** — temperature/dewpoint\n"
            "- **A3012** — altimeter setting 30.12 inHg"
        ),
        "difficulty_level": 2,
        "tags": ["weather", "METAR", "observations"],
        "is_published": True,
    },
    {
        "category_slug": "weather-meteorology",
        "title": "Thunderstorm Hazards for Pilots",
        "slug": "thunderstorm-hazards",
        "summary": "Understanding and avoiding convective weather.",
        "content": (
            "# Thunderstorm Hazards\n\n"
            "Thunderstorms present multiple hazards:\n\n"
            "- **Turbulence** — severe up/downdrafts\n"
            "- **Icing** — supercooled water at altitude\n"
            "- **Hail** — can cause structural damage\n"
            "- **Lightning** — can damage electronics\n"
            "- **Wind shear** — rapid changes near the surface\n"
            "- **Microbursts** — intense localized downdrafts\n\n"
            "**Rule of thumb**: Stay at least 20 NM from any thunderstorm."
        ),
        "difficulty_level": 3,
        "tags": ["weather", "thunderstorm", "hazards", "convective"],
        "is_published": True,
    },
]


# ══════════════════════════════════════════════════════════════════════════
#  Waypoints
# ══════════════════════════════════════════════════════════════════════════

WAYPOINTS_DATA: list[dict] = [
    # Major US airports
    {"name": "John F. Kennedy Intl", "identifier": "KJFK", "type": "airport",
     "lat": 40.6413, "lng": -73.7781, "elevation_ft": 13},
    {"name": "Los Angeles Intl", "identifier": "KLAX", "type": "airport",
     "lat": 33.9425, "lng": -118.4081, "elevation_ft": 128},
    {"name": "Chicago O'Hare Intl", "identifier": "KORD", "type": "airport",
     "lat": 41.9742, "lng": -87.9073, "elevation_ft": 672},
    {"name": "Hartsfield-Jackson Atlanta", "identifier": "KATL", "type": "airport",
     "lat": 33.6407, "lng": -84.4277, "elevation_ft": 1026},
    {"name": "San Francisco Intl", "identifier": "KSFO", "type": "airport",
     "lat": 37.6213, "lng": -122.3790, "elevation_ft": 13},
    {"name": "Dallas/Fort Worth Intl", "identifier": "KDFW", "type": "airport",
     "lat": 32.8998, "lng": -97.0403, "elevation_ft": 607},
    {"name": "Denver Intl", "identifier": "KDEN", "type": "airport",
     "lat": 39.8561, "lng": -104.6737, "elevation_ft": 5431},
    {"name": "Miami Intl", "identifier": "KMIA", "type": "airport",
     "lat": 25.7959, "lng": -80.2870, "elevation_ft": 8},
    # VORs
    {"name": "Kennedy VOR", "identifier": "JFK", "type": "VOR",
     "lat": 40.6340, "lng": -73.7670, "frequency": 115.9},
    {"name": "Los Angeles VOR", "identifier": "LAX", "type": "VOR",
     "lat": 33.9330, "lng": -118.4320, "frequency": 113.6},
    {"name": "O'Hare VOR", "identifier": "ORD", "type": "VOR",
     "lat": 41.9800, "lng": -87.9050, "frequency": 113.9},
    {"name": "Atlanta VOR", "identifier": "ATL", "type": "VOR",
     "lat": 33.6290, "lng": -84.4350, "frequency": 116.9},
    {"name": "Denver VOR", "identifier": "DEN", "type": "VOR",
     "lat": 39.8490, "lng": -104.6580, "frequency": 117.9},
    # Fixes / intersections
    {"name": "CAMRN", "identifier": "CAMRN", "type": "fix",
     "lat": 40.5500, "lng": -73.9000},
    {"name": "ROBER", "identifier": "ROBER", "type": "fix",
     "lat": 40.9800, "lng": -74.1500},
    {"name": "BETTE", "identifier": "BETTE", "type": "fix",
     "lat": 41.2000, "lng": -74.5000},
    {"name": "MERIT", "identifier": "MERIT", "type": "fix",
     "lat": 41.5500, "lng": -75.2000},
    {"name": "DIRECT", "identifier": "DRECT", "type": "fix",
     "lat": 41.8000, "lng": -76.0000},
    {"name": "PLANO", "identifier": "PLANO", "type": "fix",
     "lat": 42.0000, "lng": -80.0000},
    {"name": "BRIGS", "identifier": "BRIGS", "type": "fix",
     "lat": 42.0200, "lng": -85.0000},
]


# ══════════════════════════════════════════════════════════════════════════
#  Badges
# ══════════════════════════════════════════════════════════════════════════

BADGES_DATA: list[dict[str, str | int | bool | dict]] = [
    # Flight badges
    {"name": "First Flight", "slug": "first-flight",
     "description": "Complete your first training session.",
     "category": "flight", "tier": "bronze", "sort_order": 0,
     "criteria": {"type": "sessions_completed", "count": 1}},
    {"name": "Sky Explorer", "slug": "sky-explorer",
     "description": "Complete 10 training sessions.",
     "category": "flight", "tier": "silver", "sort_order": 1,
     "criteria": {"type": "sessions_completed", "count": 10}},
    {"name": "Air Captain", "slug": "air-captain",
     "description": "Complete 50 training sessions.",
     "category": "flight", "tier": "gold", "sort_order": 2,
     "criteria": {"type": "sessions_completed", "count": 50}},
    {"name": "Flight Master", "slug": "flight-master",
     "description": "Complete 200 training sessions.",
     "category": "flight", "tier": "platinum", "sort_order": 3,
     "criteria": {"type": "sessions_completed", "count": 200}},
    # Communication badges
    {"name": "First Contact", "slug": "first-contact",
     "description": "Complete your first ATC radio exchange.",
     "category": "communication", "tier": "bronze", "sort_order": 10,
     "criteria": {"type": "voice_logs", "count": 1}},
    {"name": "Radio Pro", "slug": "radio-pro",
     "description": "Achieve 95%+ communication score in 5 sessions.",
     "category": "communication", "tier": "silver", "sort_order": 11,
     "criteria": {"type": "comm_score", "min_score": 95, "sessions": 5}},
    {"name": "Tower Whisperer", "slug": "tower-whisperer",
     "description": "Complete 100 ATC exchanges with no errors.",
     "category": "communication", "tier": "gold", "sort_order": 12,
     "criteria": {"type": "perfect_exchanges", "count": 100}},
    # Knowledge badges
    {"name": "Bookworm", "slug": "bookworm",
     "description": "Read 10 knowledge base articles.",
     "category": "knowledge", "tier": "bronze", "sort_order": 20,
     "criteria": {"type": "articles_read", "count": 10}},
    {"name": "Quiz Ace", "slug": "quiz-ace",
     "description": "Pass 5 knowledge assessments with 90%+.",
     "category": "knowledge", "tier": "silver", "sort_order": 21,
     "criteria": {"type": "assessments_passed", "count": 5, "min_score": 90}},
    {"name": "Scholar", "slug": "scholar",
     "description": "Pass every available assessment.",
     "category": "knowledge", "tier": "gold", "sort_order": 22,
     "criteria": {"type": "all_assessments_passed"}},
    # Streak badges
    {"name": "Week Warrior", "slug": "week-warrior",
     "description": "Train 7 days in a row.",
     "category": "streak", "tier": "bronze", "sort_order": 30,
     "criteria": {"type": "streak_days", "count": 7}},
    {"name": "Month of Dedication", "slug": "month-dedication",
     "description": "Train 30 days in a row.",
     "category": "streak", "tier": "silver", "sort_order": 31,
     "criteria": {"type": "streak_days", "count": 30}},
    # Achievement badges
    {"name": "Emergency Handler", "slug": "emergency-handler",
     "description": "Successfully complete an emergency scenario.",
     "category": "achievement", "tier": "silver", "sort_order": 40,
     "criteria": {"type": "scenario_type", "value": "emergency"}},
    {"name": "Night Owl", "slug": "night-owl",
     "description": "Complete a night flight scenario.",
     "category": "achievement", "tier": "bronze", "sort_order": 41,
     "criteria": {"type": "scenario_type", "value": "night"}},
    {"name": "Multi-Airport", "slug": "multi-airport",
     "description": "Train at 5 different airports.",
     "category": "achievement", "tier": "silver", "sort_order": 42,
     "criteria": {"type": "unique_airports", "count": 5}},
]


# ══════════════════════════════════════════════════════════════════════════
#  Sample Assessment
# ══════════════════════════════════════════════════════════════════════════

SAMPLE_ASSESSMENT = {
    "title": "ATC Communication Fundamentals",
    "description": (
        "Test your knowledge of standard ATC phraseology, "
        "radio procedures, and communication best practices."
    ),
    "passing_score": 70.0,
    "time_limit_minutes": 15,
    "is_published": True,
    "questions": [
        {
            "id": "q1",
            "prompt": (
                "What is the correct order for an initial radio call?"
            ),
            "choices": [
                "A) Your callsign, facility name, request",
                "B) Facility name, your callsign, position, request",
                "C) Facility name, request, your callsign",
                "D) Position, your callsign, facility name",
            ],
            "correct": "B",
        },
        {
            "id": "q2",
            "prompt": "What does 'Roger' mean in aviation radio?",
            "choices": [
                "A) I agree with your instruction",
                "B) I have received your message",
                "C) I will comply",
                "D) Say again",
            ],
            "correct": "B",
        },
        {
            "id": "q3",
            "prompt": (
                "Which readback is ALWAYS required?"
            ),
            "choices": [
                "A) Weather information",
                "B) Traffic advisories",
                "C) Hold-short instructions",
                "D) Altimeter settings",
            ],
            "correct": "C",
        },
        {
            "id": "q4",
            "prompt": (
                "What does 'Wilco' mean?"
            ),
            "choices": [
                "A) Will comply",
                "B) I understand",
                "C) Roger that",
                "D) Standby",
            ],
            "correct": "A",
        },
        {
            "id": "q5",
            "prompt": (
                "You hear 'SkyBridge 427, say altitude'. "
                "What should you respond?"
            ),
            "choices": [
                "A) SkyBridge 427, level flight level two-four-zero",
                "B) Say again",
                "C) Roger",
                "D) SkyBridge 427, affirm",
            ],
            "correct": "A",
        },
    ],
}


# ══════════════════════════════════════════════════════════════════════════
#  Sample Flight Plan
# ══════════════════════════════════════════════════════════════════════════

SAMPLE_FLIGHT_PLAN = {
    "title": "KJFK → KORD Training Route",
    "departure_icao": "KJFK",
    "arrival_icao": "KORD",
    "alternate_icao": "KMDW",
    "route_string": "KJFK JFK V16 MERIT J584 PLANO BRIGS KORD",
    "aircraft_type": "C172",
    "fuel_required_gal": 42.0,
    "fuel_reserve_gal": 8.5,
    "total_weight_lbs": 2200.0,
    "max_weight_lbs": 2550.0,
    "cg_position": 47.2,
    "weather_briefing": {
        "synopsis": "High pressure over the Northeast, clear skies.",
        "winds_aloft": "FL180: 270/35, FL240: 280/45",
    },
    "airspace_restrictions": [
        {"type": "TFR", "area": "DC SFRA", "status": "avoid"},
    ],
    "source_type": "form",
    "status": "draft",
    "legs": [
        {
            "sequence": 0,
            "from_identifier": "KJFK",
            "to_identifier": "MERIT",
            "distance_nm": 95.0,
            "magnetic_heading": 290.0,
            "altitude": "FL180",
            "estimated_time_minutes": 38.0,
            "fuel_burn_gal": 12.0,
            "wind": {"direction": 270, "speed": 25},
        },
        {
            "sequence": 1,
            "from_identifier": "MERIT",
            "to_identifier": "PLANO",
            "distance_nm": 280.0,
            "magnetic_heading": 275.0,
            "altitude": "FL240",
            "estimated_time_minutes": 95.0,
            "fuel_burn_gal": 22.0,
            "wind": {"direction": 280, "speed": 45},
        },
        {
            "sequence": 2,
            "from_identifier": "PLANO",
            "to_identifier": "KORD",
            "distance_nm": 120.0,
            "magnetic_heading": 265.0,
            "altitude": "10000",
            "estimated_time_minutes": 42.0,
            "fuel_burn_gal": 8.0,
            "wind": {"direction": 260, "speed": 15},
        },
    ],
}


# ══════════════════════════════════════════════════════════════════════════
#  New seed functions
# ══════════════════════════════════════════════════════════════════════════


async def _seed_content(session: AsyncSession) -> tuple[int, int]:
    """Seed content categories and articles. Returns (cat_count, art_count)."""
    cat_count = 0
    art_count = 0
    cat_map: dict[str, ContentCategory] = {}

    for c_data in CONTENT_CATEGORIES:
        slug = str(c_data["slug"])
        result = await session.execute(
            select(ContentCategory).where(ContentCategory.slug == slug)
        )
        existing = result.scalar_one_or_none()
        if existing:
            _skip(f"Category '{existing.name}' already exists")
            cat_map[slug] = existing
            continue

        cat = ContentCategory(
            name=str(c_data["name"]),
            slug=slug,
            description=str(c_data.get("description", "")),
            icon=str(c_data.get("icon", "")),
            sort_order=int(c_data.get("sort_order", 0)),
            is_active=True,
        )
        session.add(cat)
        await session.flush()
        cat_map[slug] = cat
        cat_count += 1
        _ok(f"Category: {BOLD}{cat.name}{RESET}")

    for a_data in CONTENT_ARTICLES:
        slug = str(a_data["slug"])
        result = await session.execute(
            select(ContentArticle).where(ContentArticle.slug == slug)
        )
        existing = result.scalar_one_or_none()
        if existing:
            _skip(f"Article '{existing.title}' already exists")
            continue

        cat_slug = str(a_data["category_slug"])
        cat = cat_map.get(cat_slug)
        if not cat:
            _warn(f"Category '{cat_slug}' not found — skipping article")
            continue

        article = ContentArticle(
            category_id=cat.id,
            title=str(a_data["title"]),
            slug=slug,
            content=str(a_data["content"]),
            summary=str(a_data.get("summary", "")),
            difficulty_level=int(a_data.get("difficulty_level", 1)),
            tags=list(a_data.get("tags", [])),
            is_published=bool(a_data.get("is_published", False)),
        )
        session.add(article)
        art_count += 1

    await session.flush()
    if art_count:
        _ok(f"Articles: {BOLD}{art_count}{RESET} created")
    return cat_count, art_count


async def _seed_waypoints(session: AsyncSession) -> dict[str, Waypoint]:
    """Seed navigation waypoints. Returns identifier → Waypoint map."""
    wp_map: dict[str, Waypoint] = {}
    count = 0

    for w_data in WAYPOINTS_DATA:
        identifier = w_data.get("identifier", "")
        result = await session.execute(
            select(Waypoint).where(Waypoint.identifier == identifier)
        )
        existing = result.scalar_one_or_none()
        if existing:
            wp_map[identifier] = existing
            continue

        wp = Waypoint(
            name=w_data["name"],
            identifier=identifier,
            type=w_data["type"],
            lat=w_data["lat"],
            lng=w_data["lng"],
            frequency=w_data.get("frequency"),
            elevation_ft=w_data.get("elevation_ft"),
        )
        session.add(wp)
        count += 1
        wp_map[identifier] = wp

    await session.flush()
    if count:
        _ok(f"Waypoints: {BOLD}{count}{RESET} created")
    return wp_map


async def _seed_badges(session: AsyncSession) -> int:
    """Seed gamification badges. Returns count of new badges."""
    count = 0

    for b_data in BADGES_DATA:
        slug = str(b_data["slug"])
        result = await session.execute(
            select(Badge).where(Badge.slug == slug)
        )
        if result.scalar_one_or_none():
            _skip(f"Badge '{b_data['name']}' already exists")
            continue

        badge = Badge(
            name=str(b_data["name"]),
            slug=slug,
            description=str(b_data["description"]),
            category=str(b_data["category"]),
            tier=str(b_data["tier"]),
            sort_order=int(b_data.get("sort_order", 0)),
            criteria=dict(b_data.get("criteria", {})),
            is_active=True,
        )
        session.add(badge)
        count += 1

    await session.flush()
    if count:
        tier_label = lambda t: {  # noqa: E731
            "bronze": f"{DIM}bronze{RESET}",
            "silver": f"{CYAN}silver{RESET}",
            "gold": f"{YELLOW}gold{RESET}",
            "platinum": f"{MAGENTA}platinum{RESET}",
        }.get(t, t)
        _ok(f"Badges: {BOLD}{count}{RESET} created")
    return count


async def _seed_assessment(
    session: AsyncSession,
    org: Organization,
    instructor: User,
) -> int:
    """Seed a sample knowledge assessment. Returns 1 if created, 0 if skipped."""
    title = SAMPLE_ASSESSMENT["title"]
    result = await session.execute(
        select(KnowledgeAssessment).where(
            KnowledgeAssessment.title == title,
        )
    )
    if result.scalar_one_or_none():
        _skip(f"Assessment '{title}' already exists")
        return 0

    assessment = KnowledgeAssessment(
        title=str(title),
        description=str(SAMPLE_ASSESSMENT["description"]),
        questions=list(SAMPLE_ASSESSMENT["questions"]),
        passing_score=float(SAMPLE_ASSESSMENT["passing_score"]),
        time_limit_minutes=int(SAMPLE_ASSESSMENT["time_limit_minutes"]),
        is_published=bool(SAMPLE_ASSESSMENT["is_published"]),
        org_id=org.id,
        created_by=instructor.id,
    )
    session.add(assessment)
    await session.flush()
    _ok(
        f"Assessment: {BOLD}{assessment.title}{RESET}  "
        f"({len(SAMPLE_ASSESSMENT['questions'])} questions)"
    )
    return 1


async def _seed_flight_plan(
    session: AsyncSession,
    user: User,
    org: Organization,
) -> int:
    """Seed a sample flight plan with legs. Returns 1 if created."""
    title = SAMPLE_FLIGHT_PLAN["title"]
    result = await session.execute(
        select(FlightPlan).where(
            FlightPlan.title == title,
            FlightPlan.user_id == user.id,
        )
    )
    if result.scalar_one_or_none():
        _skip(f"Flight plan '{title}' already exists")
        return 0

    plan = FlightPlan(
        user_id=user.id,
        org_id=org.id,
        title=str(title),
        departure_icao=str(SAMPLE_FLIGHT_PLAN["departure_icao"]),
        arrival_icao=str(SAMPLE_FLIGHT_PLAN["arrival_icao"]),
        alternate_icao=str(SAMPLE_FLIGHT_PLAN.get("alternate_icao", "")),
        route_string=str(SAMPLE_FLIGHT_PLAN.get("route_string", "")),
        aircraft_type=str(SAMPLE_FLIGHT_PLAN.get("aircraft_type", "")),
        fuel_required_gal=float(SAMPLE_FLIGHT_PLAN["fuel_required_gal"]),
        fuel_reserve_gal=float(SAMPLE_FLIGHT_PLAN["fuel_reserve_gal"]),
        total_weight_lbs=float(SAMPLE_FLIGHT_PLAN["total_weight_lbs"]),
        max_weight_lbs=float(SAMPLE_FLIGHT_PLAN["max_weight_lbs"]),
        cg_position=float(SAMPLE_FLIGHT_PLAN["cg_position"]),
        weather_briefing=dict(SAMPLE_FLIGHT_PLAN["weather_briefing"]),
        airspace_restrictions=list(
            SAMPLE_FLIGHT_PLAN["airspace_restrictions"]
        ),
        source_type=str(SAMPLE_FLIGHT_PLAN["source_type"]),
        status=str(SAMPLE_FLIGHT_PLAN["status"]),
    )
    session.add(plan)
    await session.flush()

    for leg_data in SAMPLE_FLIGHT_PLAN["legs"]:
        leg = FlightPlanLeg(
            flight_plan_id=plan.id,
            sequence=int(leg_data["sequence"]),
            from_identifier=str(leg_data.get("from_identifier", "")),
            to_identifier=str(leg_data.get("to_identifier", "")),
            distance_nm=float(leg_data.get("distance_nm", 0)),
            magnetic_heading=float(leg_data.get("magnetic_heading", 0)),
            altitude=str(leg_data.get("altitude", "")),
            estimated_time_minutes=float(
                leg_data.get("estimated_time_minutes", 0)
            ),
            fuel_burn_gal=float(leg_data.get("fuel_burn_gal", 0)),
            wind=leg_data.get("wind"),
        )
        session.add(leg)

    await session.flush()
    _ok(
        f"Flight Plan: {BOLD}{plan.title}{RESET}  "
        f"({len(SAMPLE_FLIGHT_PLAN['legs'])} legs)"
    )
    return 1


def _print_summary(counts: dict[str, int]) -> None:
    _header("Seed Summary")
    max_label = max(len(k) for k in counts)
    for label, count in counts.items():
        bar = f"{GREEN}{'█' * count}{RESET}" if count else f"{DIM}—{RESET}"
        print(f"  {label:<{max_label}}  {BOLD}{count:>3}{RESET}  {bar}")
    print()


# ══════════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════════


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the Horus database with demo aviation training data.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Truncate all seeded tables before inserting (destructive).",
    )
    args = parser.parse_args()

    settings = get_settings()
    _header("Horus ATC — Database Seed")
    _step(f"Environment: {BOLD}{settings.environment}{RESET}")
    _step(f"Database:    {DIM}{settings.database_url.split('@')[-1]}{RESET}")

    factory = get_session_factory()

    try:
        async with factory() as session:
            # Quick connectivity / migration check
            try:
                await session.execute(text("SELECT 1 FROM users LIMIT 0"))
            except (OperationalError, ProgrammingError) as exc:
                _fail("Cannot query the 'users' table.")
                _fail("It looks like database migrations have not been applied yet.")
                print()
                print(f"  {BOLD}Run migrations first:{RESET}")
                print("    cd backend && alembic upgrade head")
                print()
                print(f"  {DIM}Original error: {exc}{RESET}")
                sys.exit(1)

            # ── Reset if requested ────────────────────────────────────
            if args.reset:
                _warn("--reset flag detected: truncating all seeded tables")
                await _reset_tables(session)

            # ── Seed data ─────────────────────────────────────────────
            print(f"\n{BOLD}  Seeding organization …{RESET}")
            org = await _seed_organization(session)

            print(f"\n{BOLD}  Seeding users & seats …{RESET}")
            users = await _seed_users(session, org)

            instructor = users["james.chen@skybridge.aero"]

            print(f"\n{BOLD}  Seeding scenarios …{RESET}")
            scenarios = await _seed_scenarios(session, org, instructor)

            print(f"\n{BOLD}  Seeding training sessions & voice logs …{RESET}")
            ts_count, vl_count = await _seed_sessions_and_logs(
                session,
                scenarios,
                users,
                org,
            )

            print(f"\n{BOLD}  Seeding content categories & articles …{RESET}")
            cat_count, art_count = await _seed_content(session)

            print(f"\n{BOLD}  Seeding navigation waypoints …{RESET}")
            await _seed_waypoints(session)

            print(f"\n{BOLD}  Seeding badges …{RESET}")
            badge_count = await _seed_badges(session)

            print(f"\n{BOLD}  Seeding knowledge assessment …{RESET}")
            assess_count = await _seed_assessment(session, org, instructor)

            maria = users["maria.santos@skybridge.aero"]
            print(f"\n{BOLD}  Seeding flight plan …{RESET}")
            fp_count = await _seed_flight_plan(session, maria, org)

            await session.commit()

            # ── Summary ───────────────────────────────────────────────
            org_users = sum(1 for u in USERS_DATA if u["role"] != "platform-admin")
            _print_summary(
                {
                    "Organizations": 1,
                    "Users": len(USERS_DATA),
                    "Seats": org_users,
                    "Scenarios": len(SCENARIOS_DATA),
                    "Training Sessions": ts_count,
                    "Voice Logs": vl_count,
                    "Content Categories": cat_count,
                    "Content Articles": art_count,
                    "Waypoints": len(WAYPOINTS_DATA),
                    "Badges": badge_count,
                    "Assessments": assess_count,
                    "Flight Plans": fp_count,
                }
            )
            _ok(f"{GREEN}Seed complete!{RESET}\n")

    except (OSError, OperationalError) as exc:
        _fail(f"Database connection failed: {exc}")
        print()
        print(f"  {BOLD}Make sure PostgreSQL is running and .env is configured:{RESET}")
        print("    docker compose up -d postgres")
        print()
        sys.exit(1)
    finally:
        engine = get_engine()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
