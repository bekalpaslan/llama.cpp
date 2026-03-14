"""Tests for reference audio validation (VC-03)."""

import numpy as np
import pytest


class TestValidateReferenceAudio:
    """Tests for validate_reference_audio()."""

    def test_rejects_too_short(self, tmp_audio_file):
        """Audio under 5s raises ValueError with 'too short' and minimum requirement."""
        from validate_reference import validate_reference_audio

        path = tmp_audio_file(duration=3.0)
        with pytest.raises(ValueError, match="too short"):
            validate_reference_audio(path)

    def test_rejects_too_long(self, tmp_audio_file):
        """Audio over 60s raises ValueError with 'too long' and maximum limit."""
        from validate_reference import validate_reference_audio

        path = tmp_audio_file(duration=65.0)
        with pytest.raises(ValueError, match="too long"):
            validate_reference_audio(path)

    def test_rejects_low_sample_rate(self, tmp_audio_file):
        """Audio below 16kHz raises ValueError with sample rate info."""
        from validate_reference import validate_reference_audio

        path = tmp_audio_file(duration=10.0, sample_rate=8000)
        with pytest.raises(ValueError, match="sample rate too low"):
            validate_reference_audio(path)

    def test_rejects_low_snr(self, tmp_audio_file):
        """Audio with SNR below 15dB raises ValueError with quality guidance."""
        from validate_reference import validate_reference_audio

        # Very noisy audio: noise_level=0.5 will overwhelm the 0.5-amplitude signal
        path = tmp_audio_file(duration=10.0, noise_level=0.5)
        with pytest.raises(ValueError, match="quality too low"):
            validate_reference_audio(path)

    def test_accepts_valid_audio(self, tmp_audio_file):
        """10s clean audio at 22050Hz returns dict with expected keys."""
        from validate_reference import validate_reference_audio

        path = tmp_audio_file(duration=10.0, sample_rate=22050)
        result = validate_reference_audio(path)

        assert isinstance(result, dict)
        assert "duration_seconds" in result
        assert "sample_rate" in result
        assert "snr_db" in result
        assert "quality" in result
        assert result["sample_rate"] == 22050
        assert 9.5 <= result["duration_seconds"] <= 10.5

    def test_quality_good_vs_acceptable(self, tmp_audio_file):
        """SNR >= 25dB returns quality='good', 15-25dB returns quality='acceptable'."""
        from validate_reference import validate_reference_audio

        # Clean audio (no noise) should have very high SNR -> "good"
        path_clean = tmp_audio_file(duration=10.0, noise_level=0.0)
        result_clean = validate_reference_audio(path_clean)
        assert result_clean["quality"] == "good"

        # Moderately noisy audio should have lower SNR -> "acceptable"
        # noise_level=0.05 with signal amplitude 0.5 gives SNR ~20dB
        path_noisy = tmp_audio_file(duration=10.0, noise_level=0.05)
        result_noisy = validate_reference_audio(path_noisy)
        assert result_noisy["quality"] == "acceptable"

    def test_estimate_snr_silent_noise(self, tmp_audio_file):
        """Near-silent noise floor returns high SNR (effectively clean)."""
        from validate_reference import validate_reference_audio

        path = tmp_audio_file(duration=10.0, noise_level=0.0)
        result = validate_reference_audio(path)
        # Pure sine wave with no noise should have very high SNR
        assert result["snr_db"] >= 25.0

    def test_stereo_to_mono(self, tmp_audio_file):
        """Stereo reference audio is handled correctly (uses first channel)."""
        from validate_reference import validate_reference_audio

        path = tmp_audio_file(duration=10.0, channels=2)
        result = validate_reference_audio(path)

        assert isinstance(result, dict)
        assert "duration_seconds" in result
        assert result["sample_rate"] == 22050
