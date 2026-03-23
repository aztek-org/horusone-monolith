"""Flight plan API routes.

- ``GET    /``                — list user's flight plans
- ``POST   /``                — create from form data
- ``POST   /from-text``       — create from plain text (AI stub)
- ``POST   /from-image``      — create from uploaded image (AI stub)
- ``GET    /{id}``            — full flight plan with legs
- ``PUT    /{id}``            — update flight plan
- ``POST   /{id}/validate``   — trigger validation (stub)
- ``POST   /{id}/activate``   — set status to active
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

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
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/flight-plans", tags=["Flight Plans"])

plan_repo = FlightPlanRepository()


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
    """Create a flight plan by parsing free-text input.

    .. note::
        **Stub implementation** — actual AI text parsing will be
        implemented in Phase 3 (LangGraph).  Currently creates a
        draft plan with the raw text stored in ``notes``.
    """
    # TODO(phase3): Replace with LangGraph text-to-flight-plan agent
    effective_org = data.org_id or org_id
    plan = await plan_repo.create_flight_plan(
        db,
        data={
            "title": data.title or "Flight Plan (from text)",
            "departure_icao": "ZZZZ",
            "arrival_icao": "ZZZZ",
            "notes": f"[AUTO-PARSED TEXT]\n{data.text}",
            "source_type": "text",
            "status": "draft",
        },
        user_id=local_user.id,
        org_id=effective_org,
    )
    logger.info("Created draft flight plan %s from text input", plan.id)
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
    """Create a flight plan from an uploaded image (OCR).

    .. note::
        **Stub implementation** — actual OCR/image parsing will be
        implemented in Phase 3 (LangGraph).  Currently creates a
        draft plan noting the image was received.
    """
    # TODO(phase3): Replace with LangGraph image-to-flight-plan agent
    filename = file.filename or "unknown"
    content_type = file.content_type or "unknown"

    plan = await plan_repo.create_flight_plan(
        db,
        data={
            "title": f"Flight Plan (from image: {filename})",
            "departure_icao": "ZZZZ",
            "arrival_icao": "ZZZZ",
            "notes": (
                f"[AUTO-PARSED IMAGE]\n"
                f"Filename: {filename}\n"
                f"Content-Type: {content_type}\n"
                f"TODO: OCR processing pending (Phase 3)"
            ),
            "source_type": "image",
            "status": "draft",
        },
        user_id=local_user.id,
        org_id=org_id,
    )
    logger.info("Created draft flight plan %s from image upload", plan.id)
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


# ── Validation & activation ────────────────────────────────────────


@router.post("/{plan_id}/validate")
async def validate_flight_plan(
    plan_id: uuid.UUID,
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Trigger validation of a flight plan.

    .. note::
        **Stub implementation** — actual Gatekeeper validation logic
        will be implemented in Phase 3 (LangGraph).  Currently always
        returns ``{"valid": true, "errors": []}``.
    """
    # TODO(phase3): Replace with LangGraph Gatekeeper validation agent
    plan = await plan_repo.get_flight_plan(db, plan_id, local_user.id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flight plan {plan_id} not found",
        )

    logger.info("Validation requested for flight plan %s (stub)", plan_id)
    return {"valid": True, "errors": [], "plan_id": str(plan_id)}


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
