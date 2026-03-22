"""Tests for diarization functionality in handler.py."""

from unittest.mock import MagicMock, patch

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
            {
                "id": 1,
                "start": 3.8,
                "end": 7.24,
                "text": " I am doing great, thank you.",
                "avg_logprob": -0.1892,
                "no_speech_prob": 0.0087,
                "words": [
                    {"start": 3.8, "end": 4.0, "word": " I", "probability": 0.99},
                ],
            },
        ],
        "language": "en",
        "language_probability": 0.98,
        "duration": 10.5,
        "duration_after_vad": 9.8,
    }


@pytest.fixture
def mock_diarize_pipeline():
    """Mock DiarizationPipeline that returns speaker segments."""
    pipeline = MagicMock()
    # The pipeline returns a DataFrame-like object with speaker labels
    pipeline.return_value = MagicMock()
    return pipeline


class TestDiarization:
    """Tests for diarization logic in handler."""

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_diarize_requested_with_pipeline(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
        mock_transcribe_result,
    ):
        """diarize=true and pipeline loaded -> assigns speaker labels."""
        mock_resolve.return_value = "/tmp/audio.wav"
        mock_transcribe.return_value = mock_transcribe_result
        mock_torch.cuda.is_available.return_value = True

        # Mock whisperx functions used in diarization
        with patch("handler.diarize_pipeline") as mock_pipeline, \
             patch("handler.whisperx") as mock_whisperx:
            mock_pipeline.__bool__ = lambda self: True
            mock_pipeline.return_value = MagicMock()  # diarization result
            mock_whisperx.load_audio.return_value = MagicMock()
            mock_whisperx.assign_word_speakers.return_value = {
                "segments": [
                    {"id": 0, "start": 0.0, "end": 3.52, "text": " Hello", "speaker": "SPEAKER_00"},
                    {"id": 1, "start": 3.8, "end": 7.24, "text": " Great", "speaker": "SPEAKER_01"},
                ],
            }

            from handler import handler

            job = {"input": {"audio_url": "https://example.com/audio.wav", "diarize": True}}
            result = handler(job)

            mock_whisperx.assign_word_speakers.assert_called_once()
            # Result should contain speaker-labeled segments
            assert "segments" in result

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_diarize_requested_without_pipeline(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
        mock_transcribe_result,
    ):
        """diarize=true but pipeline is None -> returns warning."""
        mock_resolve.return_value = "/tmp/audio.wav"
        mock_transcribe.return_value = mock_transcribe_result
        mock_torch.cuda.is_available.return_value = True

        with patch("handler.diarize_pipeline", None):
            from handler import handler

            job = {"input": {"audio_url": "https://example.com/audio.wav", "diarize": True}}
            result = handler(job)

            assert "diarization_warning" in result

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_diarize_not_requested(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
        mock_transcribe_result,
    ):
        """diarize=false -> no diarization attempted, no speaker labels."""
        mock_resolve.return_value = "/tmp/audio.wav"
        mock_transcribe.return_value = mock_transcribe_result
        mock_torch.cuda.is_available.return_value = True

        with patch("handler.diarize_pipeline") as mock_pipeline:
            from handler import handler

            job = {"input": {"audio_url": "https://example.com/audio.wav", "diarize": False}}
            result = handler(job)

            # Pipeline should not be called
            mock_pipeline.assert_not_called()
            assert "diarization_warning" not in result

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_diarize_min_max_speakers(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
        mock_transcribe_result,
    ):
        """min_speakers and max_speakers forwarded to pipeline."""
        mock_resolve.return_value = "/tmp/audio.wav"
        mock_transcribe.return_value = mock_transcribe_result
        mock_torch.cuda.is_available.return_value = True

        with patch("handler.diarize_pipeline") as mock_pipeline, \
             patch("handler.whisperx") as mock_whisperx:
            mock_pipeline.__bool__ = lambda self: True
            mock_pipeline.return_value = MagicMock()
            mock_whisperx.load_audio.return_value = MagicMock()
            mock_whisperx.assign_word_speakers.return_value = {
                "segments": mock_transcribe_result["segments"],
            }

            from handler import handler

            job = {
                "input": {
                    "audio_url": "https://example.com/audio.wav",
                    "diarize": True,
                    "min_speakers": 2,
                    "max_speakers": 5,
                }
            }
            handler(job)

            # Check pipeline was called with min/max speakers
            pipeline_call = mock_pipeline.call_args
            assert pipeline_call[1].get("min_speakers") == 2 or \
                   (len(pipeline_call[0]) > 1 and pipeline_call[0][1] == 2) or \
                   pipeline_call.kwargs.get("min_speakers") == 2

    @patch("handler.torch")
    @patch("handler.cleanup_audio")
    @patch("handler.transcribe_audio")
    @patch("handler.resolve_audio_input")
    def test_diarize_warning_message_content(
        self, mock_resolve, mock_transcribe, mock_cleanup, mock_torch,
        mock_transcribe_result,
    ):
        """Warning includes HF_TOKEN, pyannote model name, and user agreement."""
        mock_resolve.return_value = "/tmp/audio.wav"
        mock_transcribe.return_value = mock_transcribe_result
        mock_torch.cuda.is_available.return_value = True

        with patch("handler.diarize_pipeline", None):
            from handler import handler

            job = {"input": {"audio_url": "https://example.com/audio.wav", "diarize": True}}
            result = handler(job)

            warning = result["diarization_warning"]
            assert "HF_TOKEN" in warning
            assert "pyannote/speaker-diarization-3.1" in warning
            assert "user agreement" in warning.lower() or "agree" in warning.lower()
