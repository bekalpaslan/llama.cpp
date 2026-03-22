"""Tests for audio input/output utilities."""

import base64
import os
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from audio_utils import resolve_audio_input, cleanup_audio, encode_audio_output


class TestResolveAudioInputURL:
    """Tests for URL-based audio input resolution."""

    def test_resolve_url_success(self, sample_audio_bytes):
        """resolve_audio_input with audio_url downloads file and returns path to existing temp file."""
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [sample_audio_bytes]
        mock_response.headers = {"content-type": "audio/wav"}
        mock_response.raise_for_status = MagicMock()

        with patch("audio_utils.requests.get", return_value=mock_response) as mock_get, \
             patch("audio_utils.socket.getaddrinfo", return_value=[
                 (2, 1, 6, "", ("93.184.216.34", 443))
             ]):
            result = resolve_audio_input({"audio_url": "https://example.com/test.wav"})

        try:
            assert os.path.isfile(result)
            with open(result, "rb") as f:
                content = f.read()
            assert len(content) > 0
        finally:
            if os.path.exists(result):
                os.unlink(result)

    def test_url_extension_detection_mp3(self, sample_audio_bytes):
        """URL ending in .mp3 produces temp file with .mp3 suffix."""
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [sample_audio_bytes]
        mock_response.headers = {"content-type": "audio/mpeg"}
        mock_response.raise_for_status = MagicMock()

        with patch("audio_utils.requests.get", return_value=mock_response), \
             patch("audio_utils.socket.getaddrinfo", return_value=[
                 (2, 1, 6, "", ("93.184.216.34", 443))
             ]):
            result = resolve_audio_input({"audio_url": "https://example.com/file.mp3"})

        try:
            assert result.endswith(".mp3")
        finally:
            if os.path.exists(result):
                os.unlink(result)

    def test_url_extension_detection_wav(self, sample_audio_bytes):
        """URL ending in .wav produces temp file with .wav suffix."""
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [sample_audio_bytes]
        mock_response.headers = {"content-type": "audio/wav"}
        mock_response.raise_for_status = MagicMock()

        with patch("audio_utils.requests.get", return_value=mock_response), \
             patch("audio_utils.socket.getaddrinfo", return_value=[
                 (2, 1, 6, "", ("93.184.216.34", 443))
             ]):
            result = resolve_audio_input({"audio_url": "https://example.com/speech.wav"})

        try:
            assert result.endswith(".wav")
        finally:
            if os.path.exists(result):
                os.unlink(result)


class TestResolveAudioInputBase64:
    """Tests for base64-based audio input resolution."""

    def test_resolve_base64_success(self, sample_audio_bytes):
        """resolve_audio_input with audio_base64 decodes and returns path to existing temp file."""
        encoded = base64.b64encode(sample_audio_bytes).decode("utf-8")

        result = resolve_audio_input({"audio_base64": encoded})

        try:
            assert os.path.isfile(result)
            with open(result, "rb") as f:
                content = f.read()
            assert content == sample_audio_bytes
        finally:
            if os.path.exists(result):
                os.unlink(result)


class TestResolveAudioInputValidation:
    """Tests for input validation and error handling."""

    def test_resolve_missing_input(self):
        """resolve_audio_input({}) raises ValueError."""
        with pytest.raises(ValueError, match="audio_url.*audio_base64"):
            resolve_audio_input({})

    def test_unsupported_scheme(self):
        """resolve_audio_input with ftp:// raises ValueError about scheme."""
        with pytest.raises(ValueError, match="scheme"):
            resolve_audio_input({"audio_url": "ftp://example.com/file.wav"})


class TestSSRFPrevention:
    """Tests for SSRF (Server-Side Request Forgery) prevention."""

    def test_ssrf_private_ip(self):
        """resolve_audio_input rejects URLs resolving to private IPs."""
        with patch("audio_utils.socket.getaddrinfo", return_value=[
            (2, 1, 6, "", ("192.168.1.1", 80))
        ]):
            with pytest.raises(ValueError, match="(?i)(private|internal)"):
                resolve_audio_input({"audio_url": "http://192.168.1.1/audio.wav"})

    def test_ssrf_loopback(self):
        """resolve_audio_input rejects URLs resolving to loopback."""
        with patch("audio_utils.socket.getaddrinfo", return_value=[
            (2, 1, 6, "", ("127.0.0.1", 80))
        ]):
            with pytest.raises(ValueError):
                resolve_audio_input({"audio_url": "http://localhost/audio.wav"})

    def test_ssrf_link_local(self):
        """resolve_audio_input rejects URLs resolving to link-local IPs."""
        with patch("audio_utils.socket.getaddrinfo", return_value=[
            (2, 1, 6, "", ("169.254.169.254", 80))
        ]):
            with pytest.raises(ValueError):
                resolve_audio_input({"audio_url": "http://169.254.169.254/metadata"})


class TestCleanupAudio:
    """Tests for cleanup_audio utility."""

    def test_cleanup_removes_file(self, tmp_path):
        """cleanup_audio(path) removes the file at path."""
        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"fake audio")
        path = str(test_file)

        assert os.path.exists(path)
        cleanup_audio(path)
        assert not os.path.exists(path)

    def test_cleanup_missing_file(self):
        """cleanup_audio on non-existent path does not raise."""
        cleanup_audio("/nonexistent/path/to/file.wav")


class TestEncodeAudioOutput:
    """Tests for encode_audio_output utility."""

    def test_encode_output_wav(self):
        """encode_audio_output returns dict with valid base64 and metadata."""
        sample_rate = 16000
        duration = 1.0
        num_samples = int(sample_rate * duration)
        audio_array = np.zeros(num_samples, dtype=np.float32)

        result = encode_audio_output(audio_array, sample_rate, "wav")

        assert isinstance(result, dict)
        assert "audio_base64" in result
        assert result["format"] == "wav"
        assert result["sample_rate"] == sample_rate
        assert abs(result["duration_seconds"] - duration) < 0.01

        # Verify base64 is valid
        decoded = base64.b64decode(result["audio_base64"])
        assert len(decoded) > 0
