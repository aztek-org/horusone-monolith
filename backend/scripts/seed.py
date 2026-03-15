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
from app.db.session import get_engine, get_session_factory  # noqa: E402
from app.models.organization import Organization  # noqa: E402
from app.models.scenario import Scenario  # noqa: E402
from app.models.seat import Seat  # noqa: E402
from app.models.training_session import TrainingSession  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.voice_log import VoiceLog  # noqa: E402

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
ORG_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "skybridge.aero")

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
    "user_preferences",
    "voice_logs",
    "training_sessions",
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
#  Summary
# ══════════════════════════════════════════════════════════════════════════


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
