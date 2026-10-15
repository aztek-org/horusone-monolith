"""Unit tests for ContentRepository.

All database I/O is mocked via AsyncSession — no real DB connection needed.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.repositories.content_repository import ContentRepository
from app.models.content import ContentArticle


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


def _mock_session_scalars_unique(rows: list) -> AsyncMock:
    """Return an AsyncSession mock for ``result.scalars().unique().all()``."""
    session = AsyncMock()
    result_proxy = MagicMock()
    unique_proxy = MagicMock()
    unique_proxy.all.return_value = rows
    scalars_proxy = MagicMock()
    scalars_proxy.unique.return_value = unique_proxy
    result_proxy.scalars.return_value = scalars_proxy
    session.execute.return_value = result_proxy
    return session


# ── ContentRepository ──────────────────────────────────────────────────


class TestContentRepository:
    """Tests for content category, article, and search queries."""

    @pytest.mark.asyncio
    async def test_get_categories_returns_rows(self) -> None:
        row = MagicMock()
        session = _mock_session_scalars_unique([row])
        repo = ContentRepository()

        assert await repo.get_categories(session) == [row]

    @pytest.mark.asyncio
    async def test_get_categories_filters_inactive_by_default(self) -> None:
        session = _mock_session_scalars_unique([])
        repo = ContentRepository()

        await repo.get_categories(session)

        query = str(session.execute.await_args.args[0])
        assert "content_categories.is_active IS true" in query

    @pytest.mark.asyncio
    async def test_get_categories_include_inactive_skips_filter(self) -> None:
        session = _mock_session_scalars_unique([])
        repo = ContentRepository()

        await repo.get_categories(session, include_inactive=True)

        query = str(session.execute.await_args.args[0])
        assert "WHERE" not in query

    @pytest.mark.asyncio
    async def test_get_category_by_slug_found(self) -> None:
        fake = MagicMock()
        session = _mock_session(scalar_result=fake)
        repo = ContentRepository()

        assert await repo.get_category_by_slug(session, "basics") is fake

    @pytest.mark.asyncio
    async def test_get_category_by_slug_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = ContentRepository()

        assert await repo.get_category_by_slug(session, "missing") is None

    @pytest.mark.asyncio
    async def test_get_article_by_slug_increments_view_count(self) -> None:
        article = MagicMock()
        article.id = uuid.uuid4()
        article.view_count = 5
        select_proxy = MagicMock()
        select_proxy.scalar_one_or_none.return_value = article
        update_proxy = MagicMock()
        session = AsyncMock()
        session.execute.side_effect = [select_proxy, update_proxy]
        repo = ContentRepository()

        result = await repo.get_article_by_slug(session, "how-to")

        assert result is article
        assert article.view_count == 6
        assert session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_get_article_by_slug_not_found_no_increment(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = ContentRepository()

        assert await repo.get_article_by_slug(session, "missing") is None
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_article_persists_and_returns(self) -> None:
        session = AsyncMock()
        session.add = MagicMock()
        repo = ContentRepository()
        author_id = uuid.uuid4()
        org_id = uuid.uuid4()

        result = await repo.create_article(
            session,
            {"category_id": uuid.uuid4(), "title": "T", "slug": "t", "content": "body"},
            author_id,
            org_id,
        )

        assert isinstance(result, ContentArticle)
        assert result.author_id == author_id
        assert result.org_id == org_id
        session.add.assert_called_once_with(result)
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_article_applies_fields(self) -> None:
        article = MagicMock()
        session = _mock_session(scalar_result=article)
        repo = ContentRepository()

        result = await repo.update_article(session, uuid.uuid4(), {"title": "New"})

        assert result is article
        assert article.title == "New"
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_article_not_found_returns_none(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = ContentRepository()

        assert await repo.update_article(session, uuid.uuid4(), {"title": "New"}) is None
        session.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_articles_by_category_returns_published(self) -> None:
        rows = [MagicMock()]
        session = _mock_session_scalars(rows)
        repo = ContentRepository()

        assert await repo.get_articles_by_category(session, uuid.uuid4()) == rows

        query = str(session.execute.await_args.args[0])
        assert "content_articles.is_published IS true" in query

    @pytest.mark.asyncio
    async def test_search_articles_empty_query_returns_empty(self) -> None:
        session = AsyncMock()
        repo = ContentRepository()

        assert await repo.search_articles(session, "   ") == []
        session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_search_articles_builds_tsquery(self) -> None:
        row = MagicMock()
        session = _mock_session_scalars([row])
        repo = ContentRepository()

        assert await repo.search_articles(session, "engine failure") == [row]

        query = str(session.execute.await_args.args[0])
        assert "to_tsquery" in query
        assert "to_tsvector" in query

    @pytest.mark.asyncio
    async def test_search_articles_falls_back_to_ilike(self) -> None:
        row = MagicMock()
        fallback_proxy = MagicMock()
        scalars_proxy = MagicMock()
        scalars_proxy.all.return_value = [row]
        fallback_proxy.scalars.return_value = scalars_proxy
        session = AsyncMock()
        session.execute.side_effect = [RuntimeError("bad tsquery"), fallback_proxy]
        repo = ContentRepository()

        result = await repo.search_articles(session, "engine failure")

        assert result == [row]
        fallback_query = str(session.execute.await_args.args[0])
        assert "LIKE" in fallback_query.upper()
        assert "to_tsquery" not in fallback_query
