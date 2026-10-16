"""Repository for knowledge assessments and assessment results."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import AssessmentResult, KnowledgeAssessment

logger = logging.getLogger(__name__)


class AssessmentRepository:
    """Data-access layer for knowledge assessments and grading."""

    # ── Assessment CRUD ────────────────────────────────────────────

    async def list_assessments(
        self,
        db: AsyncSession,
        org_id: uuid.UUID | None = None,
        module_id: uuid.UUID | None = None,
        is_published: bool | None = None,
    ) -> list[KnowledgeAssessment]:
        """List assessments with optional filters.

        Args:
            db: Async database session.
            org_id: Optional organisation filter.
            module_id: Optional module filter.
            is_published: If set, filter by published status.

        Returns:
            List of KnowledgeAssessment rows.
        """
        query = select(KnowledgeAssessment)

        if org_id is not None:
            query = query.where(
                (KnowledgeAssessment.org_id == org_id) | KnowledgeAssessment.org_id.is_(None)
            )
        if module_id is not None:
            query = query.where(KnowledgeAssessment.module_id == module_id)
        if is_published is not None:
            query = query.where(KnowledgeAssessment.is_published == is_published)

        result = await db.execute(query.order_by(KnowledgeAssessment.created_at.desc()))
        return list(result.scalars().all())

    async def get_assessment(
        self, db: AsyncSession, assessment_id: uuid.UUID
    ) -> KnowledgeAssessment | None:
        """Get a single assessment by ID.

        Args:
            db: Async database session.
            assessment_id: UUID of the assessment.

        Returns:
            The KnowledgeAssessment or None.
        """
        result = await db.execute(
            select(KnowledgeAssessment).where(KnowledgeAssessment.id == assessment_id)
        )
        return result.scalar_one_or_none()

    async def create_assessment(
        self,
        db: AsyncSession,
        data: dict,
        created_by: uuid.UUID,
        org_id: uuid.UUID | None,
    ) -> KnowledgeAssessment:
        """Create a new knowledge assessment.

        Args:
            db: Async database session.
            data: Dict of assessment fields.
            created_by: UUID of the creating user.
            org_id: Organisation scope.

        Returns:
            The created KnowledgeAssessment.
        """
        assessment = KnowledgeAssessment(
            **data,
            created_by=created_by,
            org_id=org_id,
        )
        db.add(assessment)
        await db.flush()
        await db.refresh(assessment)
        logger.info("Created assessment: %s (%s)", assessment.id, assessment.title)
        return assessment

    # ── Submission and grading ─────────────────────────────────────

    async def submit_assessment(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        assessment_id: uuid.UUID,
        answers: dict[str, Any],
        time_taken_seconds: int | None = None,
    ) -> AssessmentResult:
        """Grade a user's submission and save the result.

        Grading logic: for each question in the assessment, compare
        the submitted answer against the ``correct_answer`` field.
        The score is the percentage of correct answers.

        Args:
            db: Async database session.
            user_id: UUID of the submitting user.
            assessment_id: UUID of the assessment.
            answers: Map of question_id → selected answer.
            time_taken_seconds: Optional time taken.

        Returns:
            The created AssessmentResult.

        Raises:
            ValueError: If the assessment does not exist.
        """
        assessment = await self.get_assessment(db, assessment_id)
        if assessment is None:
            raise ValueError(f"Assessment {assessment_id} not found")

        # Grade the answers
        questions = assessment.questions or []
        total = len(questions)
        correct = 0

        for question in questions:
            q_id = str(question.get("id", ""))
            correct_answer = question.get("correct_answer")
            submitted = answers.get(q_id)
            if submitted is not None and submitted == correct_answer:
                correct += 1

        score = (correct / total * 100) if total > 0 else 0.0
        passed = score >= assessment.passing_score

        result_obj = AssessmentResult(
            user_id=user_id,
            assessment_id=assessment_id,
            score=round(score, 2),
            answers=answers,
            passed=passed,
            time_taken_seconds=time_taken_seconds,
        )
        db.add(result_obj)
        await db.flush()
        await db.refresh(result_obj)
        logger.info(
            "Assessment %s submitted by %s — score=%.1f passed=%s",
            assessment_id,
            user_id,
            score,
            passed,
        )
        return result_obj

    # ── Results ────────────────────────────────────────────────────

    async def get_user_results(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[AssessmentResult]:
        """Get paginated assessment results for a user.

        Args:
            db: Async database session.
            user_id: UUID of the user.
            limit: Max rows to return.
            offset: Rows to skip.

        Returns:
            List of AssessmentResult rows, newest first.
        """
        result = await db.execute(
            select(AssessmentResult)
            .where(AssessmentResult.user_id == user_id)
            .order_by(AssessmentResult.completed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
