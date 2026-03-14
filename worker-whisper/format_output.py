"""
SRT/VTT/text output formatting utilities.

Converts transcription segments to standard subtitle formats
and plain text output.
"""


def format_timestamp_srt(seconds: float) -> str:
    """Convert seconds to SRT timestamp format: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_timestamp_vtt(seconds: float) -> str:
    """Convert seconds to VTT timestamp format: HH:MM:SS.mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def segments_to_srt(segments: list) -> str:
    """
    Convert segments to SRT subtitle format.

    Args:
        segments: List of segment dicts with 'start', 'end', 'text' keys.

    Returns:
        SRT-formatted string with numbered entries.
    """
    if not segments:
        return ""

    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(
            f"{format_timestamp_srt(seg['start'])} --> "
            f"{format_timestamp_srt(seg['end'])}"
        )
        lines.append(seg["text"].strip())
        lines.append("")
    return "\n".join(lines)


def segments_to_vtt(segments: list) -> str:
    """
    Convert segments to WebVTT subtitle format.

    Args:
        segments: List of segment dicts with 'start', 'end', 'text' keys.

    Returns:
        VTT-formatted string starting with WEBVTT header.
    """
    lines = ["WEBVTT", ""]
    if not segments:
        return "WEBVTT\n\n"
    for seg in segments:
        lines.append(
            f"{format_timestamp_vtt(seg['start'])} --> "
            f"{format_timestamp_vtt(seg['end'])}"
        )
        lines.append(seg["text"].strip())
        lines.append("")
    return "\n".join(lines)


def segments_to_text(segments: list) -> str:
    """
    Convert segments to plain text by joining stripped text.

    Args:
        segments: List of segment dicts with 'text' key.

    Returns:
        Space-joined text from all segments.
    """
    return " ".join(seg["text"].strip() for seg in segments)
