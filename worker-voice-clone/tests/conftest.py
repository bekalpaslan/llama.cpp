"""Shared test fixtures for worker-voice-clone test suite."""

import io
from unittest.mock import MagicMock

import numpy as np
import pytest
import soundfile as sf


@pytest.fixture
def sample_audio_bytes():
    """
    Factory fixture: generate sine-wave WAV bytes.

    Args:
        duration: Duration in seconds (default 10).
        sample_rate: Sample rate in Hz (default 22050).
        channels: Number of audio channels (default 1).
        frequency: Sine wave frequency in Hz (default 440).
        noise_level: Additive Gaussian noise std dev (default 0.0).

    Returns:
        WAV file content as bytes.
    """

    def _factory(
        duration=10.0,
        sample_rate=22050,
        channels=1,
        frequency=440.0,
        noise_level=0.0,
    ):
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        signal = 0.5 * np.sin(2 * np.pi * frequency * t)

        if noise_level > 0:
            noise = np.random.default_rng(42).normal(0, noise_level, len(t))
            signal = signal + noise

        if channels > 1:
            signal = np.column_stack([signal] * channels)

        buf = io.BytesIO()
        sf.write(buf, signal, sample_rate, format="wav")
        buf.seek(0)
        return buf.read()

    return _factory


@pytest.fixture
def tmp_audio_file(tmp_path, sample_audio_bytes):
    """
    Write sample audio bytes to a temporary file and return the path.

    Returns:
        pathlib.Path to the WAV file.
    """

    def _factory(**kwargs):
        audio_bytes = sample_audio_bytes(**kwargs)
        path = tmp_path / "reference.wav"
        path.write_bytes(audio_bytes)
        return str(path)

    return _factory


@pytest.fixture
def mock_chatterbox_model():
    """
    Mock Chatterbox model with generate() returning a torch tensor.

    Returns a MagicMock with:
    - generate() returning a tensor of shape [1, 24000*3] (3 seconds at 24kHz)
    - sr attribute = 24000
    """
    try:
        import torch
    except ImportError:
        pytest.skip("torch not available")

    model = MagicMock()
    model.sr = 24000
    # 3 seconds of audio at 24kHz
    model.generate.return_value = torch.randn(1, 24000 * 3)
    return model
