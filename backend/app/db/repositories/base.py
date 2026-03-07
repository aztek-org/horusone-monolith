"""Generic base repository with common CRUD operations."""
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType")


class BaseRepository(Generic[ModelType, CreateSchemaType]):
    """Generic CRUD repository.

    Args:
        model: The SQLAlchemy model class.
    """

    def __init__(self, model: type[ModelType]) -> None:
        self.model = model

    async def get_by_id(self, session: AsyncSession, record_id: int) -> ModelType | None:
        """Get a record by primary key."""
        result = await session.execute(select(self.model).where(self.model.id == record_id))
        return result.scalar_one_or_none()

    async def get_all(
        self, session: AsyncSession, *, limit: int = 100, offset: int = 0
    ) -> list[ModelType]:
        """Get all records with pagination."""
        result = await session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def create(self, session: AsyncSession, data: CreateSchemaType) -> ModelType:
        """Create a new record."""
        obj = self.model(**data.model_dump())
        session.add(obj)
        await session.flush()
        await session.refresh(obj)
        return obj

    async def delete(self, session: AsyncSession, record_id: int) -> bool:
        """Delete a record by primary key."""
        obj = await self.get_by_id(session, record_id)
        if obj is None:
            return False
        await session.delete(obj)
        return True
