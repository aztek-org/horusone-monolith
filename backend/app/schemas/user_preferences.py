"""Pydantic schemas for user preferences."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ── Typed preference sub-models (reference structure) ──────────────


class VoicePreferences(BaseModel):
    """Voice/audio related preferences.

    Attributes:
        radio_effects: Whether to apply radio effects to TTS output.
        language: Preferred language code (e.g. ``en``, ``es``).
        ptt_mode: Push-to-talk mode — ``hold`` or ``toggle``.
    """

    radio_effects: bool = True
    language: str = "en"
    ptt_mode: str = "hold"


class DisplayPreferences(BaseModel):
    """UI display preferences.

    Attributes:
        animations: Whether UI animations are enabled.
        theme: Colour theme — ``dark`` or ``light``.
        compact_mode: Whether the sidebar/panels use compact layout.
    """

    animations: bool = True
    theme: str = "dark"
    compact_mode: bool = False


class PreferencesData(BaseModel):
    """Full typed preference structure (used as a reference/default).

    The JSONB column allows arbitrary keys, but this model documents the
    canonical shape and provides sensible defaults.

    Attributes:
        keyboard_shortcuts: Map of action name → key binding.
        voice: Voice and audio preferences.
        display: Display and theme preferences.
    """

    keyboard_shortcuts: dict[str, str] = Field(default_factory=lambda: {"push_to_talk": "KeyB"})
    voice: VoicePreferences = Field(default_factory=VoicePreferences)
    display: DisplayPreferences = Field(default_factory=DisplayPreferences)


# ── API request / response schemas ─────────────────────────────────


class UserPreferencesRead(BaseModel):
    """Schema returned when reading user preferences.

    Attributes:
        id: The preferences row UUID.
        user_id: The owning user's UUID.
        preferences: The raw JSONB preferences dictionary.
        created_at: Row creation timestamp.
        updated_at: Row last-update timestamp.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    preferences: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserPreferencesUpdate(BaseModel):
    """Schema for updating user preferences (partial / deep merge).

    Attributes:
        preferences: A dictionary that will be deep-merged into the
            existing preferences document.
    """

    preferences: dict[str, Any]


class SectionUpdate(BaseModel):
    """Schema for updating a single preference section.

    Attributes:
        data: The section payload to deep-merge.
    """

    data: dict[str, Any]
