# Phase 4: Voice Cloning Worker - Research

**Researched:** 2026-03-14
**Domain:** Zero-shot voice cloning via Chatterbox TTS on RunPod Serverless
**Confidence:** HIGH

## Summary

Phase 4 delivers a standalone RunPod serverless worker (`worker-voice-clone/`) that accepts a short reference audio clip plus text and synthesizes new speech in the cloned voice. The engine is Chatterbox TTS (MIT license, Resemble AI), which supports zero-shot voice cloning from as little as 5 seconds of reference audio. Chatterbox has three model variants -- Turbo (350M params, English-only, fastest), Original (500M, English, emotion control), and Multilingual (500M, 23 languages, cross-lingual transfer) -- all of which can clone voices. The Multilingual variant directly satisfies requirement VC-02 (cross-lingual synthesis) without needing GPT-SoVITS.

The critical technical challenge is that voice cloning quality degrades silently on bad reference audio -- the model never errors, it just produces garbage. Reference audio validation (duration, sample rate, SNR) must run before any GPU compute. The output sample rate from Chatterbox is natively 24kHz; to meet VC-04 (48kHz output), the worker must upsample via `torchaudio.functional.resample()`. MP3 encoding requires ffmpeg (already in the Dockerfile template).

**Primary recommendation:** Use Chatterbox Multilingual as the default model variant (covers 23 languages including cross-lingual voice transfer), with Chatterbox Turbo as a speed preset for English-only use cases. Copy the established worker-template/worker-whisper patterns verbatim for project structure, then customize for voice cloning specifics.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VC-01 | Zero-shot voice cloning from 5-30s reference audio | Chatterbox supports zero-shot cloning via `audio_prompt_path` parameter; 5-20s reference optimal |
| VC-02 | Cross-lingual synthesis (multiple languages) | Chatterbox Multilingual supports 23 languages with cross-lingual voice transfer; `language_id` parameter selects target language |
| VC-03 | Reference audio quality validation (duration, sample rate, SNR) | Implement validate_reference.py with numpy-based SNR estimation, soundfile for duration/sample rate checks |
| VC-04 | 48kHz output in WAV and MP3 formats | Chatterbox outputs 24kHz natively; upsample via torchaudio.functional.resample(); MP3 via ffmpeg subprocess |
| VC-05 | Published to RunPod Hub with GPU presets | Follow hub.json pattern from worker-whisper; Turbo on T4, Multilingual on A4000 |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| chatterbox-tts | 0.1.6 | Voice cloning + TTS engine | MIT license, Resemble AI backed, 3 model variants, zero-shot from 5s audio, 23 languages (multilingual). Only commercial-safe open-source voice cloning option. |
| torch | >=2.4.0 | Deep learning runtime | Required by Chatterbox. Pin with CUDA 12.4 wheel index. |
| torchaudio | >=2.4.0 | Audio resampling (24kHz to 48kHz), audio I/O | `torchaudio.functional.resample()` for quality upsampling; `torchaudio.save()` for output. |
| runpod | >=1.7.0 | Serverless handler framework | Same SDK pattern as all other workers. |
| soundfile | >=0.12.0 | Audio I/O for validation and output encoding | Read reference audio metadata (sample rate, duration) without loading full waveform. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | >=1.24.0 | Audio array manipulation, SNR estimation | Reference audio validation; always used |
| huggingface-hub | >=0.25.0 | Model downloading | Chatterbox downloads weights from HF hub on first load via `from_pretrained()` |
| requests | >=2.31.0 | HTTP client for URL input | Audio URL download, same as all workers |
| ffmpeg | system package | MP3 encoding | Required for WAV-to-MP3 conversion; install via `apt-get` in Dockerfile |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Chatterbox | GPT-SoVITS v4 | Better few-shot quality, more languages natively, but complex install, CUDA 12.4 compatibility unverified, non-trivial API, large footprint. Deferred to v2 (VC-06). |
| Chatterbox | F5-TTS | Superior zero-shot cloning quality, but CC-BY-NC-4.0 model license prevents commercial use. Hard blocker. |
| Chatterbox | XTTS-v2 | Coqui shut down Jan 2024, no commercial license available. Dead project. |
| torchaudio resample | scipy.signal.resample | scipy works but torchaudio runs on GPU if needed, already a dependency, higher quality Kaiser window option. |

**Installation:**
```bash
# System deps in Dockerfile
apt-get install -y ffmpeg libsndfile1

# Python packages (order matters)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install chatterbox-tts>=0.1.6 runpod>=1.7.0 huggingface-hub>=0.25.0 soundfile>=0.12.0 numpy>=1.24.0 requests>=2.31.0
```

## Architecture Patterns

### Recommended Project Structure
```
worker-voice-clone/
  handler.py              # RunPod handler: route, validate, synthesize, encode
  voice_clone.py          # Chatterbox wrapper: load model, generate with cloning
  validate_reference.py   # Reference audio validation: duration, sample rate, SNR
  download_model.py       # Copied from worker-template (verbatim)
  audio_utils.py          # Copied from worker-template (verbatim)
  requirements.txt        # Python dependencies
  Dockerfile              # CUDA 12.4 runtime + chatterbox-tts
  pyproject.toml          # Project metadata + pytest config
  test_input.json         # RunPod local test input
  .runpod/
    hub.json              # RunPod Hub presets (Turbo T4, Multilingual A4000)
  tests/
    __init__.py
    conftest.py           # Shared fixtures (mock Chatterbox model, sample audio)
    test_validate_reference.py
    test_voice_clone.py
    test_handler.py
    test_hub.py
```

### Pattern 1: Chatterbox Model Loading at Startup

**What:** Load Chatterbox model once at module level, keep GPU-resident across requests.
**When to use:** Always -- matches the established worker pattern (faster-whisper in worker-whisper, Kokoro in TTS worker).

```python
# Source: Chatterbox GitHub README + worker-whisper handler.py pattern
import os
import logging
import torch

logger = logging.getLogger(__name__)

if "PYTORCH_CUDA_ALLOC_CONF" not in os.environ:
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

MODEL_VARIANT = os.environ.get("MODEL_VARIANT", "multilingual")  # turbo | original | multilingual

try:
    if MODEL_VARIANT == "turbo":
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        model = ChatterboxTurboTTS.from_pretrained(device="cuda")
    elif MODEL_VARIANT == "multilingual":
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
    else:
        from chatterbox.tts import ChatterboxTTS
        model = ChatterboxTTS.from_pretrained(device="cuda")
    logger.info("Loaded Chatterbox %s on CUDA", MODEL_VARIANT)
except Exception as e:
    logger.error("Failed to load Chatterbox model: %s", e)
    model = None
```

### Pattern 2: Voice Cloning Inference

**What:** Generate speech from text using a reference audio clip for voice cloning.
**When to use:** Every voice cloning request.

```python
# Source: Chatterbox GitHub README
import torchaudio as ta

def clone_voice(model, text, reference_audio_path, language_id="en",
                exaggeration=0.5, cfg_weight=0.5, temperature=0.8):
    """Generate speech cloning the voice from reference audio."""
    kwargs = {"audio_prompt_path": reference_audio_path}

    # Multilingual model accepts language_id
    if hasattr(model, 'generate') and language_id:
        kwargs["language_id"] = language_id

    # Original/Multilingual models accept emotion controls
    if exaggeration is not None:
        kwargs["exaggeration"] = exaggeration
    if cfg_weight is not None:
        kwargs["cfg_weight"] = cfg_weight

    wav = model.generate(text, **kwargs)
    sample_rate = model.sr  # 24000 Hz native
    return wav, sample_rate
```

### Pattern 3: Output Audio Encoding with Upsampling

**What:** Upsample Chatterbox 24kHz output to 48kHz and encode as WAV or MP3.
**When to use:** Every response that needs 48kHz output (VC-04 requirement).

```python
# Source: torchaudio docs + worker-template audio_utils.py
import torchaudio.functional as F
import subprocess
import tempfile
import base64
from io import BytesIO
import soundfile as sf

def encode_output(wav_tensor, native_sr, output_format="wav", target_sr=48000):
    """Encode audio tensor to base64 with optional upsampling."""
    # Upsample from 24kHz to 48kHz
    if target_sr != native_sr:
        wav_tensor = F.resample(wav_tensor, native_sr, target_sr)

    # Move to CPU numpy
    audio_np = wav_tensor.squeeze().cpu().numpy()

    if output_format == "mp3":
        return _encode_mp3(audio_np, target_sr)
    else:
        return _encode_wav(audio_np, target_sr)

def _encode_wav(audio_np, sample_rate):
    buf = BytesIO()
    sf.write(buf, audio_np, sample_rate, format="wav")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8"), "wav"

def _encode_mp3(audio_np, sample_rate):
    """Encode via ffmpeg subprocess (ffmpeg is in the Docker image)."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
        sf.write(tmp_wav.name, audio_np, sample_rate, format="wav")
        tmp_wav_path = tmp_wav.name

    tmp_mp3_path = tmp_wav_path.replace(".wav", ".mp3")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_wav_path, "-codec:a", "libmp3lame",
             "-qscale:a", "2", tmp_mp3_path],
            capture_output=True, check=True
        )
        with open(tmp_mp3_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8"), "mp3"
    finally:
        for p in [tmp_wav_path, tmp_mp3_path]:
            try:
                os.unlink(p)
            except OSError:
                pass
```

### Pattern 4: Reference Audio Validation

**What:** Validate reference audio before GPU inference to prevent garbage output.
**When to use:** Every request, before calling the model.

```python
# Source: Research pitfalls (Pitfall 6), Fish Audio voice cloning guide
import numpy as np
import soundfile as sf

MIN_DURATION_SECONDS = 5.0
MAX_DURATION_SECONDS = 60.0
MIN_SAMPLE_RATE = 16000
MIN_SNR_DB = 15.0  # Conservative threshold

def validate_reference_audio(audio_path):
    """
    Validate reference audio for voice cloning quality.

    Returns:
        dict with validation result and quality metrics.
    Raises:
        ValueError with actionable message on validation failure.
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
        audio_data = audio_data[:, 0]  # mono
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

def _estimate_snr(audio, frame_length=2048, silence_threshold_percentile=10):
    """
    Estimate SNR using energy-based method.

    Assumes lowest-energy frames are noise, highest-energy frames are signal.
    """
    # Frame the audio
    n_frames = len(audio) // frame_length
    if n_frames < 2:
        return 0.0

    frames = audio[:n_frames * frame_length].reshape(n_frames, frame_length)
    frame_energy = np.mean(frames ** 2, axis=1)
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
```

### Anti-Patterns to Avoid

- **Skipping reference audio validation:** The model never errors on bad input. It silently produces garbage. Always validate before inference.
- **Returning 24kHz output without upsampling:** VC-04 requires 48kHz. Chatterbox natively outputs 24kHz. Must upsample.
- **Baking Chatterbox model weights into Docker image:** Chatterbox downloads weights via `from_pretrained()` from HuggingFace Hub. The weights are ~2-3GB. Let them download at startup and cache on `/runpod-volume`.
- **Using `from_pretrained()` without volume caching:** Chatterbox auto-downloads to `~/.cache/huggingface/` which is ephemeral in containers. Set `HF_HOME=/runpod-volume/.cache/huggingface` to persist across cold starts.
- **Ignoring language_id for Multilingual variant:** Without `language_id`, the Multilingual model may produce incorrect pronunciation. Always require it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Audio resampling (24kHz to 48kHz) | Custom interpolation | `torchaudio.functional.resample()` with Kaiser window | Resampling has non-trivial aliasing edge cases; torchaudio uses vetted DSP algorithms |
| MP3 encoding | Python-based MP3 encoder | ffmpeg subprocess | ffmpeg is already in the Dockerfile, battle-tested, handles edge cases (VBR, metadata) |
| SSRF protection | Custom URL validator | `audio_utils._validate_url()` from worker-template | Already implemented and tested in Phase 1 |
| Audio input resolution (URL/base64) | New resolver | `audio_utils.resolve_audio_input()` from worker-template | Proven pattern, handles content-type detection, streaming download |
| Speaker embedding extraction | Custom embedding pipeline | (Defer to v2 -- VC-09) | Adds complexity without v1 value; let users re-upload reference audio |
| SNR estimation | Full scipy signal processing | Numpy energy-based method (see Pattern 4) | Simple, no extra dependencies, sufficient for threshold-based gating |

**Key insight:** Voice cloning input validation is the most critical hand-build in this worker. Everything else -- audio I/O, model download, SSRF protection, output encoding -- is already solved by Phase 1 utilities or standard libraries.

## Common Pitfalls

### Pitfall 1: Voice Cloning Quality Collapses Silently on Bad Reference Audio
**What goes wrong:** Users submit noisy, too-short, or multi-speaker reference clips. Chatterbox runs without error but produces robotic, unintelligible, or wrong-voice output. Users blame the service.
**Why it happens:** Chatterbox accepts any audio tensor for speaker embedding extraction. No built-in quality gate.
**How to avoid:** Run `validate_reference_audio()` before every inference call. Reject clips under 5s, over 60s, below 16kHz, or with estimated SNR < 15dB. Return actionable error messages.
**Warning signs:** No validation code in handler, tests only use clean reference audio.

### Pitfall 2: Chatterbox Native 24kHz Output vs 48kHz Requirement
**What goes wrong:** VC-04 requires 48kHz output. Chatterbox `model.sr` returns 24000. If you save output at 24kHz and call it "48kHz", users get wrong-pitch audio when their player assumes 48kHz.
**Why it happens:** Chatterbox was designed for 24kHz output. The requirement comes from matching commercial-quality standards (ElevenLabs outputs 44.1/48kHz).
**How to avoid:** Use `torchaudio.functional.resample(wav, 24000, 48000)` with Kaiser window. This is a clean 2x upsample (integer ratio) which avoids aliasing. Include the actual sample rate in the response metadata.
**Warning signs:** Response says 48kHz but audio was saved at 24kHz without resampling.

### Pitfall 3: Chatterbox Model Download on Every Cold Start
**What goes wrong:** Chatterbox `from_pretrained()` downloads model weights (~2GB) from HuggingFace Hub to `~/.cache/huggingface/` by default. In a Docker container without volume, this happens on every cold start, adding 30-60s.
**Why it happens:** Default HF cache directory is not on the RunPod network volume.
**How to avoid:** Set `HF_HOME=/runpod-volume/.cache/huggingface` in the Dockerfile ENV block. Chatterbox uses the standard HuggingFace Hub cache path. On first start it downloads; on subsequent cold starts with the same volume, it uses the cache.
**Warning signs:** Cold start consistently takes 60s+ even with volume attached.

### Pitfall 4: GPU Memory Not Released Between Requests
**What goes wrong:** VRAM grows across requests as Chatterbox creates variable-length tensors per generation.
**Why it happens:** PyTorch CUDA allocator fragments memory. Different text lengths produce different tensor sizes.
**How to avoid:** Call `torch.cuda.empty_cache()` after every request (in `finally` block). Set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`. Log VRAM usage per request with `torch.cuda.memory_allocated()`.
**Warning signs:** Worker handles first 20 requests fine, then OOM on request 21+.

### Pitfall 5: Cross-Lingual Accent Bleed
**What goes wrong:** When using Chatterbox Multilingual for cross-lingual synthesis, the output inherits the accent of the reference clip's language. E.g., cloning an English voice to speak French produces French with a noticeable English accent.
**Why it happens:** The speaker embedding captures prosodic patterns from the reference language. This is inherent to the architecture.
**How to avoid:** Document the behavior clearly: "Cross-lingual output preserves speaker identity but may retain accent characteristics from the reference language." Suggest setting `cfg_weight=0` to reduce accent transfer (per Chatterbox docs). Return `reference_language_note` in response when `language_id` differs from detected reference language.
**Warning signs:** Users expect perfect native pronunciation in target language from cross-lingual cloning.

## Code Examples

### Complete Handler Structure
```python
# Source: worker-whisper handler.py pattern + Chatterbox API
"""
RunPod Serverless handler for voice cloning.
"""
import logging
import os
import torch
from audio_utils import resolve_audio_input, cleanup_audio
from validate_reference import validate_reference_audio
from voice_clone import load_model, clone_voice, encode_output

logger = logging.getLogger(__name__)

if "PYTORCH_CUDA_ALLOC_CONF" not in os.environ:
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# Set HF cache to volume for persistent model storage
if os.path.isdir("/runpod-volume"):
    os.environ.setdefault("HF_HOME", "/runpod-volume/.cache/huggingface")

MODEL_VARIANT = os.environ.get("MODEL_VARIANT", "multilingual")
model = load_model(MODEL_VARIANT)

def handler(job):
    job_input = job["input"]
    ref_path = None
    try:
        # Require text
        text = job_input.get("text")
        if not text or not text.strip():
            return {"error": "Required field 'text' is missing or empty."}

        # Resolve reference audio
        ref_input = {}
        if "reference_audio_url" in job_input:
            ref_input["audio_url"] = job_input["reference_audio_url"]
        elif "reference_audio_base64" in job_input:
            ref_input["audio_base64"] = job_input["reference_audio_base64"]
        else:
            return {"error": "Provide 'reference_audio_url' or 'reference_audio_base64'."}

        ref_path = resolve_audio_input(ref_input)

        # Validate reference audio quality (VC-03)
        quality = validate_reference_audio(ref_path)

        # Extract generation parameters
        language_id = job_input.get("language", "en")
        output_format = job_input.get("output_format", "wav")
        exaggeration = job_input.get("exaggeration", 0.5)
        cfg_weight = job_input.get("cfg_weight", 0.5)

        # Generate cloned speech (VC-01, VC-02)
        wav, native_sr = clone_voice(
            model, text, ref_path,
            language_id=language_id,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
        )

        # Encode output at 48kHz (VC-04)
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
```

### hub.json Preset Pattern
```json
{
  "name": "Voice Cloning Worker",
  "description": "Zero-shot voice cloning from 5-30s reference audio. Clone any voice and generate speech in 23 languages. Powered by Chatterbox TTS (MIT license).",
  "category": "voice-cloning",
  "presets": [
    {
      "name": "Voice Clone - Turbo (English)",
      "description": "Fast English voice cloning with Chatterbox Turbo. 350M params, optimized for speed. Supports paralinguistic tags ([laugh], [cough]).",
      "env": {
        "MODEL_VARIANT": "turbo",
        "MODEL_NAME": "voice-clone-turbo"
      },
      "gpu": "NVIDIA T4",
      "volume_size": 10
    },
    {
      "name": "Voice Clone - Multilingual (23 languages)",
      "description": "Cross-lingual voice cloning with Chatterbox Multilingual. 500M params. Clone a voice in one language, generate speech in any of 23 languages.",
      "env": {
        "MODEL_VARIANT": "multilingual",
        "MODEL_NAME": "voice-clone-multilingual"
      },
      "gpu": "NVIDIA RTX A4000",
      "volume_size": 10
    },
    {
      "name": "Voice Clone - Original (English, Emotion Control)",
      "description": "English voice cloning with emotion/expressiveness control. 500M params. Adjust exaggeration and cfg_weight for creative voice generation.",
      "env": {
        "MODEL_VARIANT": "original",
        "MODEL_NAME": "voice-clone-original"
      },
      "gpu": "NVIDIA RTX A4000",
      "volume_size": 10
    }
  ]
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| XTTS-v2 (Coqui) for voice cloning | Chatterbox TTS (Resemble AI) | Coqui shut down Jan 2024 | XTTS-v2 is commercially dead; Chatterbox is MIT-licensed replacement |
| GPT-SoVITS for multilingual cloning | Chatterbox Multilingual | Dec 2025 (v0.1.6) | Chatterbox Multilingual covers 23 languages without GPT-SoVITS complexity |
| Separate cloning + TTS models | Single Chatterbox model | Jun 2025 (v0.1.0) | One model handles both TTS and voice cloning; simpler deployment |
| F5-TTS for zero-shot cloning | Chatterbox for commercial use | Ongoing | F5-TTS has superior quality but CC-BY-NC license blocks commercial deployment |

**Deprecated/outdated:**
- **XTTS-v2**: Coqui Public Model License, company shut down. Cannot be used commercially.
- **Bark (Suno)**: Surpassed by 2025 models. Slow inference, high VRAM, lower quality.
- **OpenVoice v2**: Known GPU driver incompatibilities, less active development.

## Chatterbox API Reference

### Model Variants

| Variant | Import | Class | Params | VRAM | Languages | Special Features |
|---------|--------|-------|--------|------|-----------|-----------------|
| Turbo | `chatterbox.tts_turbo` | `ChatterboxTurboTTS` | 350M | ~4.5GB | English only | Paralinguistic tags: [laugh], [cough], [chuckle] |
| Original | `chatterbox.tts` | `ChatterboxTTS` | 500M | ~8GB | English only | Emotion control (exaggeration, cfg_weight) |
| Multilingual | `chatterbox.mtl_tts` | `ChatterboxMultilingualTTS` | 500M | ~8GB | 23 languages | Cross-lingual voice transfer, language_id param |

### Supported Languages (Multilingual)

Arabic (ar), Chinese (zh), Danish (da), Dutch (nl), English (en), Finnish (fi), French (fr), German (de), Greek (el), Hebrew (he), Hindi (hi), Italian (it), Japanese (ja), Korean (ko), Malay (ms), Norwegian (no), Polish (pl), Portuguese (pt), Russian (ru), Spanish (es), Swedish (sv), Swahili (sw), Turkish (tr)

### Generation Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `audio_prompt_path` | None | file path | Path to reference audio for voice cloning (5-20s recommended) |
| `language_id` | "en" | ISO 639-1 | Target language (Multilingual variant only) |
| `exaggeration` | 0.5 | 0.0-1.0 | Speech expressiveness; higher = more dramatic |
| `cfg_weight` | 0.5 | 0.0-1.0 | Voice similarity adherence; lower = closer to reference |
| `temperature` | 0.8 | 0.0+ | Sampling randomness; lower = more stable output |

### Output Properties

| Property | Value |
|----------|-------|
| Output type | PyTorch tensor |
| Native sample rate | 24000 Hz (`model.sr`) |
| Channels | Mono |
| Save method | `torchaudio.save("out.wav", wav, model.sr)` |

## Open Questions

1. **Chatterbox Multilingual cross-lingual quality**
   - What we know: Chatterbox supports 23 languages with cross-lingual voice transfer. Reference clip accent may bleed into output.
   - What's unclear: Actual output quality for non-English languages (especially CJK). No independent benchmarks found.
   - Recommendation: Implement cross-lingual as a supported feature per VC-02, but document accent-bleed caveat. Quality is acceptable for v1; refine with user feedback.

2. **Chatterbox model download path vs download_model.py**
   - What we know: Chatterbox uses `from_pretrained()` which auto-downloads via HuggingFace Hub. Our `download_model.py` manually downloads files.
   - What's unclear: Whether we should use `download_model.py` or let Chatterbox handle its own downloads.
   - Recommendation: Let Chatterbox handle its own model download via `from_pretrained()`. Just set `HF_HOME` to `/runpod-volume/.cache/huggingface` for caching. The `download_model.py` utility is not needed for this worker's model loading (but `audio_utils.py` is still needed for input handling).

3. **Exact VRAM usage per variant under load**
   - What we know: Turbo ~4.5GB, Original/Multilingual ~8GB based on web sources.
   - What's unclear: Peak VRAM during generation (text length affects tensor sizes). Whether T4 (16GB) can run Multilingual.
   - Recommendation: Default Turbo to T4 (safe), Multilingual/Original to A4000. Verify with actual testing during implementation.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 7.0 |
| Config file | pyproject.toml (same pattern as worker-whisper) |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VC-01 | Zero-shot voice cloning from reference audio | unit (mocked model) | `python -m pytest tests/test_voice_clone.py -x` | Wave 0 |
| VC-02 | Cross-lingual synthesis with language_id | unit (mocked model) | `python -m pytest tests/test_voice_clone.py::test_multilingual -x` | Wave 0 |
| VC-03 | Reference audio validation (duration, SR, SNR) | unit | `python -m pytest tests/test_validate_reference.py -x` | Wave 0 |
| VC-04 | 48kHz output in WAV and MP3 | unit | `python -m pytest tests/test_voice_clone.py::test_output_48khz -x` | Wave 0 |
| VC-05 | hub.json presets with GPU specs | unit (JSON schema) | `python -m pytest tests/test_hub.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/conftest.py` -- shared fixtures (mock Chatterbox model returning tensor, sample audio bytes)
- [ ] `tests/test_validate_reference.py` -- covers VC-03 (validation logic)
- [ ] `tests/test_voice_clone.py` -- covers VC-01, VC-02, VC-04 (model wrapper + output encoding)
- [ ] `tests/test_handler.py` -- covers handler routing, error paths, VRAM cleanup
- [ ] `tests/test_hub.py` -- covers VC-05 (hub.json schema validation)
- [ ] `pyproject.toml` -- pytest config (testpaths, pythonpath)

## Sources

### Primary (HIGH confidence)
- [Chatterbox GitHub (resemble-ai/chatterbox)](https://github.com/resemble-ai/chatterbox) -- API, model variants, generation parameters, MIT license confirmed
- [chatterbox-tts PyPI v0.1.6](https://pypi.org/project/chatterbox-tts/) -- Latest version (Dec 2025), Python >=3.10 requirement
- [Chatterbox Multilingual announcement (Resemble AI)](https://www.resemble.ai/introducing-chatterbox-multilingual-open-source-tts-for-23-languages/) -- 23 languages, cross-lingual voice transfer
- [torchaudio resampling docs](https://docs.pytorch.org/audio/stable/tutorials/audio_resampling_tutorial.html) -- Kaiser window resampling for quality upsampling
- [worker-whisper handler.py](worker-whisper/handler.py) -- Established handler pattern (module-level model load, CUDA cleanup, error handling)
- [worker-template audio_utils.py](worker-template/audio_utils.py) -- Proven audio I/O utilities (SSRF protection, URL/base64 input)

### Secondary (MEDIUM confidence)
- [Chatterbox TTS Server (devnen)](https://github.com/devnen/Chatterbox-TTS-Server) -- Community deployment patterns, VRAM observations
- [DigitalOcean Chatterbox Tutorial](https://www.digitalocean.com/community/tutorials/resemble-chatterbox-tts-text-to-speech) -- Voice cloning usage examples
- [Chatterbox TTS API (travisvn)](https://github.com/travisvn/chatterbox-tts-api) -- OpenAI-compatible API patterns, 22-language support confirmed
- [Fish Audio Voice Cloning Guide](https://fish.audio/blog/voice-cloning-guide/) -- Reference audio quality requirements (general, not Chatterbox-specific)

### Tertiary (LOW confidence)
- Chatterbox VRAM figures (Turbo ~4.5GB, Original ~8GB) -- sourced from community reports, not official benchmarks. Verify during implementation.
- SNR threshold of 15dB for reference audio -- based on general voice cloning best practices, not Chatterbox-specific validation. May need tuning.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- Chatterbox is the clear choice (MIT license, only commercial-safe option, well-documented API)
- Architecture: HIGH -- Follows proven patterns from worker-whisper and worker-template
- Pitfalls: HIGH -- Voice cloning quality collapse on bad reference audio is well-documented across all cloning engines
- Cross-lingual: MEDIUM -- Chatterbox Multilingual supports 23 languages but quality per language unverified by independent benchmarks

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (30 days -- Chatterbox is actively maintained but API is stable at v0.1.6)
