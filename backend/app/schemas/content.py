"""Pydantic schemas for content categories and articles."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── ContentCategory ───────────────────────────────────────────────


class ContentCategoryRead(BaseModel):
    """Schema returned when reading a content category.

    Includes nested ``children`` for hierarchical display.
    """

    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    parent_id: uuid.UUID | None = None
    sort_order: int
    icon: str | None = None
    is_active: bool
    created_at: datetime
    children: list[ContentCategoryRead] = []

    model_config = {"from_attributes": True}


# ── ContentArticle ────────────────────────────────────────────────


class ContentArticleCreate(BaseModel):
    """Schema for creating a content article."""

    category_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=500)
    slug: str = Field(
        ...,
        min_length=1,
        max_length=500,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    content: str = Field(..., min_length=1)
    summary: str | None = Field(default=None, max_length=1000)
    difficulty_level: int = Field(default=1, ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    org_id: uuid.UUID | None = None
    is_published: bool = False


class ContentArticleRead(BaseModel):
    """Schema returned when reading a content article."""

    id: uuid.UUID
    category_id: uuid.UUID
    title: str
    slug: str
    content: str
    summary: str | None = None
    difficulty_level: int
    tags: list[Any]
    author_id: uuid.UUID | None = None
    org_id: uuid.UUID | None = None
    is_published: bool
    view_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContentArticleUpdate(BaseModel):
    """Schema for partial article updates."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    content: str | None = Field(default=None, min_length=1)
    summary: str | None = Field(default=None, max_length=1000)
    difficulty_level: int | None = Field(default=None, ge=1, le=5)
    tags: list[str] | None = None
    is_published: bool | None = None


class ContentSearchResult(BaseModel):
    """Schema for full-text search results."""

    id: uuid.UUID
    title: str
    slug: str
    summary: str | None = None
    category_name: str
    difficulty_level: int
    relevance: float | None = None

    model_config = {"from_attributes": True}
