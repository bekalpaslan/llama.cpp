"""
Tests for handler.py -- the RunPod serverless handler for voice cloning.

Tests cover:
- Input validation (missing text, missing reference audio)
- Reference audio validation integration
- Success paths (URL and base64 inputs)
- Custom parameter forwarding
- Cleanup on success and error
- VRAM cleanup (torch.cuda.empty_cache)
- Exception handling
- runpod.serverless.start guard
"""

import importlib
import sys
import types
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
import torch


# ---------------------------------------------------------------------------
# Module-level patching: handler.py calls load_model() at import time.
# We must patch voice_clone.load_model before importing handler.
# ---------------------------------------------------------------------------
_mock_model = MagicMock()
_mock_model.sr = 24000
_mock_model.generate.return_value = torch.randn(1, 24000 * 3)

# Patch load_model before handler import
with patch("voice_clone.load_model", return_value=_mock_model):
    # Also need to ensure handler can be imported (it may re-import voice_clone)
    if "handler" in sys.modules:
        del sys.modules["handler"]
    import handler as handler_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def valid_url_input():
    """Valid job input with reference_audio_url."""
    return {
        "input": {
            "text": "Hello world, this is a test.",
            "reference_audio_url": "https://example.com/voice.wav",
        }
    }


@pytest.fixture
def valid_base64_input():
    """Valid job input with reference_audio_base64."""
    return {
        "input": {
            "text": "Hello world, this is a test.",
            "reference_audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=",
        }
    }


@pytest.fixture
def mock_dependencies():
    """Patch all external dependencies for handler tests."""
    mock_wav = torch.randn(1, 24000 * 3)
    mock_quality = {
        "duration_seconds": 10.0,
        "sample_rate": 22050,
        "snr_db": 30.0,
        "quality": "good",
    }

    with (
        patch.object(handler_module, "resolve_audio_input", return_value="/tmp/ref.wav") as mock_resolve,
        patch.object(handler_module, "validate_reference_audio", return_value=mock_quality) as mock_validate,
        patch.object(handler_module, "clone_voice", return_value=(mock_wav, 24000)) as mock_clone,
        patch.object(handler_module, "encode_output", return_value=("base64encodedaudio", "wav")) as mock_encode,
        patch.object(handler_module, "cleanup_audio") as mock_cleanup,
        patch("torch.cuda.is_available", return_value=True),
        patch("torch.cuda.empty_cache") as mock_empty_cache,
    ):
        yield {
            "resolve_audio_input": mock_resolve,
            "validate_reference_audio": mock_validate,
            "clone_voice": mock_clone,
            "encode_output": mock_encode,
            "cleanup_audio": mock_cleanup,
            "empty_cache": mock_empty_cache,
            "wav": mock_wav,
            "quality": mock_quality,
        }


# ---------------------------------------------------------------------------
# Tests: Input validation
# ---------------------------------------------------------------------------
class TestHandlerValidation:
    """Tests for input validation in handler()."""

    def test_handler_missing_text(self, mock_dependencies):
        """Handler returns error when 'text' is missing."""
        job = {"input": {"reference_audio_url": "https://example.com/voice.wav"}}
        result = handler_module.handler(job)
        assert "error" in result
        assert "text" in result["error"].lower()

    def test_handler_empty_text(self, mock_dependencies):
        """Handler returns error when 'text' is empty string."""
        job = {"input": {"text": "", "reference_audio_url": "https://example.com/voice.wav"}}
        result = handler_module.handler(job)
        assert "error" in result
        assert "text" in result["error"].lower()

    def test_handler_whitespace_text(self, mock_dependencies):
        """Handler returns error when 'text' is only whitespace."""
        job = {"input": {"text": "   ", "reference_audio_url": "https://example.com/voice.wav"}}
        result = handler_module.handler(job)
        assert "error" in result
        assert "text" in result["error"].lower()

    def test_handler_missing_reference_audio(self, mock_dependencies):
        """Handler returns error when neither reference_audio_url nor reference_audio_base64 provided."""
        job = {"input": {"text": "Hello"}}
        result = handler_module.handler(job)
        assert "error" in result
        assert "reference_audio" in result["error"].lower() or "audio" in result["error"].lower()

    def test_handler_validation_failure(self, mock_dependencies):
        """When validate_reference_audio raises ValueError, handler returns error without calling clone_voice."""
        mock_dependencies["validate_reference_audio"].side_effect = ValueError(
            "Reference audio too short (2.0s). Minimum 5.0s required."
        )
        job = {
            "input": {
                "text": "Hello",
                "reference_audio_url": "https://example.com/voice.wav",
            }
        }
        result = handler_module.handler(job)
        assert "error" in result
        assert "too short" in result["error"]
        mock_dependencies["clone_voice"].assert_not_called()


# ---------------------------------------------------------------------------
# Tests: Success paths
# ---------------------------------------------------------------------------
class TestHandlerSuccess:
    """Tests for successful handler responses."""

    def test_handler_success_url(self, valid_url_input, mock_dependencies):
        """With valid reference_audio_url + text, returns full success response."""
        result = handler_module.handler(valid_url_input)

        assert "error" not in result
        assert result["audio_base64"] == "base64encodedaudio"
        assert result["format"] == "wav"
        assert result["sample_rate"] == 48000
        assert "duration_seconds" in result
        assert result["reference_quality"] == mock_dependencies["quality"]
        assert result["model_variant"] == handler_module.MODEL_VARIANT
        assert result["language"] == "en"

    def test_handler_success_base64(self, valid_base64_input, mock_dependencies):
        """With valid reference_audio_base64 + text, returns same success response."""
        result = handler_module.handler(valid_base64_input)

        assert "error" not in result
        assert result["audio_base64"] == "base64encodedaudio"
        assert result["format"] == "wav"
        assert result["sample_rate"] == 48000

    def test_handler_maps_url_to_audio_url(self, valid_url_input, mock_dependencies):
        """Handler maps reference_audio_url to audio_url for resolve_audio_input."""
        handler_module.handler(valid_url_input)
        call_args = mock_dependencies["resolve_audio_input"].call_args[0][0]
        assert "audio_url" in call_args
        assert call_args["audio_url"] == "https://example.com/voice.wav"

    def test_handler_maps_base64_to_audio_base64(self, valid_base64_input, mock_dependencies):
        """Handler maps reference_audio_base64 to audio_base64 for resolve_audio_input."""
        handler_module.handler(valid_base64_input)
        call_args = mock_dependencies["resolve_audio_input"].call_args[0][0]
        assert "audio_base64" in call_args

    def test_handler_custom_params(self, mock_dependencies):
        """Custom language, output_format, exaggeration, cfg_weight forwarded correctly."""
        job = {
            "input": {
                "text": "Bonjour le monde",
                "reference_audio_url": "https://example.com/voice.wav",
                "language": "fr",
                "output_format": "mp3",
                "exaggeration": 0.8,
                "cfg_weight": 0.3,
            }
        }
        result = handler_module.handler(job)

        # Verify clone_voice received custom params
        clone_call = mock_dependencies["clone_voice"].call_args
        assert clone_call.kwargs["language_id"] == "fr"
        assert clone_call.kwargs["exaggeration"] == 0.8
        assert clone_call.kwargs["cfg_weight"] == 0.3

        # Verify encode_output received mp3 format
        encode_call = mock_dependencies["encode_output"].call_args
        assert encode_call[0][2] == "mp3" or encode_call.kwargs.get("output_format") == "mp3"

        # Verify response includes the language
        assert result["language"] == "fr"


# ---------------------------------------------------------------------------
# Tests: Cleanup and VRAM
# ---------------------------------------------------------------------------
class TestHandlerCleanup:
    """Tests for cleanup behavior in handler()."""

    def test_handler_cleanup_on_success(self, valid_url_input, mock_dependencies):
        """cleanup_audio called after successful request."""
        handler_module.handler(valid_url_input)
        mock_dependencies["cleanup_audio"].assert_called_once_with("/tmp/ref.wav")

    def test_handler_cleanup_on_error(self, mock_dependencies):
        """cleanup_audio called even when clone_voice raises exception."""
        mock_dependencies["clone_voice"].side_effect = RuntimeError("GPU OOM")
        job = {
            "input": {
                "text": "Hello",
                "reference_audio_url": "https://example.com/voice.wav",
            }
        }
        handler_module.handler(job)
        mock_dependencies["cleanup_audio"].assert_called_once_with("/tmp/ref.wav")

    def test_handler_cuda_empty_cache(self, valid_url_input, mock_dependencies):
        """torch.cuda.empty_cache called in finally block."""
        handler_module.handler(valid_url_input)
        mock_dependencies["empty_cache"].assert_called_once()

    def test_handler_cuda_empty_cache_on_error(self, mock_dependencies):
        """torch.cuda.empty_cache called even when exception occurs."""
        mock_dependencies["clone_voice"].side_effect = RuntimeError("GPU OOM")
        job = {
            "input": {
                "text": "Hello",
                "reference_audio_url": "https://example.com/voice.wav",
            }
        }
        handler_module.handler(job)
        mock_dependencies["empty_cache"].assert_called_once()


# ---------------------------------------------------------------------------
# Tests: Error handling
# ---------------------------------------------------------------------------
class TestHandlerErrors:
    """Tests for error handling in handler()."""

    def test_handler_exception_returns_error(self, mock_dependencies):
        """Unexpected exception returns {'error': 'Voice cloning failed: ...'}."""
        mock_dependencies["clone_voice"].side_effect = RuntimeError("Unexpected CUDA error")
        job = {
            "input": {
                "text": "Hello",
                "reference_audio_url": "https://example.com/voice.wav",
            }
        }
        result = handler_module.handler(job)
        assert "error" in result
        assert "Voice cloning failed:" in result["error"]
        assert "Unexpected CUDA error" in result["error"]


# ---------------------------------------------------------------------------
# Tests: Module guard
# ---------------------------------------------------------------------------
class TestModuleGuard:
    """Tests for runpod.serverless.start guard."""

    def test_runpod_start_guarded(self):
        """runpod.serverless.start only called under __name__ == '__main__'."""
        # When imported as a module, __name__ is "handler", not "__main__"
        # So runpod.serverless.start should NOT have been called during import
        # We verify by checking the handler module has the if __name__ guard
        import inspect
        source = inspect.getsource(handler_module)
        assert 'if __name__ == "__main__"' in source or "if __name__ == '__main__'" in source
