"""Pydantic response schema for versioned training Scenes."""

from pydantic import BaseModel


class SceneRead(BaseModel):
    """Public identity and training context for one Scene version."""

    version: str
    name: str
    aircraft: dict
    airports: dict
    objectives: list[str]
    difficulty: int
    knowledge_refs: list[str]

    model_config = {"from_attributes": True}
