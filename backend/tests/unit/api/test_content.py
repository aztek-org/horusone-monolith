"""Unit tests for the content (knowledge base) routes."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1 import content
from app.db.session import get_db_session
from app.main import app
from app.middleware.auth import TokenUser, get_current_user
from app.schemas.content import ContentArticleCreate, ContentArticleUpdate


def _user(roles: list[str] | None = None) -> TokenUser:
    return TokenUser(
        keycloak_id="kc-user",
        email="user@test.com",
        display_name="User",
        roles=roles or ["instructor"],
    )


@pytest.mark.asyncio
async def test_list_categories_forwards_include_inactive() -> None:
    listing = AsyncMock(return_value=[SimpleNamespace(id=uuid.uuid4())])
    db = object()

    with patch.object(content.content_repo, "get_categories", new=listing):
        await content.list_categories(_user=_user(), include_inactive=True, db=db)

    assert listing.await_args.args == (db, True)


@pytest.mark.asyncio
async def test_get_category_missing_returns_404() -> None:
    with patch.object(
        content.content_repo,
        "get_category_by_slug",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(HTTPException) as excinfo:
            await content.get_category(slug="missing", _user=_user(), db=object())

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_get_article_missing_returns_404() -> None:
    with patch.object(
        content.content_repo,
        "get_article_by_slug",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(HTTPException) as excinfo:
            await content.get_article(slug="missing", _user=_user(), db=object())

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_create_article_prefers_body_org_over_user_org() -> None:
    body_org = uuid.uuid4()
    fallback_org = uuid.uuid4()
    author_id = uuid.uuid4()
    create = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    data = ContentArticleCreate(
        category_id=uuid.uuid4(),
        title="Approach",
        slug="approach",
        content="body",
        org_id=body_org,
    )

    with patch.object(content.content_repo, "create_article", new=create):
        await content.create_article(
            data=data,
            user=_user(),
            local_user=SimpleNamespace(id=author_id),
            org_id=fallback_org,
            db=object(),
        )

    assert create.await_args.kwargs["org_id"] == body_org
    assert create.await_args.kwargs["author_id"] == author_id


@pytest.mark.asyncio
async def test_create_article_falls_back_to_user_org() -> None:
    fallback_org = uuid.uuid4()
    create = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    data = ContentArticleCreate(
        category_id=uuid.uuid4(), title="Approach", slug="approach", content="body"
    )

    with patch.object(content.content_repo, "create_article", new=create):
        await content.create_article(
            data=data,
            user=_user(),
            local_user=SimpleNamespace(id=uuid.uuid4()),
            org_id=fallback_org,
            db=object(),
        )

    assert create.await_args.kwargs["org_id"] == fallback_org


@pytest.mark.asyncio
async def test_update_article_rejects_empty_body() -> None:
    with pytest.raises(HTTPException) as excinfo:
        await content.update_article(
            article_id=uuid.uuid4(),
            data=ContentArticleUpdate(),
            _user=_user(),
            db=object(),
        )

    assert excinfo.value.status_code == 400


@pytest.mark.asyncio
async def test_update_article_missing_returns_404() -> None:
    with patch.object(
        content.content_repo, "update_article", new=AsyncMock(return_value=None)
    ):
        with pytest.raises(HTTPException) as excinfo:
            await content.update_article(
                article_id=uuid.uuid4(),
                data=ContentArticleUpdate(title="New"),
                _user=_user(),
                db=object(),
            )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_search_articles_forwards_query() -> None:
    search = AsyncMock(return_value=[])
    db = object()

    with patch.object(content.content_repo, "search_articles", new=search):
        await content.search_articles(
            _user=_user(), q="altitude", limit=10, offset=5, db=db
        )

    assert search.await_args.args == (db, "altitude", 10, 5)


def test_create_article_requires_instructor_role(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _user(["student"])
    app.dependency_overrides[get_db_session] = lambda: object()

    response = client.post(
        "/api/v1/content/articles",
        json={
            "category_id": str(uuid.uuid4()),
            "title": "Approach",
            "slug": "approach",
            "content": "body",
        },
    )

    assert response.status_code == 403
