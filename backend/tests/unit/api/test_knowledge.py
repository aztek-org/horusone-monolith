"""Unit tests for the knowledge ingestion and retrieval routes."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1 import knowledge
from app.middleware.auth import TokenUser


def _token(roles: list[str]) -> TokenUser:
    return TokenUser(
        keycloak_id="kc-user",
        email="user@test.com",
        display_name="User",
        roles=roles,
    )


def _request(ingestor: object | None = None, retriever: object | None = None) -> SimpleNamespace:
    state = SimpleNamespace(
        llm=object(),
        settings=SimpleNamespace(
            knowledge=object(),
            llm=SimpleNamespace(embedding_model="nomic-embed-text"),
        ),
        retriever=retriever or AsyncMock(),
    )
    return SimpleNamespace(app=SimpleNamespace(state=state))


@pytest.mark.asyncio
async def test_upload_document_requires_privileged_role() -> None:
    with pytest.raises(HTTPException) as excinfo:
        await knowledge.upload_document(
            request=_request(),
            _seat=object(),
            _user=_token(["student"]),
            file=SimpleNamespace(filename="doc.pdf", read=AsyncMock(return_value=b"x")),
            title="Doc",
            publish=False,
            org_id=uuid.uuid4(),
            local_user=SimpleNamespace(id=uuid.uuid4()),
            db=object(),
        )

    assert excinfo.value.status_code == 403


class _StubIngestor:
    """Knowledge ingestor stand-in that records construction and returns a result."""

    instances: list[_StubIngestor] = []

    def __init__(self, *_args: object) -> None:
        self.args = _args
        self.uploads: list[object] = []
        _StubIngestor.instances.append(self)

    async def ingest(self, _db: object, upload: object) -> SimpleNamespace:
        self.uploads.append(upload)
        return SimpleNamespace(document_id=uuid.uuid4(), chunk_count=3, status="staged")


@pytest.mark.asyncio
async def test_upload_document_ingests_for_privileged_role() -> None:
    _StubIngestor.instances.clear()
    local_user_id = uuid.uuid4()
    org_id = uuid.uuid4()

    with patch.object(knowledge, "KnowledgeIngestor", _StubIngestor):
        result = await knowledge.upload_document(
            request=_request(),
            _seat=object(),
            _user=_token(["instructor"]),
            file=SimpleNamespace(filename="doc.pdf", read=AsyncMock(return_value=b"data")),
            title="Doc",
            publish=True,
            org_id=org_id,
            local_user=SimpleNamespace(id=local_user_id),
            db=object(),
        )

    assert result.chunk_count == 3
    upload = _StubIngestor.instances[0].uploads[0]
    assert upload.org_id == org_id
    assert upload.created_by == local_user_id
    assert upload.is_published is True
    assert upload.content == b"data"


@pytest.mark.asyncio
async def test_search_knowledge_builds_org_scoped_query() -> None:
    org_id = uuid.uuid4()
    retriever = AsyncMock()
    retriever.search = AsyncMock(return_value=[])

    result = await knowledge.search_knowledge(
        request=_request(retriever=retriever),
        _seat=object(),
        org_id=org_id,
        q="holding pattern",
        top_k=7,
        mode="text",
        knowledge_refs=["ref-a"],
    )

    assert result == []
    query = retriever.search.await_args.args[0]
    assert query.query == "holding pattern"
    assert query.org_id == org_id
    assert query.top_k == 7
    assert query.mode == "text"
    assert query.knowledge_refs == ["ref-a"]
