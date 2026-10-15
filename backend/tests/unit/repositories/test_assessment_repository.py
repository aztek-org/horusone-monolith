"""Unit tests for AssessmentRepository.

All database I/O is mocked via AsyncSession — no real DB connection needed.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.repositories.assessment_repository import AssessmentRepository
from app.models.assessment import KnowledgeAssessment


# ── Mock helpers ───────────────────────────────────────────────────────


def _mock_session(scalar_result: object = None) -> AsyncMock:
    """Return an AsyncSession mock whose execute() returns a scalar proxy."""
    session = AsyncMock()
    result_proxy = MagicMock()
    result_proxy.scalar_one_or_none.return_value = scalar_result
    session.execute.return_value = result_proxy
    return session


def _mock_session_scalars(rows: list) -> AsyncMock:
    """Return an AsyncSession mock for queries using ``result.scalars().all()``."""
    session = AsyncMock()
    result_proxy = MagicMock()
    scalars_proxy = MagicMock()
    scalars_proxy.all.return_value = rows
    result_proxy.scalars.return_value = scalars_proxy
    session.execute.return_value = result_proxy
    return session


# ── AssessmentRepository ───────────────────────────────────────────────


class TestAssessmentRepository:
    """Tests for assessment CRUD, grading, and result history."""

    @pytest.mark.asyncio
    async def test_list_assessments_returns_rows(self) -> None:
        row = MagicMock()
        session = _mock_session_scalars([row])
        repo = AssessmentRepository()

        result = await repo.list_assessments(session)

        assert result == [row]
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_assessments_without_filters_has_no_where(self) -> None:
        session = _mock_session_scalars([])
        repo = AssessmentRepository()

        await repo.list_assessments(session)

        query = str(session.execute.await_args.args[0])
        assert "WHERE" not in query

    @pytest.mark.asyncio
    async def test_list_assessments_applies_all_filters(self) -> None:
        session = _mock_session_scalars([])
        repo = AssessmentRepository()

        await repo.list_assessments(
            session,
            org_id=uuid.uuid4(),
            module_id=uuid.uuid4(),
            is_published=True,
        )

        query = str(session.execute.await_args.args[0])
        assert "WHERE" in query
        assert "knowledge_assessments.org_id = " in query
        assert "knowledge_assessments.module_id = " in query
        assert "knowledge_assessments.is_published = " in query

    @pytest.mark.asyncio
    async def test_get_assessment_found(self) -> None:
        fake = MagicMock()
        session = _mock_session(scalar_result=fake)
        repo = AssessmentRepository()

        assert await repo.get_assessment(session, uuid.uuid4()) is fake

    @pytest.mark.asyncio
    async def test_get_assessment_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = AssessmentRepository()

        assert await repo.get_assessment(session, uuid.uuid4()) is None

    @pytest.mark.asyncio
    async def test_create_assessment_persists_and_returns(self) -> None:
        session = AsyncMock()
        session.add = MagicMock()
        repo = AssessmentRepository()
        created_by = uuid.uuid4()
        org_id = uuid.uuid4()

        result = await repo.create_assessment(
            session, {"title": "PPL Basics"}, created_by, org_id
        )

        assert isinstance(result, KnowledgeAssessment)
        assert result.title == "PPL Basics"
        assert result.created_by == created_by
        assert result.org_id == org_id
        session.add.assert_called_once_with(result)
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(result)

    @pytest.mark.asyncio
    async def test_submit_assessment_grades_and_passes(self) -> None:
        assessment = KnowledgeAssessment(
            title="t",
            questions=[
                {"id": "q1", "correct_answer": "A"},
                {"id": "q2", "correct_answer": "B"},
            ],
            passing_score=50.0,
        )
        session = _mock_session(scalar_result=assessment)
        session.add = MagicMock()
        repo = AssessmentRepository()

        result = await repo.submit_assessment(
            session,
            user_id=uuid.uuid4(),
            assessment_id=uuid.uuid4(),
            answers={"q1": "A", "q2": "B"},
            time_taken_seconds=42,
        )

        assert result.score == 100.0
        assert result.passed is True
        assert result.time_taken_seconds == 42
        session.add.assert_called_once_with(result)

    @pytest.mark.asyncio
    async def test_submit_assessment_partial_credit_fails(self) -> None:
        assessment = KnowledgeAssessment(
            title="t",
            questions=[
                {"id": "q1", "correct_answer": "A"},
                {"id": "q2", "correct_answer": "B"},
            ],
            passing_score=75.0,
        )
        session = _mock_session(scalar_result=assessment)
        session.add = MagicMock()
        repo = AssessmentRepository()

        result = await repo.submit_assessment(
            session,
            user_id=uuid.uuid4(),
            assessment_id=uuid.uuid4(),
            answers={"q1": "A", "q2": "WRONG"},
        )

        assert result.score == 50.0
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_submit_assessment_no_questions_scores_zero(self) -> None:
        assessment = KnowledgeAssessment(title="t", questions=[], passing_score=70.0)
        session = _mock_session(scalar_result=assessment)
        session.add = MagicMock()
        repo = AssessmentRepository()

        result = await repo.submit_assessment(
            session, user_id=uuid.uuid4(), assessment_id=uuid.uuid4(), answers={}
        )

        assert result.score == 0.0
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_submit_assessment_missing_raises_value_error(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = AssessmentRepository()

        with pytest.raises(ValueError):
            await repo.submit_assessment(
                session, user_id=uuid.uuid4(), assessment_id=uuid.uuid4(), answers={}
            )

    @pytest.mark.asyncio
    async def test_get_user_results_returns_rows(self) -> None:
        rows = [MagicMock(), MagicMock()]
        session = _mock_session_scalars(rows)
        repo = AssessmentRepository()

        assert await repo.get_user_results(session, uuid.uuid4()) == rows
