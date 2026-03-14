"""Tests for voice_blend module -- parsing, validation, and blending."""

import pytest
from unittest.mock import MagicMock

import torch

from voice_blend import (
    MAX_BLEND_VOICES,
    blend_voices,
    parse_voice_spec,
    validate_blend_request,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

KOKORO_VOICES = {
    "af_heart": "American Female - Heart",
    "af_bella": "American Female - Bella",
    "af_sarah": "American Female - Sarah",
    "af_nova": "American Female - Nova",
    "af_sky": "American Female - Sky",
    "am_adam": "American Male - Adam",
    "jf_alpha": "Japanese Female - Alpha",
    "bf_emma": "British Female - Emma",
}


def _make_pipeline_mock():
    """Return a mock pipeline whose load_voice returns identifiable tensors."""
    pipeline = MagicMock()
    call_count = {"n": 0}

    def _load_voice(name):
        call_count["n"] += 1
        # Each voice gets a unique scale factor so we can verify weighted math.
        scale = float(call_count["n"])
        return torch.ones(511, 1, 256) * scale

    pipeline.load_voice.side_effect = _load_voice
    return pipeline


# ===========================================================================
# parse_voice_spec
# ===========================================================================


class TestParseVoiceSpec:
    """Tests for parse_voice_spec()."""

    def test_single_voice_passthrough(self):
        result = parse_voice_spec("af_heart")
        assert result == [("af_heart", 1.0)]

    def test_single_voice_with_weight_normalizes(self):
        result = parse_voice_spec("af_heart:100")
        assert result == [("af_heart", 1.0)]

    def test_two_voices_equal_weight(self):
        result = parse_voice_spec("af_heart,af_bella")
        assert result == [("af_heart", 0.5), ("af_bella", 0.5)]

    def test_two_voices_weighted(self):
        result = parse_voice_spec("af_heart:70,af_bella:30")
        assert len(result) == 2
        assert result[0][0] == "af_heart"
        assert result[1][0] == "af_bella"
        assert abs(result[0][1] - 0.7) < 1e-9
        assert abs(result[1][1] - 0.3) < 1e-9

    def test_ratio_based_normalization(self):
        result = parse_voice_spec("af_heart:2,af_bella:1,af_sarah:1")
        assert len(result) == 3
        assert abs(result[0][1] - 0.5) < 1e-9
        assert abs(result[1][1] - 0.25) < 1e-9
        assert abs(result[2][1] - 0.25) < 1e-9

    def test_zero_weight_raises(self):
        with pytest.raises(ValueError, match="positive"):
            parse_voice_spec("af_heart:0,af_bella:30")

    def test_negative_weight_raises(self):
        with pytest.raises(ValueError, match="positive"):
            parse_voice_spec("af_heart:-5,af_bella:30")

    def test_non_numeric_weight_raises(self):
        with pytest.raises(ValueError, match="numeric"):
            parse_voice_spec("af_heart:abc,af_bella:30")

    def test_exceeds_max_blend_voices_raises(self):
        names = ",".join(f"voice_{i}" for i in range(6))
        with pytest.raises(ValueError, match="5"):
            parse_voice_spec(names)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_voice_spec("")

    def test_max_blend_voices_constant(self):
        assert MAX_BLEND_VOICES == 5


# ===========================================================================
# validate_blend_request
# ===========================================================================


class TestValidateBlendRequest:
    """Tests for validate_blend_request()."""

    def test_valid_blend_returns_none(self):
        result = validate_blend_request(
            "af_heart:70,af_bella:30", KOKORO_VOICES, "kokoro"
        )
        assert result is None

    def test_cross_language_returns_error(self):
        result = validate_blend_request(
            "af_heart:70,jf_alpha:30", KOKORO_VOICES, "kokoro"
        )
        assert result is not None
        assert "language" in result.lower()

    def test_unknown_voice_returns_error(self):
        result = validate_blend_request(
            "af_heart:70,unknown_voice:30", KOKORO_VOICES, "kokoro"
        )
        assert result is not None
        assert "unknown_voice" in result

    def test_wrong_engine_returns_error(self):
        result = validate_blend_request(
            "af_heart:70,af_bella:30", KOKORO_VOICES, "dia"
        )
        assert result is not None
        assert "kokoro" in result.lower() or "Kokoro" in result

    def test_single_voice_no_validation(self):
        result = validate_blend_request("af_heart", KOKORO_VOICES, "kokoro")
        assert result is None

    def test_single_voice_with_weight_no_validation(self):
        # "af_heart:100" has no comma, so no blend validation
        result = validate_blend_request("af_heart:100", KOKORO_VOICES, "kokoro")
        assert result is None


# ===========================================================================
# blend_voices
# ===========================================================================


class TestBlendVoices:
    """Tests for blend_voices()."""

    def test_single_voice_returns_directly(self):
        pipeline = _make_pipeline_mock()
        result = blend_voices(pipeline, [("af_heart", 1.0)])
        pipeline.load_voice.assert_called_once_with("af_heart")
        assert isinstance(result, torch.Tensor)

    def test_multi_voice_weighted_sum(self):
        pipeline = MagicMock()
        # Return deterministic tensors
        tensor_a = torch.ones(511, 1, 256) * 2.0
        tensor_b = torch.ones(511, 1, 256) * 4.0
        pipeline.load_voice.side_effect = [tensor_a, tensor_b]

        result = blend_voices(pipeline, [("af_heart", 0.7), ("af_bella", 0.3)])

        expected = tensor_a * 0.7 + tensor_b * 0.3
        assert torch.allclose(result, expected)
        assert pipeline.load_voice.call_count == 2

    def test_three_voice_blend(self):
        pipeline = MagicMock()
        t1 = torch.ones(511, 1, 256) * 1.0
        t2 = torch.ones(511, 1, 256) * 2.0
        t3 = torch.ones(511, 1, 256) * 3.0
        pipeline.load_voice.side_effect = [t1, t2, t3]

        result = blend_voices(
            pipeline, [("v1", 0.5), ("v2", 0.3), ("v3", 0.2)]
        )

        expected = t1 * 0.5 + t2 * 0.3 + t3 * 0.2
        assert torch.allclose(result, expected)
