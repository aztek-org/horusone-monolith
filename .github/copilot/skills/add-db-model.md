# Skill: Add a New Database Model + Migration

Use this skill when adding a new entity to the Horus backend database.

## Steps

### 1. Create the SQLAlchemy Model (`app/models/<entity>.py`)

```python
"""SQLAlchemy model for <Entity>."""
from datetime import datetime

from sqlalchemy import String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class <Entity>(Base):
    """<Entity> model.

    Attributes:
        id: Primary key.
        name: Human-readable name.
        created_at: Record creation timestamp.
    """

    __tablename__ = "<entities>"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships (if needed)
    # items: Mapped[list["RelatedModel"]] = relationship(back_populates="<entity>")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id} name={self.name!r}>"
```

### 2. Import the model in `app/db/base.py`

```python
# Make sure models are imported before Alembic autogenerate runs
from app.models.<entity> import <Entity>  # noqa: F401
```

### 3. Create the Pydantic Schemas (`app/schemas/<entity>.py`)

See `add-api-endpoint.md` for schema template.

### 4. Create the Repository (`app/db/repositories/<entity>_repo.py`)

```python
from app.db.repositories.base import BaseRepository
from app.models.<entity> import <Entity>
from app.schemas.<entity> import <Entity>Create


class <Entity>Repository(BaseRepository[<Entity>, <Entity>Create]):
    pass
```

### 5. Generate an Alembic Migration

```bash
cd backend
source .venv/bin/activate

# Auto-generate migration from model changes
alembic revision --autogenerate -m "add_<entity>_table"

# Review the generated migration file in alembic/versions/
# Then apply it:
alembic upgrade head
```

> ⚠️ Always review auto-generated migrations before applying. Alembic may miss some changes or generate incorrect SQL for complex types.

### 6. Column Type Reference

| Python Type | SQLAlchemy Type | Notes |
|-------------|----------------|-------|
| `str` | `String(n)` or `Text` | Use String for indexed columns |
| `int` | `Integer` | |
| `float` | `Float` | |
| `bool` | `Boolean` | |
| `datetime` | `DateTime(timezone=True)` | Always use timezone=True |
| `uuid.UUID` | `Uuid` | For public-facing IDs |
| `dict` | `JSON` | For flexible metadata |
| enum | `Enum(MyEnum)` | Use Python enum class |

### 7. Foreign Key Pattern

```python
# In the child model:
parent_id: Mapped[int] = mapped_column(ForeignKey("parents.id"), nullable=False)
parent: Mapped["ParentModel"] = relationship(back_populates="children")

# In the parent model:
children: Mapped[list["ChildModel"]] = relationship(back_populates="parent")
```

### 8. Write Model Tests (`tests/unit/models/test_<entity>.py`)

```python
import pytest
from app.models.<entity> import <Entity>


def test_<entity>_repr() -> None:
    entity = <Entity>(id=1, name="Test")
    assert "Test" in repr(entity)


def test_<entity>_tablename() -> None:
    assert <Entity>.__tablename__ == "<entities>"
```

## After Adding a Model

```bash
cd backend
ruff check app/
mypy app/
pytest tests/ -v
alembic revision --autogenerate -m "add_<entity>_table"
alembic upgrade head
```
