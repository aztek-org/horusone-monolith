"""Unit tests for the user-preferences schemas."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.user_preferences import (
    DisplayPreferences,
    PreferencesData,
    SectionUpdate,
    UserPreferencesRead,
    UserPreferencesUpdate,
    VoicePreferences,
)


class TestVoicePreferences:
    def test_defaults(self) -> None:
        prefs = VoicePreferences()
        assert prefs.radio_effects is True
        assert prefs.language == "en"
        assert prefs.ptt_mode == "hold"

    def test_accepts_overrides(self) -> None:
        prefs = VoicePreferences(radio_effects=False, language="es", ptt_mode="toggle")
        assert prefs.radio_effects is False
        assert prefs.ptt_mode == "toggle"


class TestDisplayPreferences:
    def test_defaults(self) -> None:
        prefs = DisplayPreferences()
        assert prefs.animations is True
        assert prefs.theme == "dark"
        assert prefs.compact_mode is False


class TestPreferencesData:
    def test_nested_defaults(self) -> None:
        data = PreferencesData()

        assert data.keyboard_shortcuts == {"push_to_talk": "KeyB"}
        assert isinstance(data.voice, VoicePreferences)
        assert isinstance(data.display, DisplayPreferences)

    def test_serialises_nested_models_to_dicts(self) -> None:
        dumped = PreferencesData().model_dump()

        assert dumped["voice"]["ptt_mode"] == "hold"
        assert dumped["display"]["theme"] == "dark"

    def test_accepts_partial_nested_override(self) -> None:
        data = PreferencesData(voice={"language": "es"})

        assert data.voice.language == "es"
        assert data.voice.radio_effects is True


class TestUserPreferencesRead:
    def test_requires_all_fields(self) -> None:
        with pytest.raises(ValidationError):
            UserPreferencesRead(preferences={})

    def test_accepts_full_row(self) -> None:
        row = UserPreferencesRead(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            preferences={"voice": {"language": "en"}},
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-02T00:00:00",
        )
        assert row.preferences == {"voice": {"language": "en"}}


class TestUpdateSchemas:
    def test_user_preferences_update_requires_preferences(self) -> None:
        with pytest.raises(ValidationError):
            UserPreferencesUpdate()

    def test_section_update_wraps_data(self) -> None:
        update = SectionUpdate(data={"theme": "light"})
        assert update.data == {"theme": "light"}

    def test_section_update_requires_data(self) -> None:
        with pytest.raises(ValidationError):
            SectionUpdate()
