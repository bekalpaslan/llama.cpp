"""
RunPod Serverless handler for speech-to-text transcription.

Wires transcribe.py and format_output.py into a RunPod handler with:
- Single audio transcription (URL or base64)
- Batch audio processing (multiple URLs)
- WhisperX diarization with graceful degradation
- VRAM cleanup after each request
"""

import logging
import os

import torch

from transcribe import transcribe_audio
from format_output import segments_to_srt, segments_to_vtt, segments_to_text
from audio_utils import resolve_audio_input, cleanup_audio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CUDA memory configuration
# ---------------------------------------------------------------------------
if "PYTORCH_CUDA_ALLOC_CONF" not in os.environ:
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# ---------------------------------------------------------------------------
# Model loading (module-level, runs once at cold start)
# ---------------------------------------------------------------------------
MODEL_SIZE = os.environ.get("MODEL_SIZE", "large-v3-turbo")
COMPUTE_TYPE = os.environ.get("COMPUTE_TYPE", "int8")
HF_TOKEN = os.environ.get("HF_TOKEN")
HF_REPO_ID = os.environ.get("HF_REPO_ID")
MODEL_NAME = os.environ.get("MODEL_NAME")

model_path = MODEL_SIZE

if HF_REPO_ID:
    try:
        from download_model import download_model
        model_path = download_model(
            repo_id=HF_REPO_ID,
            token=HF_TOKEN or None,
            snapshot=True,
        )
        logger.info("Downloaded model from %s to %s", HF_REPO_ID, model_path)
    except Exception as e:
        logger.warning("Failed to download model from %s: %s. Using MODEL_SIZE=%s", HF_REPO_ID, e, MODEL_SIZE)
        model_path = MODEL_SIZE

try:
    from faster_whisper import WhisperModel
    model = WhisperModel(model_path, device="cuda", compute_type=COMPUTE_TYPE)
    logger.info("Loaded WhisperModel: %s (compute_type=%s)", model_path, COMPUTE_TYPE)
except Exception as e:
    logger.warning("Failed to load WhisperModel: %s. Handler will fail on requests.", e)
    model = None

# ---------------------------------------------------------------------------
# Diarization pipeline (optional, requires HF_TOKEN)
# ---------------------------------------------------------------------------
diarize_pipeline = None
whisperx = None

if HF_TOKEN:
    try:
        import whisperx as _whisperx
        whisperx = _whisperx
        from whisperx.diarize import DiarizationPipeline
        diarize_pipeline = DiarizationPipeline(use_auth_token=HF_TOKEN, device="cuda")
        logger.info("Diarization pipeline loaded successfully")
    except Exception as e:
        logger.warning("Failed to load diarization pipeline: %s", e)
        diarize_pipeline = None
else:
    try:
        import whisperx as _whisperx
        whisperx = _whisperx
    except ImportError:
        whisperx = None
    logger.info("HF_TOKEN not set -- diarization unavailable")


# ---------------------------------------------------------------------------
# Diarization helper
# ---------------------------------------------------------------------------
def _process_diarization(audio_path, segments, job_input):
    """
    Apply speaker diarization to transcribed segments.

    If diarize_pipeline is None, returns a warning message explaining
    the HF_TOKEN requirement. Otherwise, runs WhisperX diarization
    and assigns speaker labels.

    Returns:
        dict with either speaker-labeled segments or a warning.
    """
    if diarize_pipeline is None:
        return {
            "diarization_warning": (
                "Diarization requested but unavailable. "
                "Set HF_TOKEN environment variable and accept the user agreement "
                "for pyannote/speaker-diarization-3.1 at "
                "https://huggingface.co/pyannote/speaker-diarization-3.1"
            ),
        }

    # Load audio for whisperx
    audio = whisperx.load_audio(audio_path)

    # Build diarization kwargs
    diarize_kwargs = {}
    min_speakers = job_input.get("min_speakers")
    max_speakers = job_input.get("max_speakers")
    if min_speakers is not None:
        diarize_kwargs["min_speakers"] = min_speakers
    if max_speakers is not None:
        diarize_kwargs["max_speakers"] = max_speakers

    # Run diarization
    diarize_result = diarize_pipeline(audio, **diarize_kwargs)

    # Assign speakers to segments
    result = whisperx.assign_word_speakers(diarize_result, {"segments": segments})

    return {"segments": result["segments"]}


# ---------------------------------------------------------------------------
# Single audio processing
# ---------------------------------------------------------------------------
def _process_single(job_input):
    """
    Process a single audio transcription request.

    Handles resolve -> transcribe -> diarize (optional) -> format -> cleanup.
    """
    audio_path = None
    try:
        audio_path = resolve_audio_input(job_input)

        # Extract parameters
        language = job_input.get("language")
        task = job_input.get("task", "transcribe")
        word_timestamps = job_input.get("word_timestamps", True)
        output_format = job_input.get("output_format", "json")
        diarize = job_input.get("diarize", False)
        beam_size = job_input.get("beam_size", 5)
        temperature = job_input.get("temperature", 0.0)

        # Transcribe
        result = transcribe_audio(
            model,
            audio_path,
            language=language,
            task=task,
            word_timestamps=word_timestamps,
            beam_size=beam_size,
            temperature=temperature,
        )

        # Diarization (optional)
        if diarize:
            diarize_result = _process_diarization(audio_path, result["segments"], job_input)
            if "diarization_warning" in diarize_result:
                result["diarization_warning"] = diarize_result["diarization_warning"]
            elif "segments" in diarize_result:
                result["segments"] = diarize_result["segments"]

        # Output format conversion
        if output_format == "text":
            result["text"] = segments_to_text(result["segments"])
        elif output_format == "srt":
            result["srt"] = segments_to_srt(result["segments"])
        elif output_format == "vtt":
            result["vtt"] = segments_to_vtt(result["segments"])

        return result

    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Transcription failed: {str(e)}"}
    finally:
        if audio_path:
            cleanup_audio(audio_path)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------
def _process_batch(job_input):
    """
    Process multiple audio URLs in a single job.

    Extracts shared parameters (language, output_format, etc.) and applies
    them to each audio URL individually.
    """
    audio_urls = job_input.get("audio_urls", [])
    results = []

    # Extract shared parameters (everything except audio_urls)
    shared_params = {k: v for k, v in job_input.items() if k != "audio_urls"}

    for url in audio_urls:
        single_input = {"audio_url": url, **shared_params}
        result = _process_single(single_input)
        results.append(result)

    return {"results": results}


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------
def handler(job):
    """
    RunPod handler entry point.

    Routes to batch or single processing based on input keys.

    Input formats:
    - Single: {"audio_url": "..."} or {"audio_base64": "..."}
    - Batch: {"audio_urls": ["...", "..."]}

    Optional parameters:
    - language: Language code (e.g., "en"), None for auto-detect
    - task: "transcribe" or "translate"
    - output_format: "json", "text", "srt", "vtt"
    - diarize: Boolean, requires HF_TOKEN
    - min_speakers / max_speakers: For diarization
    - beam_size: Beam size for decoding (default 5)
    - temperature: Sampling temperature (default 0.0)
    """
    job_input = job["input"]

    if "audio_urls" in job_input:
        return _process_batch(job_input)

    return _process_single(job_input)


# ---------------------------------------------------------------------------
# RunPod serverless start
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import runpod
    runpod.serverless.start({"handler": handler})
