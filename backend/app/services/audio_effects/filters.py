"""Audio effects for radio simulation using scipy."""

import logging

import numpy as np
from scipy import signal

from app.config import get_settings

logger = logging.getLogger(__name__)


class RadioEffectsProcessor:
    """Apply radio effects to audio for realistic ATC simulation."""

    def __init__(self) -> None:
        """Initialize the effects processor."""
        self.settings = get_settings()

    def apply_radio_effects(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
    ) -> np.ndarray:
        """Apply radio effects to audio.

        Args:
            audio_data: Input audio as numpy array
            sample_rate: Sample rate of the audio

        Returns:
            Processed audio with radio effects
        """
        if not self.settings.enable_radio_effects:
            return audio_data

        try:
            # 1. Apply band-pass filter (300Hz - 3400Hz for radio effect)
            audio_data = self._apply_bandpass_filter(audio_data, sample_rate)

            # 2. Add background noise
            audio_data = self._add_noise(audio_data)

            # 3. Add static/crackle
            audio_data = self._add_static(audio_data)

            # 4. Normalize
            audio_data = self._normalize(audio_data)

            return audio_data

        except Exception as e:
            logger.error(f"Error applying radio effects: {e}")
            return audio_data

    def _apply_bandpass_filter(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
    ) -> np.ndarray:
        """Apply band-pass filter to simulate radio frequency response.

        Args:
            audio_data: Input audio
            sample_rate: Sample rate

        Returns:
            Filtered audio
        """
        # Radio frequency range: 300Hz - 3400Hz
        lowcut = 300.0
        highcut = 3400.0

        # Design Butterworth band-pass filter
        nyquist = sample_rate / 2
        low = lowcut / nyquist
        high = highcut / nyquist

        b, a = signal.butter(4, [low, high], btype="band")
        filtered = signal.filtfilt(b, a, audio_data)

        return filtered

    def _add_noise(self, audio_data: np.ndarray) -> np.ndarray:
        """Add background noise to audio.

        Args:
            audio_data: Input audio

        Returns:
            Audio with added noise
        """
        noise_level = self.settings.noise_level
        noise = np.random.normal(0, noise_level, audio_data.shape)
        return audio_data + noise

    def _add_static(self, audio_data: np.ndarray) -> np.ndarray:
        """Add random static/crackle to audio.

        Args:
            audio_data: Input audio

        Returns:
            Audio with added static
        """
        static_level = self.settings.static_level

        # Create random static bursts
        static_probability = 0.001  # 0.1% chance per sample
        static_mask = np.random.random(audio_data.shape) < static_probability
        static = static_mask * np.random.uniform(-static_level, static_level, audio_data.shape)

        return audio_data + static

    def _normalize(self, audio_data: np.ndarray) -> np.ndarray:
        """Normalize audio to prevent clipping.

        Args:
            audio_data: Input audio

        Returns:
            Normalized audio
        """
        max_val = np.abs(audio_data).max()
        if max_val > 0:
            return audio_data * (0.95 / max_val)
        return audio_data

    def add_transmission_clicks(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
    ) -> np.ndarray:
        """Add transmission start/end clicks.

        Args:
            audio_data: Input audio
            sample_rate: Sample rate

        Returns:
            Audio with transmission clicks
        """
        # Add a small click at the start
        click_duration = int(0.01 * sample_rate)  # 10ms click
        start_click = np.random.uniform(-0.1, 0.1, click_duration)

        # Add click to beginning
        audio_with_click = np.concatenate([start_click, audio_data])

        return audio_with_click
