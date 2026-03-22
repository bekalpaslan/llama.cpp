"""Tests for transcribe.py -- core transcription logic wrapping faster-whisper."""

from transcribe import transcribe_audio


class TestTranscribeBasic:
    """Test basic transcription output structure."""

    def test_transcribe_basic(self, mock_whisper_model):
        """transcribe_audio() returns dict with required keys."""
        result = transcribe_audio(mock_whisper_model, "/tmp/test.wav")

        assert isinstance(result, dict)
        assert "segments" in result
        assert "language" in result
        assert "language_probability" in result
        assert "duration" in result
        assert "duration_after_vad" in result

    def test_segments_materialized(self, mock_whisper_model):
        """Segments are a list (not generator), can be iterated multiple times."""
        result = transcribe_audio(mock_whisper_model, "/tmp/test.wav")

        segments = result["segments"]
        assert isinstance(segments, list)
        # Should be able to iterate multiple times
        first_pass = [s["text"] for s in segments]
        second_pass = [s["text"] for s in segments]
        assert first_pass == second_pass
        assert len(segments) == 3


class TestWordTimestamps:
    """Test word-level timestamp output."""

    def test_word_timestamps(self, mock_whisper_model):
        """Returned segments contain 'words' list with start/end/word/probability fields."""
        result = transcribe_audio(mock_whisper_model, "/tmp/test.wav")

        for segment in result["segments"]:
            assert "words" in segment
            assert isinstance(segment["words"], list)
            assert len(segment["words"]) > 0

            for word in segment["words"]:
                assert "start" in word
                assert "end" in word
                assert "word" in word
                assert "probability" in word
                assert isinstance(word["start"], float)
                assert isinstance(word["end"], float)
                assert isinstance(word["word"], str)
                assert isinstance(word["probability"], float)


class TestVADFilter:
    """Test VAD filter parameter handling."""

    def test_vad_default_enabled(self, mock_whisper_model):
        """model.transcribe is called with vad_filter=True by default."""
        transcribe_audio(mock_whisper_model, "/tmp/test.wav")

        call_kwargs = mock_whisper_model.transcribe.call_args[1]
        assert call_kwargs["vad_filter"] is True

    def test_vad_can_be_disabled(self, mock_whisper_model):
        """Passing vad_filter=False forwards to model.transcribe."""
        # Reset mock to return fresh generator
        from unittest.mock import MagicMock

        def _make_word(start, end, word, probability):
            w = MagicMock()
            w.start = start
            w.end = end
            w.word = word
            w.probability = probability
            return w

        seg = MagicMock()
        seg.id = 0
        seg.start = 0.0
        seg.end = 1.0
        seg.text = " Test."
        seg.avg_logprob = -0.2
        seg.no_speech_prob = 0.01
        seg.words = [_make_word(0.0, 0.5, " Test.", 0.95)]

        info = MagicMock()
        info.language = "en"
        info.language_probability = 0.99
        info.duration = 1.0
        info.duration_after_vad = 1.0

        mock_whisper_model.transcribe.return_value = (iter([seg]), info)

        transcribe_audio(mock_whisper_model, "/tmp/test.wav", vad_filter=False)

        call_kwargs = mock_whisper_model.transcribe.call_args[1]
        assert call_kwargs["vad_filter"] is False


class TestLanguageDetection:
    """Test language detection output."""

    def test_language_detection(self, mock_whisper_model):
        """Result contains language and language_probability from model info."""
        result = transcribe_audio(mock_whisper_model, "/tmp/test.wav")

        assert result["language"] == "en"
        assert result["language_probability"] == 0.98


class TestTranslateTask:
    """Test translation task parameter forwarding."""

    def test_translate_task(self, mock_whisper_model):
        """Passing task='translate' forwards to model.transcribe."""
        # Reset mock for fresh generator
        from unittest.mock import MagicMock

        seg = MagicMock()
        seg.id = 0
        seg.start = 0.0
        seg.end = 1.0
        seg.text = " Translated text."
        seg.avg_logprob = -0.2
        seg.no_speech_prob = 0.01
        seg.words = []

        info = MagicMock()
        info.language = "es"
        info.language_probability = 0.95
        info.duration = 1.0
        info.duration_after_vad = 0.9

        mock_whisper_model.transcribe.return_value = (iter([seg]), info)

        transcribe_audio(mock_whisper_model, "/tmp/test.wav", task="translate")

        call_kwargs = mock_whisper_model.transcribe.call_args[1]
        assert call_kwargs["task"] == "translate"


class TestConditionOnPreviousText:
    """Test condition_on_previous_text parameter."""

    def test_condition_on_previous_text_false(self, mock_whisper_model):
        """model.transcribe is called with condition_on_previous_text=False."""
        transcribe_audio(mock_whisper_model, "/tmp/test.wav")

        call_kwargs = mock_whisper_model.transcribe.call_args[1]
        assert call_kwargs["condition_on_previous_text"] is False
