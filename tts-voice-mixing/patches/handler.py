"""RunPod TTS Worker handler with voice blending validation.

Drop-in replacement for tts-worker/handler.py.
Adds validate_blend_request() call in the Kokoro engine path.
"""

import base64
import io
import os
import time

import runpod
import soundfile as sf

# Engine selection
TTS_ENGINE = os.environ.get("TTS_ENGINE", "kokoro")

# Import the appropriate engine
if TTS_ENGINE == "kokoro":
    from engines.kokoro_engine import KOKORO_VOICES, KokoroEngine
    from voice_blend import validate_blend_request

    engine = KokoroEngine()
elif TTS_ENGINE == "dia":
    from engines.dia_engine import DiaEngine

    engine = DiaEngine()
elif TTS_ENGINE == "f5":
    from engines.f5_engine import F5Engine

    engine = F5Engine()
else:
    raise ValueError(f"Unknown TTS_ENGINE: {TTS_ENGINE}")


def _convert_audio(wav_bytes: bytes, sample_rate: int, output_format: str) -> bytes:
    """Convert WAV bytes to the requested output format.

    Args:
        wav_bytes: Raw WAV audio bytes.
        sample_rate: Sample rate of the audio.
        output_format: Target format ("wav", "flac", "pcm").

    Returns:
        Audio bytes in the requested format.
    """
    if output_format == "wav":
        return wav_bytes

    # Read the WAV data
    audio_data, sr = sf.read(io.BytesIO(wav_bytes))

    if output_format == "flac":
        buf = io.BytesIO()
        sf.write(buf, audio_data, sr, format="FLAC")
        return buf.getvalue()
    elif output_format == "pcm":
        # Return raw PCM (16-bit signed integer)
        import numpy as np

        pcm_data = (audio_data * 32767).astype(np.int16)
        return pcm_data.tobytes()
    else:
        return wav_bytes


def handler(job):
    """Handle a TTS generation request.

    Expected input format:
        {
            "text": "Hello world",
            "voice": "af_heart" or "af_heart:70,af_bella:30",
            "speed": 1.0,
            "response_format": "wav"
        }

    Returns:
        {
            "audio": "<base64-encoded audio>",
            "format": "wav",
            "sample_rate": 24000,
            "engine": "kokoro",
            "duration_seconds": 1.23
        }
    """
    job_input = job["input"]

    # Extract parameters
    text = job_input.get("text", "")
    voice = job_input.get("voice", "af_heart")
    speed = float(job_input.get("speed", 1.0))
    response_format = job_input.get("response_format", "wav").lower()

    if not text:
        return {"error": "No text provided. Please provide 'text' in the input."}

    # Validate voice blend request (Kokoro only)
    if TTS_ENGINE == "kokoro":
        blend_error = validate_blend_request(voice, KOKORO_VOICES, TTS_ENGINE)
        if blend_error:
            return {"error": blend_error}

    # Generate audio
    start_time = time.time()

    try:
        wav_bytes, sample_rate = engine.generate(
            text=text, voice=voice, speed=speed
        )
    except Exception as e:
        return {"error": f"TTS generation failed: {str(e)}"}

    if not wav_bytes:
        return {"error": "TTS engine produced no audio output."}

    generation_time = time.time() - start_time

    # Convert to requested format
    try:
        output_bytes = _convert_audio(wav_bytes, sample_rate, response_format)
    except Exception as e:
        return {"error": f"Audio conversion failed: {str(e)}"}

    # Encode as base64
    audio_b64 = base64.b64encode(output_bytes).decode("utf-8")

    return {
        "audio": audio_b64,
        "format": response_format,
        "sample_rate": sample_rate,
        "engine": TTS_ENGINE,
        "duration_seconds": round(generation_time, 3),
    }


def dispatch(job):
    """Route requests to the appropriate handler.

    Supports:
        - {"action": "list_voices"} -> returns available voices
        - All other inputs -> handler() for TTS generation
    """
    job_input = job.get("input", {})

    # Handle list_voices action
    action = job_input.get("action", "")
    if action == "list_voices":
        return {"voices": engine.list_voices(), "engine": TTS_ENGINE}

    return handler(job)


if __name__ == "__main__":
    runpod.serverless.start({"handler": dispatch})
