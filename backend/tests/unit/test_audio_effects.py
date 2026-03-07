"""Tests for radio effects audio filters."""
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.audio_effects.filters import RadioEffectsProcessor


SAMPLE_RATE = 16000


def _make_sine(duration: float = 0.5, freq: float = 440.0) -> np.ndarray:
    """Generate a sine wave for use as test audio."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration))
    return np.sin(2 * np.pi * freq * t).astype(np.float64)


def _mock_settings(enable_radio_effects: bool = True) -> MagicMock:
    settings = MagicMock()
    settings.enable_radio_effects = enable_radio_effects
    settings.noise_level = 0.02
    settings.static_level = 0.01
    return settings


@pytest.fixture
def processor() -> RadioEffectsProcessor:
    """RadioEffectsProcessor with radio effects enabled and mocked settings."""
    with patch(
        "app.services.audio_effects.filters.get_settings",
        return_value=_mock_settings(enable_radio_effects=True),
    ):
        return RadioEffectsProcessor()


@pytest.fixture
def processor_disabled() -> RadioEffectsProcessor:
    """RadioEffectsProcessor with radio effects disabled."""
    with patch(
        "app.services.audio_effects.filters.get_settings",
        return_value=_mock_settings(enable_radio_effects=False),
    ):
        return RadioEffectsProcessor()


def test_apply_radio_effects_returns_ndarray(processor: RadioEffectsProcessor) -> None:
    """apply_radio_effects should return a numpy array."""
    audio = _make_sine()
    result = processor.apply_radio_effects(audio, sample_rate=SAMPLE_RATE)
    assert isinstance(result, np.ndarray)


def test_apply_radio_effects_preserves_approximate_length(
    processor: RadioEffectsProcessor,
) -> None:
    """apply_radio_effects should not drastically change the number of samples."""
    audio = _make_sine()
    result = processor.apply_radio_effects(audio, sample_rate=SAMPLE_RATE)
    assert len(result) == len(audio)


def test_apply_radio_effects_disabled_returns_input_unchanged(
    processor_disabled: RadioEffectsProcessor,
) -> None:
    """When effects are disabled, apply_radio_effects should return the original array."""
    audio = _make_sine()
    result = processor_disabled.apply_radio_effects(audio, sample_rate=SAMPLE_RATE)
    np.testing.assert_array_equal(result, audio)


def test_normalize_scales_peak_to_095(processor: RadioEffectsProcessor) -> None:
    """_normalize should scale audio so its peak amplitude is exactly 0.95."""
    audio = np.array([0.0, 0.5, 1.0, -0.5, 0.25])
    result = processor._normalize(audio)
    assert np.abs(result).max() == pytest.approx(0.95)


def test_normalize_all_zeros_unchanged(processor: RadioEffectsProcessor) -> None:
    """_normalize should return a silent signal unchanged without division by zero."""
    silent = np.zeros(256)
    result = processor._normalize(silent)
    np.testing.assert_array_equal(result, silent)


def test_normalize_scales_proportionally(processor: RadioEffectsProcessor) -> None:
    """_normalize should preserve the relative shape of the waveform."""
    audio = np.array([1.0, 0.5, -0.5, -1.0])
    result = processor._normalize(audio)
    # Ratios between samples should be maintained
    assert result[0] == pytest.approx(-result[3])
    assert result[1] == pytest.approx(-result[2])


def test_bandpass_filter_preserves_shape(processor: RadioEffectsProcessor) -> None:
    """_apply_bandpass_filter should not change the number of samples."""
    audio = _make_sine()
    result = processor._apply_bandpass_filter(audio, sample_rate=SAMPLE_RATE)
    assert result.shape == audio.shape


def test_add_transmission_clicks_increases_length(
    processor: RadioEffectsProcessor,
) -> None:
    """add_transmission_clicks should prepend a 10 ms click to the audio."""
    audio = _make_sine()
    result = processor.add_transmission_clicks(audio, sample_rate=SAMPLE_RATE)
    expected_click_samples = int(0.01 * SAMPLE_RATE)  # 160 samples at 16 kHz
    assert len(result) == len(audio) + expected_click_samples


def test_add_transmission_clicks_returns_ndarray(
    processor: RadioEffectsProcessor,
) -> None:
    """add_transmission_clicks should return a numpy array."""
    audio = _make_sine()
    result = processor.add_transmission_clicks(audio, sample_rate=SAMPLE_RATE)
    assert isinstance(result, np.ndarray)


def test_add_noise_changes_signal(processor: RadioEffectsProcessor) -> None:
    """_add_noise should alter the signal values."""
    audio = np.zeros(1000)
    result = processor._add_noise(audio)
    # With non-zero noise_level, at least some samples should differ
    assert not np.array_equal(result, audio)
