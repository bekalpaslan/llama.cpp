"""Shared test fixtures for worker-template test suite."""

import struct
import tempfile
import shutil
from collections import namedtuple
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def tmp_model_dir(tmp_path):
    """Create a temporary directory for model storage, cleaned up after test."""
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    yield str(model_dir)


HfHubMocks = namedtuple("HfHubMocks", ["hf_hub_download", "snapshot_download"])


@pytest.fixture
def mock_hf_hub():
    """Patch huggingface_hub download functions with MagicMock objects."""
    with patch("download_model.hf_hub_download") as mock_single, \
         patch("download_model.snapshot_download") as mock_snapshot:
        yield HfHubMocks(hf_hub_download=mock_single, snapshot_download=mock_snapshot)


@pytest.fixture
def sample_audio_bytes():
    """Return minimal valid WAV file bytes (16kHz mono 16-bit PCM, 100 samples of silence)."""
    sample_rate = 16000
    num_channels = 1
    bits_per_sample = 16
    num_samples = 100
    bytes_per_sample = bits_per_sample // 8
    data_size = num_samples * num_channels * bytes_per_sample
    fmt_chunk_size = 16

    # RIFF header
    header = struct.pack(
        "<4sI4s",
        b"RIFF",
        36 + data_size,  # file size - 8
        b"WAVE",
    )

    # fmt sub-chunk
    fmt_chunk = struct.pack(
        "<4sIHHIIHH",
        b"fmt ",
        fmt_chunk_size,
        1,  # PCM format
        num_channels,
        sample_rate,
        sample_rate * num_channels * bytes_per_sample,  # byte rate
        num_channels * bytes_per_sample,  # block align
        bits_per_sample,
    )

    # data sub-chunk (silence)
    data_chunk = struct.pack("<4sI", b"data", data_size)
    data_chunk += b"\x00" * data_size

    return header + fmt_chunk + data_chunk
