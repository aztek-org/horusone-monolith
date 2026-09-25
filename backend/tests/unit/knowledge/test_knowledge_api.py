import uuid

from fastapi.testclient import TestClient

from app.config import KnowledgeSettings, get_settings
from app.db.session import get_db_session
from app.main import app
from app.middleware.auth import TokenUser, get_current_user
from app.middleware.org_context import (
    get_authenticated_user,
    get_org_id,
    require_active_seat,
)
from app.models.user import User


class StubSession:
    def __init__(self):
        self.values = []

    def add(self, value):
        self.values.append(value)

    async def flush(self):
        for value in self.values:
            if getattr(value, "id", None) is None and hasattr(value, "title"):
                value.id = uuid.uuid4()

    async def execute(self, statement):
        class Result:
            def scalar(self):
                return 0

        return Result()


def test_student_cannot_upload_knowledge(test_settings):
    user = TokenUser("student", "student@example.com", "Student", ["student"])

    async def current_user():
        return user

    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[require_active_seat] = lambda: object()
    app.dependency_overrides[get_org_id] = lambda: None

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/knowledge/documents",
            files={"file": ("notes.md", b"# Notes\n\ntext", "text/markdown")},
            data={"title": "Notes"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 403


def test_instructor_can_upload_knowledge(test_settings):
    org_id = uuid.uuid4()
    user = TokenUser("instructor", "instructor@example.com", "Instructor", ["instructor"])
    local_user = User(
        id=uuid.uuid4(),
        keycloak_id="instructor",
        email=user.email,
        display_name=user.display_name,
    )

    async def current_user():
        return user

    async def authenticated_user():
        return local_user

    app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(
        update={
            "knowledge": KnowledgeSettings(
                chunk_size=4,
                chunk_overlap=1,
                embedding_dimensions=768,
                top_k=5,
                default_chunk_quota=100,
            )
        }
    )
    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[require_active_seat] = lambda: object()
    app.dependency_overrides[get_authenticated_user] = authenticated_user
    app.dependency_overrides[get_org_id] = lambda: org_id
    app.dependency_overrides[get_db_session] = lambda: StubSession()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/knowledge/documents",
            files={"file": ("notes.md", b"one two three four five", "text/markdown")},
            data={"title": "Notes"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 201
    assert response.json()["chunk_count"] == 2
