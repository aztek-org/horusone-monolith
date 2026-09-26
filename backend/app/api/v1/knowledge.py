"""Knowledge document ingestion and tenant-scoped retrieval routes."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import has_role
from app.db.session import get_db_session
from app.knowledge.ingest import KnowledgeIngestor
from app.knowledge.types import DocumentUpload, RetrievalQuery
from app.middleware.auth import CurrentUser
from app.middleware.org_context import (
    RequireActiveSeat,
    get_authenticated_user,
    get_org_id,
)
from app.models.user import User
from app.schemas.knowledge import IngestStatusResponse, RetrievedChunkRead

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


@router.post(
    "/documents",
    response_model=IngestStatusResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    request: Request,
    _seat: RequireActiveSeat,
    _user: CurrentUser,
    file: UploadFile = File(...),
    title: str = Form(...),
    publish: bool = Form(False),
    org_id: uuid.UUID | None = Depends(get_org_id),
    local_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> IngestStatusResponse:
    """Extract, embed, and stage a document for the active organization."""
    if not has_role(_user, "org-admin", "instructor", "collaborator", "staff"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Knowledge upload requires instructor, collaborator, or staff role"
            ),
        )

    ingestor = KnowledgeIngestor(
        request.app.state.llm,
        request.app.state.settings.knowledge,
        request.app.state.settings.llm.embedding_model,
    )
    result = await ingestor.ingest(
        db,
        DocumentUpload(
            title=title,
            source_filename=file.filename or "upload",
            content=await file.read(),
            org_id=org_id,
            created_by=local_user.id,
            is_published=publish,
        ),
    )
    return IngestStatusResponse(
        document_id=result.document_id,
        chunk_count=result.chunk_count,
        status=result.status,
    )


@router.get("/search", response_model=list[RetrievedChunkRead])
async def search_knowledge(
    request: Request,
    _seat: RequireActiveSeat,
    org_id: uuid.UUID | None = Depends(get_org_id),
    q: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=20),
    mode: Literal["hybrid", "vector", "text"] = "hybrid",
    knowledge_refs: list[str] | None = Query(default=None),
) -> list[RetrievedChunkRead]:
    """Return published chunks visible to the active organization."""
    return await request.app.state.retriever.search(
        RetrievalQuery(
            query=q,
            org_id=org_id,
            top_k=top_k,
            knowledge_refs=knowledge_refs or [],
            mode=mode,
        )
    )
