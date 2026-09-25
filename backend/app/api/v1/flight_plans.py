"""Flight plan API routes.

- ``GET    /``                — list user's flight plans
- ``POST   /``                — create from form data
- ``POST   /from-text``       — create from plain text (AI-powered)
- ``POST   /from-image``      — create from uploaded image (OCR + AI)
- ``GET    /{id}``            — full flight plan with legs
- ``PUT    /{id}``            — update flight plan
- ``POST   /{id}/validate``   — trigger LangGraph validation pipeline
- ``POST   /{id}/activate``   — set status to active
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.repositories.flight_plan_repository import FlightPlanRepository
from app.db.session import get_db_session
from app.middleware.auth import CurrentUser
from app.middleware.org_context import RequireActiveSeat, get_authenticated_user, get_org_id
from app.models.user import User
from app.schemas.flight_plan import (
    FlightPlanCreate,
    FlightPlanFromText,
    FlightPlanRead,
    FlightPlanUpdate,
    ValidationResponse,
)
from app.services.flight_plan_parser import FlightPlanParser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/flight-plans", tags=["Flight Plans"])

plan_repo = FlightPlanRepository()


def _get_parser() -> FlightPlanParser:
    """Construct a ``FlightPlanParser`` from current settings."""
    settings = get_settings()
    return FlightPlanParser(
        ollama_base_url=settings.ollama_base_url,
        model=settings.ollama_llm_model,
    )


# ── List / Create ──────────────────────────────────────────────────


@router.get("/", response_model=list[FlightPlanRead])
async def list_flight_plans(
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
    plan_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> list[FlightPlanRead]:
    """List the current user's flight plans.

    Optionally filter by ``status`` (draft, validated, approved, active,
    completed).
    """
    plans = await plan_repo.list_flight_plans(
        db,
        user_id=local_user.id,
        org_id=org_id,
        status=plan_status,
        limit=limit,
        offset=offset,
    )
    return plans  # type: ignore[return-value]


@router.post(
    "/",
    response_model=FlightPlanRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_flight_plan(
    data: FlightPlanCreate,
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
    db: AsyncSession = Depends(get_db_session),
) -> FlightPlanRead:
    """Create a new flight plan from structured form data."""
    plan_data = data.model_dump()
    # Use explicit org_id from body, otherwise fall back to user's org
    effective_org = plan_data.pop("org_id", None) or org_id

    plan = await plan_repo.create_flight_plan(
        db, plan_data, user_id=local_user.id, org_id=effective_org
    )
    return plan  # type: ignore[return-value]


# ── AI-powered create stubs ────────────────────────────────────────


@router.post(
    "/from-text",
    response_model=FlightPlanRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_flight_plan_from_text(
    data: FlightPlanFromText,
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
    db: AsyncSession = Depends(get_db_session),
) -> FlightPlanRead:
    """Create a flight plan by parsing free-text input via AI.

    Uses the Ollama LLM to extract structured fields from the free-text
    description.  Falls back to keyword-based extraction when the LLM
    is unavailable.
    """
    effective_org = data.org_id or org_id
    parser = _get_parser()

    try:
        parsed = await parser.from_text(data.text)
    except Exception:
        logger.warning("Flight plan text parsing failed — creating stub plan", exc_info=True)
        parsed = {}

    plan_data: dict[str, Any] = {
        "title": data.title or _derive_title(parsed, "text"),
        "departure_icao": parsed.get("departure_icao") or "ZZZZ",
        "arrival_icao": parsed.get("arrival_icao") or "ZZZZ",
        "alternate_icao": parsed.get("alternate_icao"),
        "aircraft_type": parsed.get("aircraft_type"),
        "route_string": parsed.get("route_string"),
        "notes": f"[AUTO-PARSED TEXT]\n{data.text}",
        "source_type": "text",
        "status": "draft",
    }

    plan = await plan_repo.create_flight_plan(
        db, data=plan_data, user_id=local_user.id, org_id=effective_org
    )
    logger.info("Created flight plan %s from text input (AI-parsed)", plan.id)
    return plan  # type: ignore[return-value]


@router.post(
    "/from-image",
    response_model=FlightPlanRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_flight_plan_from_image(
    file: UploadFile,
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
    db: AsyncSession = Depends(get_db_session),
) -> FlightPlanRead:
    """Create a flight plan from an uploaded image (OCR + AI parsing).

    Pipeline: read image bytes → OCR text extraction → LLM parsing
    into structured fields.  Falls back gracefully at each stage.
    """
    filename = file.filename or "unknown"
    content_type = file.content_type or "unknown"
    parser = _get_parser()

    try:
        image_bytes = await file.read()
    except Exception:
        logger.exception("Failed to read uploaded image")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded image file",
        )

    try:
        parsed = await parser.from_image(image_bytes)
    except Exception:
        logger.warning("Flight plan image parsing failed — creating stub plan", exc_info=True)
        parsed = {}

    plan_data: dict[str, Any] = {
        "title": _derive_title(parsed, f"image: {filename}"),
        "departure_icao": parsed.get("departure_icao") or "ZZZZ",
        "arrival_icao": parsed.get("arrival_icao") or "ZZZZ",
        "alternate_icao": parsed.get("alternate_icao"),
        "aircraft_type": parsed.get("aircraft_type"),
        "route_string": parsed.get("route_string"),
        "notes": (
            f"[AUTO-PARSED IMAGE]\n"
            f"Filename: {filename}\n"
            f"Content-Type: {content_type}\n"
            f"Parsed fields: {list(k for k, v in parsed.items() if v)}"
        ),
        "source_type": "image",
        "status": "draft",
    }

    plan = await plan_repo.create_flight_plan(
        db, data=plan_data, user_id=local_user.id, org_id=org_id
    )
    logger.info("Created flight plan %s from image upload (OCR+AI)", plan.id)
    return plan  # type: ignore[return-value]


# ── Single plan operations ─────────────────────────────────────────


@router.get("/{plan_id}", response_model=FlightPlanRead)
async def get_flight_plan(
    plan_id: uuid.UUID,
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> FlightPlanRead:
    """Get a full flight plan with its legs."""
    plan = await plan_repo.get_flight_plan(db, plan_id, local_user.id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flight plan {plan_id} not found",
        )
    return plan  # type: ignore[return-value]


@router.put("/{plan_id}", response_model=FlightPlanRead)
async def update_flight_plan(
    plan_id: uuid.UUID,
    data: FlightPlanUpdate,
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> FlightPlanRead:
    """Partially update a flight plan.

    Only fields present in the request body are updated.
    """
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    plan = await plan_repo.update_flight_plan(
        db, plan_id, update_data, local_user.id
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flight plan {plan_id} not found",
        )
    return plan  # type: ignore[return-value]


# ── Delete ─────────────────────────────────────────────────────────


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flight_plan(
    plan_id: uuid.UUID,
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a flight plan owned by the current user."""
    deleted = await plan_repo.delete_flight_plan(db, plan_id, local_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flight plan {plan_id} not found",
        )


# ── Validation & activation ────────────────────────────────────────


@router.post("/{plan_id}/validate", response_model=ValidationResponse)
async def validate_flight_plan(
    plan_id: uuid.UUID,
    request: Request,
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Trigger LangGraph validation of a flight plan.

    Runs the full Gatekeeper validation pipeline (weather, fuel, route,
    airspace, performance) through the composed Session module.  Falls back to
    a basic structural check when the pipeline is unavailable.
    """
    plan = await plan_repo.get_flight_plan(db, plan_id, local_user.id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flight plan {plan_id} not found",
        )

    # Build a FlightPlanState dict from the ORM model
    flight_plan_data: dict[str, Any] = {
        "departure_icao": plan.departure_icao,
        "arrival_icao": plan.arrival_icao,
        "alternate_icao": plan.alternate_icao,
        "aircraft_type": plan.aircraft_type or "C172",
        "fuel_on_board": plan.fuel_required_gal or 40.0,
        "fuel_reserve": plan.fuel_reserve_gal or 8.0,
        "total_weight": plan.total_weight_lbs or 2200.0,
        "max_weight": plan.max_weight_lbs or 2550.0,
        "flight_rules": "VFR",
        "cruise_altitude": 5500,
        "cruise_speed": 110,
        "estimated_time_enroute": 90.0,
        "route": [],
    }

    try:
        snapshot = await request.app.state.session_module.validate(
            user_id=local_user.id,
            flight_plan=flight_plan_data,
        )
        validation_passed = bool(snapshot.state.get("validation_passed", False))

        # Update plan status based on validation outcome
        new_status = "validated" if validation_passed else "draft"
        await plan_repo.update_status(db, plan_id, new_status, local_user.id)

        logger.info(
            "Validation for plan %s: %s",
            plan_id,
            "PASSED" if validation_passed else "FAILED",
        )

        return ValidationResponse(
            plan_id=str(plan_id),
            valid=validation_passed,
            results=snapshot.state.get("validation_results", []),
            weather=snapshot.state.get("weather"),
            fuel_state=snapshot.state.get("fuel_state"),
            route_info=snapshot.state.get("route_info"),
            airspace_info=snapshot.state.get("airspace_info"),
            aircraft_performance=snapshot.state.get("aircraft_performance"),
            session_id=None,
        )

    except Exception:
        logger.warning(
            "LangGraph validation unavailable for plan %s — running basic check",
            plan_id,
            exc_info=True,
        )
        # Fallback: basic structural validation
        errors: list[dict[str, Any]] = []
        if plan.departure_icao == "ZZZZ":
            errors.append({
                "agent": "gatekeeper",
                "passed": False,
                "severity": "critical",
                "message": "Departure airport is unknown (ZZZZ)",
            })
        if plan.arrival_icao == "ZZZZ":
            errors.append({
                "agent": "gatekeeper",
                "passed": False,
                "severity": "critical",
                "message": "Arrival airport is unknown (ZZZZ)",
            })

        is_valid = len(errors) == 0
        if is_valid:
            await plan_repo.update_status(db, plan_id, "validated", local_user.id)

        return ValidationResponse(
            plan_id=str(plan_id),
            valid=is_valid,
            results=errors,
            weather=None,
            fuel_state=None,
            route_info=None,
            airspace_info=None,
            aircraft_performance=None,
            session_id=None,
        )


@router.post("/{plan_id}/activate", response_model=FlightPlanRead)
async def activate_flight_plan(
    plan_id: uuid.UUID,
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> FlightPlanRead:
    """Set a flight plan's status to ``active``."""
    plan = await plan_repo.update_status(
        db, plan_id, "active", local_user.id
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flight plan {plan_id} not found",
        )
    return plan  # type: ignore[return-value]


# ── Helpers ────────────────────────────────────────────────────────


def _derive_title(parsed: dict[str, Any], source_label: str) -> str:
    """Build a descriptive title from parsed flight plan data.

    Args:
        parsed: Dict of parsed fields (may be empty or have ``None`` values).
        source_label: Short description of the source (e.g. ``"text"``).

    Returns:
        A human-readable title string.
    """
    dep = parsed.get("departure_icao")
    arr = parsed.get("arrival_icao")
    if dep and arr:
        return f"Flight Plan: {dep} → {arr}"
    return f"Flight Plan (from {source_label})"
