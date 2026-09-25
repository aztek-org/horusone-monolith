"""Scene-level generation constraints."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SceneConstraints:
    """Optional overrides for generation temperature and output length."""

    temperature: float | None = None
    max_output_tokens: int | None = None


def merge(base: SceneConstraints, override: SceneConstraints) -> SceneConstraints:
    """Apply explicitly set scene overrides to base generation constraints."""
    return SceneConstraints(
        temperature=(
            override.temperature if override.temperature is not None else base.temperature
        ),
        max_output_tokens=(
            override.max_output_tokens
            if override.max_output_tokens is not None
            else base.max_output_tokens
        ),
    )
