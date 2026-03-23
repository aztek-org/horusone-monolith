"""Content management API routes (knowledge base).

- ``GET  /categories``            — category tree
- ``GET  /categories/{slug}``     — single category with articles
- ``GET  /articles/{slug}``       — single article (increments view count)
- ``POST /articles``              — create article (instructor+)
- ``PUT  /articles/{id}``         — update article (instructor+)
- ``GET  /search``                — full-text article search
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.content_repository import ContentRepository
from app.db.session import get_db_session
from app.middleware.auth import CurrentUser, RequireInstructor
from app.middleware.org_context import get_authenticated_user, get_org_id
from app.models.user import User
from app.schemas.content import (
    ContentArticleCreate,
    ContentArticleRead,
    ContentArticleUpdate,
    ContentCategoryRead,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/content", tags=["Content"])

content_repo = ContentRepository()


# ── Categories ─────────────────────────────────────────────────────


@router.get("/categories", response_model=list[ContentCategoryRead])
async def list_categories(
    _user: CurrentUser,
    include_inactive: bool = Query(default=False),
    db: AsyncSession = Depends(get_db_session),
) -> list[ContentCategoryRead]:
    """Get the category tree.

    By default only active categories are returned.  Pass
    ``include_inactive=true`` to include all.
    """
    categories = await content_repo.get_categories(db, include_inactive)
    return categories  # type: ignore[return-value]


@router.get(
    "/categories/{slug}",
    response_model=ContentCategoryRead,
)
async def get_category(
    slug: str,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> ContentCategoryRead:
    """Get a single category by slug with its articles."""
    category = await content_repo.get_category_by_slug(db, slug)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{slug}' not found",
        )
    return category  # type: ignore[return-value]


# ── Articles ───────────────────────────────────────────────────────


@router.get("/articles/{slug}", response_model=ContentArticleRead)
async def get_article(
    slug: str,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> ContentArticleRead:
    """Get a single article by slug.

    Each call increments the article's view count.
    """
    article = await content_repo.get_article_by_slug(db, slug)
    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article '{slug}' not found",
        )
    return article  # type: ignore[return-value]


@router.post(
    "/articles",
    response_model=ContentArticleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_article(
    data: ContentArticleCreate,
    user: RequireInstructor,
    local_user: User = Depends(get_authenticated_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
    db: AsyncSession = Depends(get_db_session),
) -> ContentArticleRead:
    """Create a new content article.

    Requires instructor role or higher.  The ``org_id`` from the
    request body is used if provided; otherwise falls back to the
    user's organisation context.  Articles with ``org_id=null`` are
    platform-wide.
    """
    article_data = data.model_dump()
    # Use explicit org_id from body, otherwise fall back to user's org
    effective_org = article_data.pop("org_id", None) or org_id

    article = await content_repo.create_article(
        db, article_data, author_id=local_user.id, org_id=effective_org
    )
    return article  # type: ignore[return-value]


@router.put(
    "/articles/{article_id}",
    response_model=ContentArticleRead,
)
async def update_article(
    article_id: uuid.UUID,
    data: ContentArticleUpdate,
    _user: RequireInstructor,
    db: AsyncSession = Depends(get_db_session),
) -> ContentArticleRead:
    """Partially update a content article.

    Requires instructor role or higher.  Only fields present in the
    request body are updated.
    """
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    article = await content_repo.update_article(db, article_id, update_data)
    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article {article_id} not found",
        )
    return article  # type: ignore[return-value]


# ── Search ─────────────────────────────────────────────────────────


@router.get("/search", response_model=list[ContentArticleRead])
async def search_articles(
    _user: CurrentUser,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> list[ContentArticleRead]:
    """Full-text search across published articles.

    Uses PostgreSQL ``to_tsvector`` / ``to_tsquery`` with an ILIKE
    fallback when the query cannot be parsed.
    """
    articles = await content_repo.search_articles(db, q, limit, offset)
    return articles  # type: ignore[return-value]
