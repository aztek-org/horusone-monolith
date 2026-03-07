---
name: Add Database Model
description: >
  Guide to create a new SQLAlchemy ORM model with Alembic migration, repository,
  and Pydantic schemas for the Horus backend database.
---

# Add a New Database Model + Migration

Use this skill when adding a new entity to the Horus backend database.

## Steps

### 1. Create the SQLAlchemy Model (`app/models/<entity>.py`)

```python
from datetime import datetime

from sqlalchemy import String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class <Entity>(Base):
    __tablename__ = "<entities>"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id} name={self.name!r}>"
```

### 2. Register the model in `app/db/registry.py`

```python
from app.models.<entity> import <Entity>  # noqa: F401
```

### 3. Create the Pydantic Schemas (`app/schemas/<entity>.py`)

See the `add-api-endpoint` skill for the schema template.

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
alembic revision --autogenerate -m "add_<entity>_table"
# Review the generated migration, then apply:
alembic upgrade head
```

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

### 7. Foreign Key Pattern

```python
# Child model:
parent_id: Mapped[int] = mapped_column(ForeignKey("parents.id"), nullable=False)
parent: Mapped["ParentModel"] = relationship(back_populates="children")

# Parent model:
children: Mapped[list["ChildModel"]] = relationship(back_populates="parent")
```

### 8. Run checks

```bash
cd backend
ruff check app/
mypy app/
pytest tests/ -v
alembic revision --autogenerate -m "add_<entity>_table"
alembic upgrade head
```
