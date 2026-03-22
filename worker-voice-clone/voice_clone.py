"""
Voice cloning wrapper for Chatterbox TTS.

Provides model loading, voice cloning inference, and output encoding
with optional upsampling from Chatterbox's native 24kHz to 48kHz.
"""

import base64
import importlib
import logging
import os
import subprocess
import tempfile
from io import BytesIO

import numpy as np
import soundfile as sf
import torch
import torchaudio.functional as F

logger = logging.getLogger(__name__)

# Variant -> (module path, class name)
_VARIANT_MAP = {
    "turbo": ("chatterbox.tts_turbo", "ChatterboxTurboTTS"),
    "original": ("chatterbox.tts", "ChatterboxTTS"),
    "multilingual": ("chatterbox.mtl_tts", "ChatterboxMultilingualTTS"),
}


def load_model(variant: str = "multilingual", device: str = "cuda"):
    """
    Load a Chatterbox model variant.

    Args:
        variant: Model variant - "turbo", "original", or "multilingual".
        device: Device to load the model on (default "cuda").

    Returns:
        Loaded Chatterbox model instance.

    Raises:
        ValueError: If variant is not recognized.
    """
    if variant not in _VARIANT_MAP:
        raise ValueError(
            f"Unknown model variant '{variant}'. "
            f"Choose from: {', '.join(_VARIANT_MAP.keys())}"
        )

    module_path, class_name = _VARIANT_MAP[variant]
    module = importlib.import_module(module_path)
    model_class = getattr(module, class_name)
    model = model_class.from_pretrained(device=device)

    logger.info("Loaded Chatterbox %s on %s", variant, device)
    return model


def clone_voice(
    model,
    text: str,
    reference_audio_path: str,
    language_id: str = "en",
    exaggeration: float = 0.5,
    cfg_weight: float = 0.5,
    temperature: float = 0.8,
) -> tuple:
    """
    Generate speech cloning the voice from reference audio.

    Args:
        model: Loaded Chatterbox model instance.
        text: Text to synthesize.
        reference_audio_path: Path to reference audio file.
        language_id: Target language ISO code (used by multilingual variant).
        exaggeration: Speech expressiveness (0.0-1.0).
        cfg_weight: Voice similarity adherence (0.0-1.0).
        temperature: Sampling randomness.

    Returns:
        Tuple of (wav_tensor, sample_rate).
    """
    kwargs = {
        "audio_prompt_path": reference_audio_path,
        "language_id": language_id,
        "exaggeration": exaggeration,
        "cfg_weight": cfg_weight,
    }

    wav = model.generate(text, **kwargs)
    sample_rate = model.sr
    return wav, sample_rate


def encode_output(
    wav_tensor: torch.Tensor,
    native_sr: int,
    output_format: str = "wav",
    target_sr: int = 48000,
) -> tuple:
    """
    Encode audio tensor to base64 with optional upsampling.

    Args:
        wav_tensor: Audio tensor from Chatterbox model.
        native_sr: Native sample rate of the tensor (usually 24000).
        output_format: Output format - "wav" or "mp3".
        target_sr: Target sample rate for output (default 48000).

    Returns:
        Tuple of (base64_string, format_string).
    """
    # Upsample if needed
    if target_sr != native_sr:
        wav_tensor = F.resample(wav_tensor, native_sr, target_sr)

    # Move to CPU numpy
    audio_np = wav_tensor.squeeze().cpu().numpy()

    if output_format == "mp3":
        return _encode_mp3(audio_np, target_sr)
    else:
        return _encode_wav(audio_np, target_sr)


def _encode_wav(audio_np: np.ndarray, sample_rate: int) -> tuple:
    """Encode numpy audio to WAV base64."""
    buf = BytesIO()
    sf.write(buf, audio_np, sample_rate, format="wav")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8"), "wav"


def _encode_mp3(audio_np: np.ndarray, sample_rate: int) -> tuple:
    """Encode numpy audio to MP3 via ffmpeg subprocess."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
        sf.write(tmp_wav.name, audio_np, sample_rate, format="wav")
        tmp_wav_path = tmp_wav.name

    tmp_mp3_path = tmp_wav_path.replace(".wav", ".mp3")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                tmp_wav_path,
                "-codec:a",
                "libmp3lame",
                "-qscale:a",
                "2",
                tmp_mp3_path,
            ],
            capture_output=True,
            check=True,
        )
        with open(tmp_mp3_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8"), "mp3"
    finally:
        for p in [tmp_wav_path, tmp_mp3_path]:
            try:
                os.unlink(p)
            except OSError:
                pass
