"""Unit tests for the content-management schemas."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.content import (
    ContentArticleCreate,
    ContentArticleRead,
    ContentArticleUpdate,
    ContentCategoryDetailRead,
    ContentCategoryRead,
    ContentSearchResult,
)


class TestContentArticleCreate:
    def test_defaults(self) -> None:
        article = ContentArticleCreate(
            category_id=uuid.uuid4(),
            title="Pattern Work",
            slug="pattern-work",
            content="Body",
        )
        assert article.difficulty_level == 1
        assert article.tags == []
        assert article.is_published is False
        assert article.org_id is None

    def test_slug_rejects_uppercase_and_spaces(self) -> None:
        with pytest.raises(ValidationError, match="slug"):
            ContentArticleCreate(
                category_id=uuid.uuid4(),
                title="T",
                slug="Bad Slug",
                content="Body",
            )

    def test_slug_accepts_kebab_case(self) -> None:
        article = ContentArticleCreate(
            category_id=uuid.uuid4(),
            title="T",
            slug="a-b-c-1",
            content="Body",
        )
        assert article.slug == "a-b-c-1"

    def test_difficulty_level_bounds(self) -> None:
        with pytest.raises(ValidationError, match="difficulty_level"):
            ContentArticleCreate(
                category_id=uuid.uuid4(), title="T", slug="t", content="B",
                difficulty_level=6,
            )

    def test_content_must_not_be_empty(self) -> None:
        with pytest.raises(ValidationError, match="content"):
            ContentArticleCreate(
                category_id=uuid.uuid4(), title="T", slug="t", content=""
            )


class TestContentArticleUpdate:
    def test_all_fields_optional(self) -> None:
        update = ContentArticleUpdate()
        assert update.title is None
        assert update.difficulty_level is None

    def test_rejects_empty_title_when_supplied(self) -> None:
        with pytest.raises(ValidationError, match="title"):
            ContentArticleUpdate(title="")

    def test_rejects_out_of_range_difficulty(self) -> None:
        with pytest.raises(ValidationError, match="difficulty_level"):
            ContentArticleUpdate(difficulty_level=0)


class TestContentCategoryRead:
    def test_defaults_children_empty(self) -> None:
        category = ContentCategoryRead(
            id=uuid.uuid4(),
            name="Basics",
            slug="basics",
            sort_order=0,
            is_active=True,
            created_at="2024-01-01T00:00:00",
        )
        assert category.children == []
        assert category.parent_id is None

    def test_detail_read_defaults_articles_empty(self) -> None:
        category = ContentCategoryDetailRead(
            id=uuid.uuid4(),
            name="Basics",
            slug="basics",
            sort_order=0,
            is_active=True,
            created_at="2024-01-01T00:00:00",
        )
        assert category.articles == []


class TestContentArticleRead:
    def test_accepts_full_row(self) -> None:
        read = ContentArticleRead(
            id=uuid.uuid4(),
            category_id=uuid.uuid4(),
            title="T",
            slug="t",
            content="B",
            difficulty_level=2,
            tags=[],
            is_published=True,
            view_count=3,
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )
        assert read.view_count == 3


class TestContentSearchResult:
    def test_defaults(self) -> None:
        result = ContentSearchResult(
            id=uuid.uuid4(),
            title="T",
            slug="t",
            category_name="Basics",
            difficulty_level=1,
        )
        assert result.relevance is None
        assert result.summary is None
