"""Scenario API routes."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.scenario_repo import ScenarioRepository
from app.db.session import get_db_session
from app.schemas.scenario import ScenarioCreate, ScenarioResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scenarios", tags=["Scenarios"])
repo = ScenarioRepository()


@router.get("/", response_model=list[ScenarioResponse])
async def list_scenarios(
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session),
) -> list[ScenarioResponse]:
    """List all training scenarios."""
    return await repo.get_all(session, limit=limit, offset=offset)  # type: ignore[return-value]


@router.post("/", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    data: ScenarioCreate,
    session: AsyncSession = Depends(get_db_session),
) -> ScenarioResponse:
    """Create a new training scenario."""
    scenario = await repo.create(session, data)
    logger.info(f"Created scenario: {scenario.id} - {scenario.name}")
    return scenario  # type: ignore[return-value]


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> ScenarioResponse:
    """Get a specific training scenario by ID."""
    scenario = await repo.get_by_id(session, scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario {scenario_id} not found",
        )
    return scenario  # type: ignore[return-value]
