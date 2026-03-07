"""Training session API routes."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.session_repo import TrainingSessionRepository
from app.db.session import get_db_session
from app.schemas.training_session import TrainingSessionCreate, TrainingSessionResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["Sessions"])
repo = TrainingSessionRepository()


@router.get("/", response_model=list[TrainingSessionResponse])
async def list_sessions(
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session),
) -> list[TrainingSessionResponse]:
    """List all training sessions."""
    return await repo.get_all(session, limit=limit, offset=offset)  # type: ignore[return-value]


@router.post("/", response_model=TrainingSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: TrainingSessionCreate,
    session: AsyncSession = Depends(get_db_session),
) -> TrainingSessionResponse:
    """Create a new training session."""
    training_session = await repo.create(session, data)
    logger.info(f"Created training session: {training_session.id}")
    return training_session  # type: ignore[return-value]


@router.get("/{session_id}", response_model=TrainingSessionResponse)
async def get_session(
    session_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> TrainingSessionResponse:
    """Get a specific training session by ID."""
    training_session = await repo.get_with_logs(session, session_id)
    if training_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return training_session  # type: ignore[return-value]
