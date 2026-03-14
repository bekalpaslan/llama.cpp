"""
Reference audio validation for voice cloning.

Validates duration, sample rate, and signal-to-noise ratio of reference
audio before passing it to the Chatterbox model. Bad reference audio
produces silently degraded output -- the model never errors, it just
generates garbage. Validation must run before any GPU compute.
"""

import numpy as np
import soundfile as sf

MIN_DURATION_SECONDS = 5.0
MAX_DURATION_SECONDS = 60.0
MIN_SAMPLE_RATE = 16000
MIN_SNR_DB = 15.0


def validate_reference_audio(audio_path: str) -> dict:
    """
    Validate reference audio for voice cloning quality.

    Checks duration, sample rate, and estimated SNR against thresholds.

    Args:
        audio_path: Path to the reference audio file.

    Returns:
        Dict with keys: duration_seconds, sample_rate, snr_db, quality.
        quality is "good" (SNR >= 25dB) or "acceptable" (15-25dB).

    Raises:
        ValueError: With actionable message on validation failure.
    """
    info = sf.info(audio_path)
    duration = info.duration
    sample_rate = info.samplerate

    # Duration check
    if duration < MIN_DURATION_SECONDS:
        raise ValueError(
            f"Reference audio too short ({duration:.1f}s). "
            f"Minimum {MIN_DURATION_SECONDS}s required. "
            "Use a 10-15 second clip for best results."
        )
    if duration > MAX_DURATION_SECONDS:
        raise ValueError(
            f"Reference audio too long ({duration:.1f}s). "
            f"Maximum {MAX_DURATION_SECONDS}s accepted. "
            "Trim to 10-20 seconds of clean speech."
        )

    # Sample rate check
    if sample_rate < MIN_SAMPLE_RATE:
        raise ValueError(
            f"Reference audio sample rate too low ({sample_rate}Hz). "
            f"Minimum {MIN_SAMPLE_RATE}Hz required."
        )

    # SNR estimation (energy-based)
    audio_data, sr = sf.read(audio_path)
    if len(audio_data.shape) > 1:
        audio_data = audio_data[:, 0]  # use first channel for mono
    snr_db = _estimate_snr(audio_data)

    if snr_db < MIN_SNR_DB:
        raise ValueError(
            f"Reference audio quality too low (estimated SNR: {snr_db:.1f}dB). "
            f"Minimum {MIN_SNR_DB}dB required. "
            "Use a clean recording with minimal background noise."
        )

    return {
        "duration_seconds": duration,
        "sample_rate": sample_rate,
        "snr_db": round(snr_db, 1),
        "quality": "good" if snr_db >= 25 else "acceptable",
    }


def _estimate_snr(
    audio: np.ndarray,
    frame_length: int = 2048,
    silence_threshold_percentile: int = 10,
) -> float:
    """
    Estimate signal-to-noise ratio using energy-based method.

    Frames the audio into fixed-length windows, computes per-frame energy,
    then compares lowest-energy frames (assumed noise) to highest-energy
    frames (assumed signal).

    Args:
        audio: 1-D numpy array of audio samples.
        frame_length: Samples per frame for energy computation.
        silence_threshold_percentile: Percentage of lowest-energy frames
            treated as noise floor.

    Returns:
        Estimated SNR in decibels. Returns 60.0 for effectively silent
        noise floor.
    """
    n_frames = len(audio) // frame_length
    if n_frames < 2:
        return 0.0

    frames = audio[: n_frames * frame_length].reshape(n_frames, frame_length)
    frame_energy = np.mean(frames**2, axis=1)
    frame_energy = np.maximum(frame_energy, 1e-10)  # avoid log(0)

    # Sort by energy
    sorted_energy = np.sort(frame_energy)
    n_noise = max(1, int(n_frames * silence_threshold_percentile / 100))
    n_signal = max(1, int(n_frames * 0.5))

    noise_energy = np.mean(sorted_energy[:n_noise])
    signal_energy = np.mean(sorted_energy[-n_signal:])

    if noise_energy <= 0:
        return 60.0  # Effectively silent noise floor

    snr = 10 * np.log10(signal_energy / noise_energy)
    return float(snr)
