# Skill: Add a New FastAPI API Endpoint

Use this skill when adding a new REST endpoint to the Horus backend.

## Steps

### 1. Create or update the Pydantic schema (`app/schemas/<domain>.py`)

```python
from pydantic import BaseModel
from datetime import datetime


class <Resource>Base(BaseModel):
    # Fields common to Create and Response
    name: str
    description: str | None = None


class <Resource>Create(<Resource>Base):
    # Fields only needed on creation
    pass


class <Resource>Response(<Resource>Base):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
```

### 2. Create or update the repository (`app/db/repositories/<domain>_repo.py`)

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.<domain> import <Resource>
from app.schemas.<domain> import <Resource>Create


class <Resource>Repository(BaseRepository[<Resource>, <Resource>Create]):
    async def get_by_name(self, session: AsyncSession, name: str) -> <Resource> | None:
        result = await session.execute(
            select(self.model).where(self.model.name == name)
        )
        return result.scalar_one_or_none()
```

### 3. Add the route (`app/api/routes/<domain>.py`)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.db.repositories.<domain>_repo import <Resource>Repository
from app.schemas.<domain> import <Resource>Create, <Resource>Response

router = APIRouter(prefix="/<resources>", tags=["<Resources>"])
repo = <Resource>Repository()


@router.get("/", response_model=list[<Resource>Response])
async def list_<resources>(
    session: AsyncSession = Depends(get_db_session),
) -> list[<Resource>Response]:
    """List all <resources>."""
    return await repo.get_all(session)


@router.post("/", response_model=<Resource>Response, status_code=status.HTTP_201_CREATED)
async def create_<resource>(
    data: <Resource>Create,
    session: AsyncSession = Depends(get_db_session),
) -> <Resource>Response:
    """Create a new <resource>."""
    return await repo.create(session, data)


@router.get("/{id}", response_model=<Resource>Response)
async def get_<resource>(
    id: int,
    session: AsyncSession = Depends(get_db_session),
) -> <Resource>Response:
    """Get a specific <resource> by ID."""
    item = await repo.get_by_id(session, id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="<Resource> not found")
    return item
```

### 4. Register the router in `app/main.py`

```python
from app.api.routes import <domain>

# Inside the file, after other router includes:
app.include_router(<domain>.router, prefix="/api/v1", tags=["<Resources>"])
```

### 5. Write integration tests (`tests/integration/test_<domain>.py`)

```python
def test_list_<resources>_empty(client):
    response = client.get("/api/v1/<resources>/")
    assert response.status_code == 200
    assert response.json() == []


def test_create_<resource>(client):
    payload = {"name": "Test", "description": "A test item"}
    response = client.post("/api/v1/<resources>/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test"
    assert "id" in data
```

### 6. Run lint and tests

```bash
cd backend
ruff check app/ --fix
mypy app/
pytest tests/ -v
```
