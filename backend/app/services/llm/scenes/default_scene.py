"""Built-in default Scene loaded from its versioned YAML resource."""

from pathlib import Path

from app.services.llm.scenes.registry import SceneConfig, load_scene_configs

DEFAULT_SCENE: SceneConfig = load_scene_configs(
    Path(__file__).parents[3] / "resources/scenes/default-v1.yaml"
).get("default-v1")
