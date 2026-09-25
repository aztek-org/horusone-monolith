"""Versioned Scene configuration and YAML registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from typing import Any

import yaml

from app.llm import SceneConstraints

_REQUIRED_PROMPT_PLACEHOLDERS = {
    "callsign",
    "aircraft_type",
    "altitude",
    "heading",
    "speed",
    "position",
    "phase",
    "destination",
    "weather",
    "pilot_message",
}


@dataclass(frozen=True)
class SceneConfig:
    """Immutable configuration for one versioned training Scene."""

    version: str
    name: str
    aircraft: dict
    airports: dict
    objectives: list[str]
    difficulty: int
    knowledge_refs: list[str]
    prompt_template: str
    constraints: SceneConstraints

    def __post_init__(self) -> None:
        """Reject prompt grammars that would fail before a live exchange."""
        try:
            self.prompt_template.format(
                **{placeholder: "test" for placeholder in _REQUIRED_PROMPT_PLACEHOLDERS}
            )
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("Scene prompt template cannot be rendered") from exc


class SceneRegistry:
    """Look up immutable Scene configurations by version."""

    def __init__(self, configs: dict[str, SceneConfig]) -> None:
        self._configs = dict(configs)

    def get(self, version: str) -> SceneConfig:
        """Return the requested Scene, raising ``KeyError`` when absent."""
        return self._configs[version]

    def list_all(self) -> list[SceneConfig]:
        """Return every registered Scene in insertion order."""
        return list(self._configs.values())

    def default(self) -> SceneConfig:
        """Return the loaded default Scene, or the built-in default."""
        from app.services.llm.scenes.default_scene import DEFAULT_SCENE

        return self._configs.get(DEFAULT_SCENE.version, DEFAULT_SCENE)


def _scene_from_mapping(raw: dict[str, Any]) -> SceneConfig:
    """Build and validate one Scene from a YAML mapping."""
    missing_fields = [field for field in ("version", "name", "prompt_template") if not raw.get(field)]
    if missing_fields:
        missing = ", ".join(missing_fields)
        raise ValueError(f"Scene is missing required fields: {missing}")

    prompt_template = raw["prompt_template"]
    missing_placeholders = sorted(
        placeholder
        for placeholder in _REQUIRED_PROMPT_PLACEHOLDERS
        if f"{{{placeholder}}}" not in prompt_template
    )
    if missing_placeholders:
        missing = ", ".join(missing_placeholders)
        raise ValueError(f"Scene prompt is missing required placeholders: {missing}")

    placeholders = {
        field_name
        for _, field_name, _, _ in Formatter().parse(prompt_template)
        if field_name is not None
    }
    unexpected_placeholders = sorted(placeholders - _REQUIRED_PROMPT_PLACEHOLDERS)
    if unexpected_placeholders:
        unexpected = ", ".join(unexpected_placeholders)
        raise ValueError(f"Scene prompt has unexpected placeholders: {unexpected}")

    constraints = raw.get("constraints") or {}
    return SceneConfig(
        version=raw["version"],
        name=raw["name"],
        aircraft=raw.get("aircraft") or {},
        airports=raw.get("airports") or {},
        objectives=raw.get("objectives") or [],
        difficulty=raw.get("difficulty", 1),
        knowledge_refs=raw.get("knowledge_refs") or [],
        prompt_template=prompt_template,
        constraints=SceneConstraints(
            temperature=constraints.get("temperature"),
            max_output_tokens=constraints.get("max_output_tokens"),
        ),
    )


def load_scene_configs(path: str | Path) -> SceneRegistry:
    """Load and validate all Scene versions from a YAML file."""
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as config_file:
        document = yaml.safe_load(config_file) or {}

    raw_scenes = document.get("scenes") if isinstance(document, dict) else None
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise ValueError("Scene YAML must contain a non-empty 'scenes' list")

    configs: dict[str, SceneConfig] = {}
    for raw_scene in raw_scenes:
        if not isinstance(raw_scene, dict):
            raise ValueError("Each Scene entry must be a mapping")
        scene = _scene_from_mapping(raw_scene)
        if scene.version in configs:
            raise ValueError(f"Duplicate Scene version: {scene.version}")
        configs[scene.version] = scene

    return SceneRegistry(configs)
