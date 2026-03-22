"""Tests for handler.py - single audio, batch processing, cleanup, and CUDA cache."""

from unittest.mock import MagicMock, patch, call

import pytest


@pytest.fixture
def mock_transcribe_result():
    """A complete transcription result dict as returned by transcribe_audio."""
    return {
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 3.52,
                "text": " Hello, how are you today?",
                "avg_logprob": -0.2341,
                "no_speech_prob": 0.0123,
                "words": [
                    {"start": 0.0, "end": 0.42, "word": " Hello,", "probability": 0.95},
                ],
            },
        ],
        "language": "en",
        "language_probability": 0.98,
        "duration": 10.5,
        "duration_after_vad": 9.8,
    }


class TestHandlerSingleAudio:
    """Tests for single audio file processing."""

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_handler_single_audio_url(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
        mock_transcribe_result,
    ):
        """handler({input: {audio_url: ...}}) calls resolve, transcribe, returns result."""
        mock_resolve.return_value = "/tmp/audio.wav"
        mock_transcribe.return_value = mock_transcribe_result
        mock_torch.cuda.is_available.return_value = True

        from handler import handler

        job = {"input": {"audio_url": "https://example.com/audio.wav"}}
        result = handler(job)

        mock_resolve.assert_called_once()
        mock_transcribe.assert_called_once()
        assert "segments" in result
        assert result["language"] == "en"

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_handler_single_audio_base64(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
        mock_transcribe_result,
    ):
        """handler({input: {audio_base64: ...}}) works the same way."""
        mock_resolve.return_value = "/tmp/audio.wav"
        mock_transcribe.return_value = mock_transcribe_result
        mock_torch.cuda.is_available.return_value = True

        from handler import handler

        job = {"input": {"audio_base64": "UklGR..."}}
        result = handler(job)

        mock_resolve.assert_called_once()
        mock_transcribe.assert_called_once()
        assert "segments" in result

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_handler_output_format_text(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
        mock_transcribe_result,
    ):
        """output_format='text' adds 'text' key to result."""
        mock_resolve.return_value = "/tmp/audio.wav"
        mock_transcribe.return_value = mock_transcribe_result
        mock_torch.cuda.is_available.return_value = True

        from handler import handler

        job = {"input": {"audio_url": "https://example.com/audio.wav", "output_format": "text"}}
        result = handler(job)

        assert "text" in result

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_handler_output_format_srt(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
        mock_transcribe_result,
    ):
        """output_format='srt' adds 'srt' key to result."""
        mock_resolve.return_value = "/tmp/audio.wav"
        mock_transcribe.return_value = mock_transcribe_result
        mock_torch.cuda.is_available.return_value = True

        from handler import handler

        job = {"input": {"audio_url": "https://example.com/audio.wav", "output_format": "srt"}}
        result = handler(job)

        assert "srt" in result

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_handler_output_format_vtt(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
        mock_transcribe_result,
    ):
        """output_format='vtt' adds 'vtt' key to result."""
        mock_resolve.return_value = "/tmp/audio.wav"
        mock_transcribe.return_value = mock_transcribe_result
        mock_torch.cuda.is_available.return_value = True

        from handler import handler

        job = {"input": {"audio_url": "https://example.com/audio.wav", "output_format": "vtt"}}
        result = handler(job)

        assert "vtt" in result

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_handler_missing_input(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
    ):
        """Returns error dict when no audio input provided."""
        mock_resolve.side_effect = ValueError("Provide 'audio_url' or 'audio_base64' in the input.")
        mock_torch.cuda.is_available.return_value = True

        from handler import handler

        job = {"input": {}}
        result = handler(job)

        assert "error" in result

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_handler_cleanup_on_error(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
    ):
        """cleanup_audio called even when transcription raises."""
        mock_resolve.return_value = "/tmp/audio.wav"
        mock_transcribe.side_effect = RuntimeError("Transcription failed")
        mock_torch.cuda.is_available.return_value = True

        from handler import handler

        job = {"input": {"audio_url": "https://example.com/audio.wav"}}
        result = handler(job)

        mock_cleanup.assert_called_with("/tmp/audio.wav")
        assert "error" in result

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_handler_cuda_cache_clear(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
        mock_transcribe_result,
    ):
        """torch.cuda.empty_cache called after request."""
        mock_resolve.return_value = "/tmp/audio.wav"
        mock_transcribe.return_value = mock_transcribe_result
        mock_torch.cuda.is_available.return_value = True

        from handler import handler

        job = {"input": {"audio_url": "https://example.com/audio.wav"}}
        handler(job)

        mock_torch.cuda.empty_cache.assert_called()


class TestHandlerBatch:
    """Tests for batch audio processing."""

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_batch_multiple_urls(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
        mock_transcribe_result,
    ):
        """handler({input: {audio_urls: [...]}}) returns {results: [...]}."""
        mock_resolve.side_effect = ["/tmp/audio1.wav", "/tmp/audio2.wav"]
        mock_transcribe.return_value = mock_transcribe_result
        mock_torch.cuda.is_available.return_value = True

        from handler import handler

        job = {
            "input": {
                "audio_urls": [
                    "https://example.com/audio1.wav",
                    "https://example.com/audio2.wav",
                ],
            }
        }
        result = handler(job)

        assert "results" in result
        assert len(result["results"]) == 2

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_batch_shared_params(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
        mock_transcribe_result,
    ):
        """language and output_format from job_input apply to all batch items."""
        mock_resolve.side_effect = ["/tmp/a1.wav", "/tmp/a2.wav"]
        mock_transcribe.return_value = mock_transcribe_result
        mock_torch.cuda.is_available.return_value = True

        from handler import handler

        job = {
            "input": {
                "audio_urls": ["https://example.com/a1.wav", "https://example.com/a2.wav"],
                "language": "en",
                "output_format": "text",
            }
        }
        result = handler(job)

        assert "results" in result
        # Each result should have 'text' key from output_format
        for r in result["results"]:
            assert "text" in r

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_batch_empty_list(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
    ):
        """Returns {results: []} for empty audio_urls list."""
        mock_torch.cuda.is_available.return_value = True

        from handler import handler

        job = {"input": {"audio_urls": []}}
        result = handler(job)

        assert result == {"results": []}

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_batch_single_url(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
        mock_transcribe_result,
    ):
        """Batch with one URL returns {results: [single_result]}."""
        mock_resolve.return_value = "/tmp/audio.wav"
        mock_transcribe.return_value = mock_transcribe_result
        mock_torch.cuda.is_available.return_value = True

        from handler import handler

        job = {"input": {"audio_urls": ["https://example.com/audio.wav"]}}
        result = handler(job)

        assert "results" in result
        assert len(result["results"]) == 1
