"""Read-only API routes for versioned training Scenes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.middleware.auth import CurrentUser
from app.schemas.scene import SceneRead
from app.services.llm.scenes.registry import SceneRegistry

router = APIRouter(prefix="/scenes", tags=["Scenes"])


@router.get("/", response_model=list[SceneRead])
async def list_scenes(_user: CurrentUser, request: Request) -> list[SceneRead]:
    """List the public training context for every registered Scene version.

    The response always includes the packaged default Scene, even when a
    configured ``SCENES_PATH`` does not name it: the registry's default has to
    be a Scene the Session module can start, so the packaged ``default-v1`` is
    registered alongside the operator's own Scenes and appears after them.
    """
    registry: SceneRegistry = request.app.state.scene_registry
    return [SceneRead.model_validate(scene) for scene in registry.list_all()]


@router.get("/{version}", response_model=SceneRead)
async def get_scene(
    version: str,
    _user: CurrentUser,
    request: Request,
) -> SceneRead:
    """Return one registered Scene version by its exact version identifier.

    An unregistered version is a 404: this never falls back to the default
    Scene, so a client cannot mistake one Scene's context for another's.
    """
    registry: SceneRegistry = request.app.state.scene_registry
    try:
        scene = registry.get(version)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scene '{version}' not found",
        ) from exc
    return SceneRead.model_validate(scene)
