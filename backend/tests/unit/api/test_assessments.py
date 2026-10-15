"""Unit tests for the knowledge-assessment routes."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1 import assessments
from app.db.session import get_db_session
from app.main import app
from app.middleware.auth import TokenUser, get_current_user
from app.schemas.assessment import AssessmentCreate, AssessmentSubmission


def _user(roles: list[str] | None = None) -> TokenUser:
    return TokenUser(
        keycloak_id="kc-user",
        email="user@test.com",
        display_name="User",
        roles=roles or ["student"],
    )


@pytest.mark.asyncio
async def test_list_assessments_forces_published_for_students() -> None:
    listing = AsyncMock(return_value=[])
    db = object()

    with patch.object(assessments.assessment_repo, "list_assessments", new=listing):
        await assessments.list_assessments(
            user=_user(["student"]), org_id=None, module_id=None, db=db
        )

    assert listing.await_args.kwargs["is_published"] is True


@pytest.mark.asyncio
async def test_list_assessments_instructors_see_unpublished() -> None:
    listing = AsyncMock(return_value=[])
    db = object()

    with patch.object(assessments.assessment_repo, "list_assessments", new=listing):
        await assessments.list_assessments(
            user=_user(["instructor"]), org_id=None, module_id=None, db=db
        )

    assert listing.await_args.kwargs["is_published"] is None


@pytest.mark.asyncio
async def test_get_my_results_scopes_to_local_user() -> None:
    user_id = uuid.uuid4()
    results = AsyncMock(return_value=[])
    db = object()

    with patch.object(assessments.assessment_repo, "get_user_results", new=results):
        await assessments.get_my_results(
            user=_user(),
            _seat=object(),
            local_user=SimpleNamespace(id=user_id),
            limit=10,
            offset=5,
            db=db,
        )

    assert results.await_args.args == (db, user_id, 10, 5)


@pytest.mark.asyncio
async def test_get_assessment_missing_returns_404() -> None:
    with patch.object(
        assessments.assessment_repo,
        "get_assessment",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(HTTPException) as excinfo:
            await assessments.get_assessment(
                assessment_id=uuid.uuid4(), _user=_user(), db=object()
            )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_create_assessment_prefers_body_org() -> None:
    body_org = uuid.uuid4()
    fallback_org = uuid.uuid4()
    created_by = uuid.uuid4()
    create = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    data = AssessmentCreate(title="Radio", org_id=body_org)

    with patch.object(assessments.assessment_repo, "create_assessment", new=create):
        await assessments.create_assessment(
            data=data,
            user=_user(["instructor"]),
            local_user=SimpleNamespace(id=created_by),
            org_id=fallback_org,
            db=object(),
        )

    assert create.await_args.kwargs["org_id"] == body_org
    assert create.await_args.kwargs["created_by"] == created_by
    assert "org_id" not in create.await_args.args[1]


@pytest.mark.asyncio
async def test_submit_assessment_unknown_returns_404() -> None:
    with patch.object(
        assessments.assessment_repo,
        "submit_assessment",
        new=AsyncMock(side_effect=ValueError("Assessment not found")),
    ):
        with pytest.raises(HTTPException) as excinfo:
            await assessments.submit_assessment(
                assessment_id=uuid.uuid4(),
                data=AssessmentSubmission(answers={}),
                user=_user(),
                _seat=object(),
                local_user=SimpleNamespace(id=uuid.uuid4()),
                db=object(),
            )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_submit_assessment_returns_graded_result() -> None:
    result = SimpleNamespace(score=90.0, passed=True)
    with patch.object(
        assessments.assessment_repo,
        "submit_assessment",
        new=AsyncMock(return_value=result),
    ):
        returned = await assessments.submit_assessment(
            assessment_id=uuid.uuid4(),
            data=AssessmentSubmission(answers={"q1": "a"}),
            user=_user(),
            _seat=object(),
            local_user=SimpleNamespace(id=uuid.uuid4()),
            db=object(),
        )

    assert returned is result


def test_create_assessment_requires_instructor_role(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _user(["student"])
    app.dependency_overrides[get_db_session] = lambda: object()

    response = client.post("/api/v1/assessments/", json={"title": "Radio"})

    assert response.status_code == 403
