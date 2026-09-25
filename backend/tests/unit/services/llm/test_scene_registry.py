"""Unit tests for versioned Scene configuration and YAML loading."""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from app.services.llm.scenes.default_scene import DEFAULT_SCENE
from app.services.llm.scenes.registry import SceneConfig, SceneRegistry, load_scene_configs

_REPO_ROOT = Path(__file__).resolve().parents[5]
_BROKEN_CONVERSION = (
    "Placeholders: {pilot_message} {callsign} {aircraft_type} {altitude} "
    "{heading} {speed} {position} {phase} {destination} {weather} "
    "{pilot_message!z}"
)


def _scene_with_prompt(prompt_template: str) -> SceneConfig:
    return SceneConfig(
        version="direct-v1",
        name="Direct",
        aircraft={},
        airports={},
        objectives=[],
        difficulty=1,
        knowledge_refs=[],
        prompt_template=prompt_template,
        constraints=DEFAULT_SCENE.constraints,
    )


def test_default_scene_is_versioned_and_constrained() -> None:
    assert DEFAULT_SCENE.version == "default-v1"
    assert DEFAULT_SCENE.aircraft["type"] == "C172"
    assert DEFAULT_SCENE.airports["departure"] == "KLAX"
    assert DEFAULT_SCENE.airports["arrival"] == "KSFO"
    assert DEFAULT_SCENE.difficulty == 1
    assert DEFAULT_SCENE.constraints.temperature == 0.3
    assert DEFAULT_SCENE.constraints.max_output_tokens == 150
    assert DEFAULT_SCENE.prompt_template.count("{pilot_message}") == 1
    assert "Example exchanges:" in DEFAULT_SCENE.prompt_template
    assert "Safety is paramount" in DEFAULT_SCENE.prompt_template


def test_registry_lookup() -> None:
    registry = SceneRegistry({DEFAULT_SCENE.version: DEFAULT_SCENE})

    assert registry.get("default-v1") is DEFAULT_SCENE
    with pytest.raises(KeyError):
        registry.get("missing-v9")


def test_registry_falls_back_to_default_scene() -> None:
    other_scene = replace(DEFAULT_SCENE, version="other-v1")
    registry = SceneRegistry({other_scene.version: other_scene})

    assert registry.default() is DEFAULT_SCENE


def test_example_config_loads(tmp_path: Path) -> None:
    destination = tmp_path / "scenes.yaml"
    shutil.copy(_REPO_ROOT / "docs/architecture/scene-config.example.yaml", destination)

    registry = load_scene_configs(destination)

    assert registry.default().version == "default-v1"
    assert registry.get("kef-ILS-25L-v1").name == "Keflavik ILS Runway 25L"


@pytest.mark.parametrize("missing_field", ["version", "name", "prompt_template"])
def test_loader_rejects_missing_required_fields(tmp_path: Path, missing_field: str) -> None:
    scene = {
        "version": "broken-v1",
        "name": "Broken",
        "prompt_template": "Placeholders: {pilot_message} {callsign} {aircraft_type} "
        "{altitude} {heading} {speed} {position} {phase} {destination} {weather}",
    }
    del scene[missing_field]
    path = tmp_path / "scenes.yaml"
    path.write_text(f"scenes:\n  - {json.dumps(scene)}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required fields"):
        load_scene_configs(path)


def test_loader_rejects_duplicate_versions(tmp_path: Path) -> None:
    scene = {
        "version": "duplicate-v1",
        "name": "Duplicate",
        "prompt_template": "Placeholders: {pilot_message} {callsign} {aircraft_type} "
        "{altitude} {heading} {speed} {position} {phase} {destination} {weather}",
    }
    path = tmp_path / "scenes.yaml"
    path.write_text(
        f"scenes:\n  - {json.dumps(scene)}\n  - {json.dumps(scene)}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate Scene version"):
        load_scene_configs(path)


def test_loader_rejects_unknown_prompt_placeholders(tmp_path: Path) -> None:
    path = tmp_path / "scenes.yaml"
    path.write_text(
        """
scenes:
  - version: broken-v1
    name: Broken
    prompt_template: "Placeholders: {pilot_message} {callsign} {aircraft_type} {altitude} {heading} {speed} {position} {phase} {destination} {weather} {unknown}"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unexpected placeholders"):
        load_scene_configs(path)


def test_loader_applies_optional_defaults(tmp_path: Path) -> None:
    path = tmp_path / "scenes.yaml"
    path.write_text(
        """
scenes:
  - version: minimal-v1
    name: Minimal
    prompt_template: "Placeholders: {pilot_message} {callsign} {aircraft_type} {altitude} {heading} {speed} {position} {phase} {destination} {weather}"
""",
        encoding="utf-8",
    )

    scene = load_scene_configs(path).get("minimal-v1")

    assert scene.aircraft == {}
    assert scene.airports == {}
    assert scene.objectives == []
    assert scene.difficulty == 1
    assert scene.constraints.temperature is None


def test_loader_rejects_a_prompt_missing_required_placeholders(tmp_path: Path) -> None:
    path = tmp_path / "scenes.yaml"
    path.write_text(
        """
scenes:
  - version: broken-v1
    name: Broken
    prompt_template: "Tell {pilot_message} to contact {callsign}."
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required placeholders"):
        load_scene_configs(path)


def test_loader_rejects_invalid_prompt_conversion(tmp_path: Path) -> None:
    path = tmp_path / "scenes.yaml"
    path.write_text(
        f"""
scenes:
  - version: broken-v1
    name: Broken
    prompt_template: "{_BROKEN_CONVERSION}"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cannot be rendered"):
        load_scene_configs(path)


def test_direct_scene_construction_rejects_invalid_prompt_conversion() -> None:
    with pytest.raises(ValueError, match="cannot be rendered"):
        _scene_with_prompt(_BROKEN_CONVERSION)
