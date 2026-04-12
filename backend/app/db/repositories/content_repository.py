"""Repository for content categories and articles."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import ContentArticle, ContentCategory

logger = logging.getLogger(__name__)


class ContentRepository:
    """Data-access layer for the knowledge-base content system.

    Handles category trees, article CRUD, and full-text search.
    """

    # ── Categories ─────────────────────────────────────────────────

    async def get_categories(
        self, db: AsyncSession, include_inactive: bool = False
    ) -> list[ContentCategory]:
        """Get all categories (flat list; tree assembled by caller or schema).

        Args:
            db: Async database session.
            include_inactive: When False, filter out inactive categories.

        Returns:
            List of ContentCategory rows ordered by sort_order.
        """
        query = select(ContentCategory).options(
            selectinload(ContentCategory.children)
        )
        if not include_inactive:
            query = query.where(ContentCategory.is_active.is_(True))
        query = query.order_by(ContentCategory.sort_order, ContentCategory.name)

        result = await db.execute(query)
        return list(result.scalars().unique().all())

    async def get_category_by_slug(
        self, db: AsyncSession, slug: str
    ) -> ContentCategory | None:
        """Get a single category by slug with its articles eagerly loaded.

        Args:
            db: Async database session.
            slug: URL-safe category identifier.

        Returns:
            The ContentCategory with articles, or None.
        """
        result = await db.execute(
            select(ContentCategory)
            .where(ContentCategory.slug == slug)
            .options(
                selectinload(ContentCategory.articles),
                selectinload(ContentCategory.children),
            )
        )
        return result.scalar_one_or_none()

    # ── Articles ───────────────────────────────────────────────────

    async def get_article_by_slug(
        self, db: AsyncSession, slug: str
    ) -> ContentArticle | None:
        """Get a single article by slug and increment its view count.

        Args:
            db: Async database session.
            slug: URL-safe article identifier.

        Returns:
            The ContentArticle, or None.
        """
        result = await db.execute(
            select(ContentArticle).where(ContentArticle.slug == slug)
        )
        article = result.scalar_one_or_none()
        if article is not None:
            await db.execute(
                update(ContentArticle)
                .where(ContentArticle.id == article.id)
                .values(view_count=ContentArticle.view_count + 1)
            )
            article.view_count += 1
        return article

    async def create_article(
        self,
        db: AsyncSession,
        data: dict,
        author_id: uuid.UUID,
        org_id: uuid.UUID | None,
    ) -> ContentArticle:
        """Create a new content article.

        Args:
            db: Async database session.
            data: Dict of article fields from the create schema.
            author_id: UUID of the authoring user.
            org_id: Organisation scope (None = platform-wide).

        Returns:
            The created ContentArticle.
        """
        article = ContentArticle(
            **data,
            author_id=author_id,
            org_id=org_id,
        )
        db.add(article)
        await db.flush()
        await db.refresh(article)
        logger.info("Created article: %s (slug=%s)", article.id, article.slug)
        return article

    async def update_article(
        self,
        db: AsyncSession,
        article_id: uuid.UUID,
        data: dict,
    ) -> ContentArticle | None:
        """Partially update an existing article.

        Args:
            db: Async database session.
            article_id: UUID of the article to update.
            data: Dict of fields to update (only set keys).

        Returns:
            The updated ContentArticle, or None if not found.
        """
        result = await db.execute(
            select(ContentArticle).where(ContentArticle.id == article_id)
        )
        article = result.scalar_one_or_none()
        if article is None:
            return None

        for field_name, value in data.items():
            setattr(article, field_name, value)

        await db.flush()
        await db.refresh(article)
        logger.info("Updated article: %s", article.id)
        return article

    async def get_articles_by_category(
        self,
        db: AsyncSession,
        category_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ContentArticle]:
        """Get articles belonging to a category.

        Args:
            db: Async database session.
            category_id: UUID of the parent category.
            limit: Max rows to return.
            offset: Number of rows to skip.

        Returns:
            List of published ContentArticle entries.
        """
        result = await db.execute(
            select(ContentArticle)
            .where(
                ContentArticle.category_id == category_id,
                ContentArticle.is_published.is_(True),
            )
            .order_by(ContentArticle.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    # ── Full-text search ───────────────────────────────────────────

    async def search_articles(
        self,
        db: AsyncSession,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ContentArticle]:
        """Full-text search articles using PostgreSQL to_tsvector / to_tsquery.

        Falls back to ILIKE if the query cannot be parsed as a tsquery.

        Args:
            db: Async database session.
            query: Search string.
            limit: Max rows to return.
            offset: Number of rows to skip.

        Returns:
            List of matching ContentArticle entries.
        """
        if not query or not query.strip():
            return []

        # Sanitise: replace spaces with & for AND-style matching
        sanitised = " & ".join(
            word for word in query.strip().split() if word
        )

        try:
            ts_query = func.to_tsquery("english", sanitised)
            ts_vector = func.to_tsvector(
                "english",
                ContentArticle.title + " " + ContentArticle.content,
            )
            stmt = (
                select(ContentArticle)
                .where(
                    ts_vector.op("@@")(ts_query),
                    ContentArticle.is_published.is_(True),
                )
                .order_by(
                    func.ts_rank(ts_vector, ts_query).desc()
                )
                .limit(limit)
                .offset(offset)
            )
            result = await db.execute(stmt)
            return list(result.scalars().all())
        except Exception:
            # Fallback: simple ILIKE search
            logger.warning(
                "Full-text search failed for query %r, falling back to ILIKE",
                query,
            )
            pattern = f"%{query}%"
            result = await db.execute(
                select(ContentArticle)
                .where(
                    ContentArticle.is_published.is_(True),
                    (
                        ContentArticle.title.ilike(pattern)
                        | ContentArticle.content.ilike(pattern)
                    ),
                )
                .order_by(ContentArticle.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all())
