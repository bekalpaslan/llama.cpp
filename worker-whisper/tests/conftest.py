"""Shared test fixtures for worker-whisper test suite."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_whisper_model():
    """
    Mock faster_whisper.WhisperModel with realistic transcribe() output.

    Returns a MagicMock whose transcribe() method returns (segments_generator, info),
    mimicking faster-whisper's actual API.
    """
    model = MagicMock()

    # Build mock word objects
    def _make_word(start, end, word, probability):
        w = MagicMock()
        w.start = start
        w.end = end
        w.word = word
        w.probability = probability
        return w

    # Build mock segment objects
    seg0 = MagicMock()
    seg0.id = 0
    seg0.start = 0.0
    seg0.end = 3.52
    seg0.text = " Hello, how are you today?"
    seg0.avg_logprob = -0.2341
    seg0.no_speech_prob = 0.0123
    seg0.words = [
        _make_word(0.0, 0.42, " Hello,", 0.95),
        _make_word(0.5, 0.72, " how", 0.98),
        _make_word(0.8, 1.1, " are", 0.97),
        _make_word(1.2, 1.5, " you", 0.99),
        _make_word(1.6, 2.1, " today?", 0.96),
    ]

    seg1 = MagicMock()
    seg1.id = 1
    seg1.start = 3.8
    seg1.end = 7.24
    seg1.text = " I am doing great, thank you."
    seg1.avg_logprob = -0.1892
    seg1.no_speech_prob = 0.0087
    seg1.words = [
        _make_word(3.8, 4.0, " I", 0.99),
        _make_word(4.1, 4.3, " am", 0.98),
        _make_word(4.4, 4.8, " doing", 0.97),
        _make_word(4.9, 5.3, " great,", 0.95),
        _make_word(5.5, 5.8, " thank", 0.96),
        _make_word(5.9, 6.2, " you.", 0.97),
    ]

    seg2 = MagicMock()
    seg2.id = 2
    seg2.start = 7.5
    seg2.end = 10.2
    seg2.text = " Let's get started."
    seg2.avg_logprob = -0.2105
    seg2.no_speech_prob = 0.0056
    seg2.words = [
        _make_word(7.5, 7.9, " Let's", 0.94),
        _make_word(8.0, 8.4, " get", 0.98),
        _make_word(8.5, 9.0, " started.", 0.96),
    ]

    # Mock info object
    info = MagicMock()
    info.language = "en"
    info.language_probability = 0.98
    info.duration = 10.5
    info.duration_after_vad = 9.8

    # transcribe() returns a generator and info
    def _segments_generator():
        yield seg0
        yield seg1
        yield seg2

    model.transcribe.return_value = (_segments_generator(), info)

    return model


@pytest.fixture
def sample_segments():
    """
    Pre-built segment dicts as they would appear after transcribe_audio() processes them.
    Three segments covering ~10 seconds of English audio.
    """
    return [
        {
            "id": 0,
            "start": 0.0,
            "end": 3.52,
            "text": " Hello, how are you today?",
            "avg_logprob": -0.2341,
            "no_speech_prob": 0.0123,
            "words": [
                {"start": 0.0, "end": 0.42, "word": " Hello,", "probability": 0.95},
                {"start": 0.5, "end": 0.72, "word": " how", "probability": 0.98},
                {"start": 0.8, "end": 1.1, "word": " are", "probability": 0.97},
                {"start": 1.2, "end": 1.5, "word": " you", "probability": 0.99},
                {"start": 1.6, "end": 2.1, "word": " today?", "probability": 0.96},
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
                {"start": 4.1, "end": 4.3, "word": " am", "probability": 0.98},
                {"start": 4.4, "end": 4.8, "word": " doing", "probability": 0.97},
                {"start": 4.9, "end": 5.3, "word": " great,", "probability": 0.95},
                {"start": 5.5, "end": 5.8, "word": " thank", "probability": 0.96},
                {"start": 5.9, "end": 6.2, "word": " you.", "probability": 0.97},
            ],
        },
        {
            "id": 2,
            "start": 7.5,
            "end": 10.2,
            "text": " Let's get started.",
            "avg_logprob": -0.2105,
            "no_speech_prob": 0.0056,
            "words": [
                {"start": 7.5, "end": 7.9, "word": " Let's", "probability": 0.94},
                {"start": 8.0, "end": 8.4, "word": " get", "probability": 0.98},
                {"start": 8.5, "end": 9.0, "word": " started.", "probability": 0.96},
            ],
        },
    ]


@pytest.fixture
def sample_segments_multi_language():
    """
    Same structure as sample_segments but for Spanish audio.
    Used to test multi-language detection.
    """
    return [
        {
            "id": 0,
            "start": 0.0,
            "end": 3.2,
            "text": " Hola, como estas hoy?",
            "avg_logprob": -0.2500,
            "no_speech_prob": 0.0150,
            "words": [
                {"start": 0.0, "end": 0.5, "word": " Hola,", "probability": 0.93},
                {"start": 0.6, "end": 0.9, "word": " como", "probability": 0.95},
                {"start": 1.0, "end": 1.4, "word": " estas", "probability": 0.94},
                {"start": 1.5, "end": 2.0, "word": " hoy?", "probability": 0.92},
            ],
        },
        {
            "id": 1,
            "start": 3.5,
            "end": 6.8,
            "text": " Estoy muy bien, gracias.",
            "avg_logprob": -0.2100,
            "no_speech_prob": 0.0090,
            "words": [
                {"start": 3.5, "end": 4.0, "word": " Estoy", "probability": 0.96},
                {"start": 4.1, "end": 4.4, "word": " muy", "probability": 0.97},
                {"start": 4.5, "end": 4.9, "word": " bien,", "probability": 0.95},
                {"start": 5.0, "end": 5.5, "word": " gracias.", "probability": 0.94},
            ],
        },
        {
            "id": 2,
            "start": 7.0,
            "end": 9.5,
            "text": " Vamos a empezar.",
            "avg_logprob": -0.2300,
            "no_speech_prob": 0.0060,
            "words": [
                {"start": 7.0, "end": 7.4, "word": " Vamos", "probability": 0.93},
                {"start": 7.5, "end": 7.8, "word": " a", "probability": 0.98},
                {"start": 7.9, "end": 8.5, "word": " empezar.", "probability": 0.95},
            ],
        },
    ]
