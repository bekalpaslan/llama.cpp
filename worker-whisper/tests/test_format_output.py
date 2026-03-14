"""Tests for format_output.py -- SRT/VTT/text output formatting."""

from format_output import (
    format_timestamp_srt,
    format_timestamp_vtt,
    segments_to_srt,
    segments_to_text,
    segments_to_vtt,
)


class TestFormatTimestampSRT:
    """Test SRT timestamp formatting."""

    def test_format_timestamp_srt(self):
        """format_timestamp_srt(3661.5) returns '01:01:01,500'."""
        assert format_timestamp_srt(3661.5) == "01:01:01,500"

    def test_format_timestamp_srt_zero(self):
        """format_timestamp_srt(0.0) returns '00:00:00,000'."""
        assert format_timestamp_srt(0.0) == "00:00:00,000"


class TestFormatTimestampVTT:
    """Test VTT timestamp formatting."""

    def test_format_timestamp_vtt(self):
        """format_timestamp_vtt(3661.5) returns '01:01:01.500'."""
        assert format_timestamp_vtt(3661.5) == "01:01:01.500"

    def test_format_timestamp_vtt_zero(self):
        """format_timestamp_vtt(0.0) returns '00:00:00.000'."""
        assert format_timestamp_vtt(0.0) == "00:00:00.000"


class TestSegmentsToSRT:
    """Test SRT output generation."""

    def test_segments_to_srt(self, sample_segments):
        """Produces valid SRT with numbered entries, timestamps, and text."""
        srt = segments_to_srt(sample_segments)

        lines = srt.split("\n")

        # First entry
        assert lines[0] == "1"
        assert "-->" in lines[1]
        assert "Hello, how are you today?" in lines[2]

        # Should have numbered entries
        assert "2" in srt
        assert "3" in srt

    def test_srt_empty_segments(self):
        """Returns empty string for empty list."""
        assert segments_to_srt([]) == ""


class TestSegmentsToVTT:
    """Test VTT output generation."""

    def test_segments_to_vtt(self, sample_segments):
        """Produces valid VTT starting with 'WEBVTT' header."""
        vtt = segments_to_vtt(sample_segments)

        assert vtt.startswith("WEBVTT")
        assert "-->" in vtt
        assert "Hello, how are you today?" in vtt

    def test_vtt_empty_segments(self):
        """Returns 'WEBVTT\\n\\n' for empty list."""
        assert segments_to_vtt([]) == "WEBVTT\n\n"


class TestSegmentsToText:
    """Test plain text output generation."""

    def test_segments_to_text(self, sample_segments):
        """Joins segment text with spaces, strips whitespace."""
        text = segments_to_text(sample_segments)

        assert "Hello, how are you today?" in text
        assert "I am doing great, thank you." in text
        assert "Let's get started." in text
        # No leading/trailing whitespace on individual segments
        assert not text.startswith(" ")

    def test_text_empty_segments(self):
        """Returns empty string for empty list."""
        assert segments_to_text([]) == ""
