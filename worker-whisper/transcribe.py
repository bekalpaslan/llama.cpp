"""
Core transcription logic wrapping faster-whisper.

Provides transcribe_audio() which takes a WhisperModel and audio path,
returning a dict with segments (materialized from generator), word-level
timestamps, language detection, and duration info.
"""


def transcribe_audio(
    model,
    audio_path: str,
    language: str | None = None,
    task: str = "transcribe",
    word_timestamps: bool = True,
    vad_filter: bool = True,
    beam_size: int = 5,
    temperature: float = 0.0,
) -> dict:
    """
    Transcribe audio file using faster-whisper.

    Args:
        model: A faster_whisper.WhisperModel instance.
        audio_path: Path to the audio file.
        language: Language code (e.g., "en"). None for auto-detection.
        task: "transcribe" or "translate" (translate to English).
        word_timestamps: Whether to include word-level timestamps.
        vad_filter: Enable VAD to prevent hallucination on silence.
        beam_size: Beam size for decoding.
        temperature: Sampling temperature.

    Returns:
        Dict with 'segments', 'language', 'language_probability',
        'duration', 'duration_after_vad'.
    """
    segments_gen, info = model.transcribe(
        audio_path,
        language=language,
        task=task,
        word_timestamps=word_timestamps,
        vad_filter=vad_filter,
        beam_size=beam_size,
        temperature=temperature,
        condition_on_previous_text=False,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    # Materialize generator immediately (single-use)
    segments = []
    for seg in segments_gen:
        seg_dict = {
            "id": seg.id,
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text,
            "avg_logprob": round(seg.avg_logprob, 4),
            "no_speech_prob": round(seg.no_speech_prob, 4),
        }
        if seg.words:
            seg_dict["words"] = [
                {
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                    "word": w.word,
                    "probability": round(w.probability, 4),
                }
                for w in seg.words
            ]
        segments.append(seg_dict)

    return {
        "segments": segments,
        "language": info.language,
        "language_probability": round(info.language_probability, 4),
        "duration": round(info.duration, 3),
        "duration_after_vad": (
            round(info.duration_after_vad, 3)
            if info.duration_after_vad
            else None
        ),
    }
