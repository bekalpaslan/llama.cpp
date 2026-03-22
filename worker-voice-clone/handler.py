"""
RunPod Serverless handler for voice cloning.

Wires validate_reference.py, voice_clone.py, and audio_utils.py into a
RunPod handler with:
- Reference audio input resolution (URL or base64)
- Reference audio quality validation (duration, sample rate, SNR)
- Chatterbox voice cloning inference
- Output encoding at 48kHz (WAV or MP3)
- VRAM cleanup after every request
"""

import logging
import os

import torch

from audio_utils import resolve_audio_input, cleanup_audio
from validate_reference import validate_reference_audio
from voice_clone import load_model, clone_voice, encode_output

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CUDA memory configuration
# ---------------------------------------------------------------------------
if "PYTORCH_CUDA_ALLOC_CONF" not in os.environ:
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# ---------------------------------------------------------------------------
# HuggingFace cache: persist model weights across cold starts on volume
# ---------------------------------------------------------------------------
if os.path.isdir("/runpod-volume"):
    os.environ.setdefault("HF_HOME", "/runpod-volume/.cache/huggingface")

# ---------------------------------------------------------------------------
# Model loading (module-level, runs once at cold start)
# ---------------------------------------------------------------------------
MODEL_VARIANT = os.environ.get("MODEL_VARIANT", "multilingual")
model = load_model(MODEL_VARIANT)


def handler(job):
    """
    RunPod handler entry point for voice cloning.

    Input format:
        {
            "text": "Text to synthesize",
            "reference_audio_url": "https://..." OR "reference_audio_base64": "...",
            "language": "en",          # optional, default "en"
            "output_format": "wav",    # optional, "wav" or "mp3"
            "exaggeration": 0.5,       # optional, 0.0-1.0
            "cfg_weight": 0.5          # optional, 0.0-1.0
        }

    Returns:
        dict with audio_base64, format, sample_rate, duration_seconds,
        reference_quality, model_variant, language -- or {"error": "..."}.
    """
    job_input = job["input"]
    ref_path = None

    try:
        # -----------------------------------------------------------------
        # Validate text input
        # -----------------------------------------------------------------
        text = job_input.get("text")
        if not text or not text.strip():
            return {"error": "Required field 'text' is missing or empty."}

        # -----------------------------------------------------------------
        # Resolve reference audio (map to audio_utils keys)
        # -----------------------------------------------------------------
        ref_input = {}
        if "reference_audio_url" in job_input:
            ref_input["audio_url"] = job_input["reference_audio_url"]
        elif "reference_audio_base64" in job_input:
            ref_input["audio_base64"] = job_input["reference_audio_base64"]
        else:
            return {
                "error": "Provide 'reference_audio_url' or 'reference_audio_base64'."
            }

        ref_path = resolve_audio_input(ref_input)

        # -----------------------------------------------------------------
        # Validate reference audio quality (VC-03)
        # -----------------------------------------------------------------
        quality = validate_reference_audio(ref_path)

        # -----------------------------------------------------------------
        # Extract generation parameters
        # -----------------------------------------------------------------
        language_id = job_input.get("language", "en")
        output_format = job_input.get("output_format", "wav")
        exaggeration = job_input.get("exaggeration", 0.5)
        cfg_weight = job_input.get("cfg_weight", 0.5)

        # -----------------------------------------------------------------
        # Generate cloned speech (VC-01, VC-02)
        # -----------------------------------------------------------------
        wav, native_sr = clone_voice(
            model,
            text,
            ref_path,
            language_id=language_id,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
        )

        # -----------------------------------------------------------------
        # Encode output at 48kHz (VC-04)
        # -----------------------------------------------------------------
        audio_b64, fmt = encode_output(wav, native_sr, output_format, target_sr=48000)
        duration = wav.shape[-1] / native_sr

        return {
            "audio_base64": audio_b64,
            "format": fmt,
            "sample_rate": 48000,
            "duration_seconds": round(duration, 2),
            "reference_quality": quality,
            "model_variant": MODEL_VARIANT,
            "language": language_id,
        }

    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Voice cloning failed: {str(e)}"}
    finally:
        if ref_path:
            cleanup_audio(ref_path)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


if __name__ == "__main__":
    import runpod

    runpod.serverless.start({"handler": handler})
