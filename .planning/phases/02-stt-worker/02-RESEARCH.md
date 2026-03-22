# Phase 2: STT Worker - Research

**Researched:** 2026-03-14
**Domain:** Speech-to-Text inference with faster-whisper + WhisperX on RunPod Serverless
**Confidence:** HIGH

## Summary

The STT worker is the most straightforward audio worker to build: audio-in, JSON-out, no audio encoding on output. The technology stack is settled -- faster-whisper is the de facto standard STT engine (RunPod's own official worker uses it), WhisperX adds speaker diarization and forced alignment on top. The key differentiator over RunPod's official `worker-faster_whisper` is speaker diarization via WhisperX + pyannote-audio, which the official worker completely lacks.

The worker will be a new directory `worker-whisper/` that copies the Phase 1 template (`worker-template/`) and adds STT-specific code. The template already provides `download_model.py`, `audio_utils.py` (with SSRF protection, URL/base64 input, audio output encoding), and a slim Dockerfile pattern. This phase adds: faster-whisper model loading, transcription with word-level timestamps, SRT/VTT/plain-text output formatting, WhisperX-based diarization (with graceful degradation when HF_TOKEN is absent), batch transcription, and hub.json presets.

The primary risks are: (1) WhisperX dependency conflicts with faster-whisper (well-documented, solvable by installing faster-whisper before whisperx), (2) pyannote-audio's gated model requirement (HF_TOKEN must be present, worker must degrade gracefully without it), (3) Whisper hallucinations on long audio without VAD (solved by enabling `vad_filter=True` by default), and (4) Docker image bloat from PyTorch + WhisperX dependencies (target under 8GB by not baking models).

**Primary recommendation:** Use faster-whisper as the core transcription engine with WhisperX as an optional diarization layer. Load faster-whisper model at startup, use WhisperX only when diarization is requested and HF_TOKEN is available. Keep the two concerns separate in the handler.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STT-01 | Transcribe audio using faster-whisper with selectable model sizes (turbo, large-v3) | faster-whisper WhisperModel accepts model_size parameter; turbo and large-v3 are both supported. Model selected via HF_REPO_ID env var or MODEL_SIZE env var. INT8 quantization fits turbo on T4. |
| STT-02 | Transcription output includes word-level timestamps | faster-whisper natively supports `word_timestamps=True` in transcribe(). Each Segment has a `.words` list with Word objects containing `.start`, `.end`, `.word`, `.probability`. |
| STT-03 | Output in plain text, SRT, or VTT subtitle formats | Trivial format conversion from faster-whisper segments. SRT/VTT are simple text formats with timestamp formatting. No external library needed -- implement as utility functions. |
| STT-04 | Auto-detect spoken language across 50+ languages | Built into faster-whisper: `transcribe()` returns `TranscriptionInfo` with `.language` and `.language_probability`. Whisper supports 99 languages natively. |
| STT-05 | Translate non-English audio to English text | faster-whisper supports `task="translate"` parameter in transcribe(). Native Whisper capability, zero additional code. |
| STT-06 | VAD enabled by default to prevent hallucination | faster-whisper supports `vad_filter=True` with Silero VAD. Enable by default, expose as parameter for override. Critical for production quality on long audio. |
| STT-07 | Speaker diarization via WhisperX + pyannote | WhisperX 3.8.2 provides DiarizationPipeline wrapping pyannote/speaker-diarization-3.1. Requires HF_TOKEN for gated model access. Must degrade gracefully when token absent. |
| STT-08 | Batch processing -- multiple audio files per job | Accept `audio_urls` array in input. Process sequentially, return array of results. Use faster-whisper BatchedInferencePipeline for per-file batched segment processing. |
| STT-09 | Published to RunPod Hub with model presets in hub.json | hub.json schema established in template. Create presets: turbo on T4 (INT8, ~3GB VRAM), large-v3 on A4000 (FP16, ~10GB VRAM). |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| faster-whisper | >=1.2.1 | Core STT inference engine | 4x faster than OpenAI Whisper, CTranslate2 INT8 quantization, RunPod's own official worker uses it. Battle-tested. |
| whisperx | >=3.8.2 | Diarization + forced alignment layer | Wraps faster-whisper + pyannote-audio + wav2vec2 alignment. The standard way to add diarization to faster-whisper. Latest stable release on PyPI. |
| pyannote-audio | >=3.3.2 | Speaker diarization engine (WhisperX dependency) | pyannote/speaker-diarization-3.1 model. Pure PyTorch (no onnxruntime). Requires HF_TOKEN for gated model access. |
| CTranslate2 | >=4.5.0 | Inference runtime (faster-whisper dependency) | CUDA 12.3+ and cuDNN 9 compatible. Handles GPU kernel optimization and INT8 quantization. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| runpod | >=1.7.0 | Serverless handler framework | Always -- same SDK as all workers |
| huggingface-hub | >=0.25.0 | Model downloading | Always -- download_model.py pattern |
| torch | >=2.4.0 | PyTorch runtime (WhisperX/pyannote dependency) | Required for diarization pipeline |
| torchaudio | >=2.4.0 | Audio loading/resampling (WhisperX dependency) | Required for WhisperX alignment |
| soundfile | >=0.12.0 | Audio I/O | Already in template |
| numpy | >=1.24.0 | Array manipulation | Already in template |
| requests | >=2.31.0 | HTTP client | Already in template |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| WhisperX for diarization | Direct pyannote-audio integration | WhisperX handles the word-to-speaker alignment automatically; doing it manually is error-prone and requires reimplementing forced alignment |
| WhisperX for diarization | NeMo-based whisper-diarization | Adds NVIDIA NeMo as heavy dependency; less mature than WhisperX for this use case |
| faster-whisper | insanely-fast-whisper | Better for batch throughput but higher per-request latency and more VRAM; worse for serverless cold-start pattern |
| faster-whisper | whisper.cpp | C++ binary (like llama.cpp pattern) but CUDA support less mature than CTranslate2; Python ecosystem integration harder |

**Installation:**

```bash
# System dependencies (in Dockerfile)
apt-get install -y ffmpeg libsndfile1

# Install PyTorch with CUDA 12.4 first
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# Install faster-whisper BEFORE whisperx (avoids dependency conflicts)
pip install faster-whisper>=1.2.1

# Install whisperx (pulls pyannote-audio, wav2vec2 alignment models)
pip install whisperx>=3.8.2

# Install remaining worker dependencies
pip install runpod>=1.7.0 huggingface-hub>=0.25.0 requests>=2.31.0 soundfile>=0.12.0 numpy>=1.24.0
```

**Critical installation order:** Install `faster-whisper` before `whisperx` to avoid dependency resolution conflicts. This is a well-documented workaround for pip resolution issues between the two packages.

## Architecture Patterns

### Recommended Project Structure

```
worker-whisper/
├── handler.py           # RunPod handler: model loading, dispatch, transcription
├── transcribe.py        # Core transcription logic (faster-whisper + WhisperX)
├── format_output.py     # SRT/VTT/plain-text formatting utilities
├── download_model.py    # Copied from worker-template (model download with caching)
├── audio_utils.py       # Copied from worker-template (audio I/O, SSRF protection)
├── requirements.txt     # Pinned dependencies
├── Dockerfile           # Single-stage, nvidia/cuda:12.4.1-runtime base
├── test_input.json      # Test payloads for local development
├── .runpod/
│   └── hub.json         # RunPod Hub presets (turbo on T4, large-v3 on A4000)
└── tests/
    ├── conftest.py      # Test fixtures
    ├── test_transcribe.py    # Transcription unit tests
    ├── test_format_output.py # Output format tests
    └── test_handler.py       # Handler integration tests
```

### Pattern 1: Dual-Mode Transcription (faster-whisper + optional WhisperX)

**What:** Load faster-whisper model at startup for basic transcription. Optionally load WhisperX diarization pipeline when HF_TOKEN is available and diarization is requested.
**When to use:** Always -- this is the core architecture.

```python
# handler.py -- startup
import os
from faster_whisper import WhisperModel

MODEL_SIZE = os.environ.get("MODEL_SIZE", "large-v3-turbo")
COMPUTE_TYPE = os.environ.get("COMPUTE_TYPE", "int8")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# Always load faster-whisper model
model = WhisperModel(MODEL_SIZE, device="cuda", compute_type=COMPUTE_TYPE)

# Conditionally load diarization pipeline
diarize_pipeline = None
if HF_TOKEN:
    try:
        from whisperx.diarize import DiarizationPipeline
        diarize_pipeline = DiarizationPipeline(use_auth_token=HF_TOKEN, device="cuda")
        print("Diarization pipeline loaded successfully")
    except Exception as e:
        print(f"Warning: Diarization unavailable: {e}")
```

### Pattern 2: Input Format Handling

**What:** Accept single audio or batch of audio files. Normalize to consistent internal format.
**When to use:** Every request.

```python
def handler(job):
    job_input = job["input"]

    # Single audio input
    if "audio_url" in job_input or "audio_base64" in job_input:
        return process_single(job_input)

    # Batch input
    if "audio_urls" in job_input:
        results = []
        for url in job_input["audio_urls"]:
            result = process_single({"audio_url": url, **shared_params(job_input)})
            results.append(result)
        return {"results": results}

    return {"error": "Provide 'audio_url', 'audio_base64', or 'audio_urls'"}
```

### Pattern 3: Output Format Dispatch

**What:** Convert transcription segments to requested output format (plain text, SRT, VTT, or raw segments JSON).
**When to use:** Every response.

```python
# format_output.py
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
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{format_timestamp_srt(seg['start'])} --> {format_timestamp_srt(seg['end'])}")
        lines.append(seg["text"].strip())
        lines.append("")
    return "\n".join(lines)

def segments_to_vtt(segments: list) -> str:
    lines = ["WEBVTT", ""]
    for seg in segments:
        lines.append(f"{format_timestamp_vtt(seg['start'])} --> {format_timestamp_vtt(seg['end'])}")
        lines.append(seg["text"].strip())
        lines.append("")
    return "\n".join(lines)

def segments_to_text(segments: list) -> str:
    return " ".join(seg["text"].strip() for seg in segments)
```

### Pattern 4: Graceful Diarization Degradation

**What:** When diarization is requested but HF_TOKEN is not available, return the transcription without speaker labels and include a warning.
**When to use:** Whenever `diarize=True` is in the request.

```python
def process_with_diarization(audio_path, segments, job_input):
    if not diarize_pipeline:
        return {
            "warning": "Diarization unavailable: HF_TOKEN not configured. "
                       "Set HF_TOKEN env var with a HuggingFace token that has "
                       "accepted pyannote/speaker-diarization-3.1 user agreement.",
            "segments": segments,  # Return without speaker labels
        }

    import whisperx
    audio = whisperx.load_audio(audio_path)

    # Run diarization
    diarize_segments = diarize_pipeline(
        audio,
        min_speakers=job_input.get("min_speakers"),
        max_speakers=job_input.get("max_speakers"),
    )

    # Align and assign speakers
    result = {"segments": segments}
    result = whisperx.assign_word_speakers(diarize_segments, result)
    return result
```

### Anti-Patterns to Avoid

- **Loading WhisperX model for every request:** WhisperX wraps faster-whisper internally. Loading both a standalone faster-whisper model AND a WhisperX model wastes VRAM. Use faster-whisper directly for transcription, WhisperX only for the diarization pipeline.
- **Consuming the segment generator multiple times:** faster-whisper `transcribe()` returns a generator. It can only be iterated once. Materialize to a list immediately: `segments = list(segments)`.
- **Returning raw Segment objects:** faster-whisper Segment dataclasses are not JSON-serializable by default. Convert to dicts using `dataclasses.asdict()` or manual conversion before returning.
- **Using `task="translate"` with diarization:** Translation changes word timings. If both translation and diarization are requested, transcribe first (for diarization alignment), then translate separately.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Word-level timestamps | Custom timestamp interpolation | `word_timestamps=True` in faster-whisper | Whisper's cross-attention weights give accurate per-word timing natively |
| Speaker diarization | Custom speaker clustering | WhisperX DiarizationPipeline + pyannote | Speaker embedding extraction, clustering, and word-speaker assignment is a research-grade problem |
| VAD preprocessing | Custom silence detection | `vad_filter=True` in faster-whisper (Silero VAD) | Silero VAD is battle-tested; custom VAD will miss edge cases and hallucination patterns |
| Audio resampling to 16kHz | Manual scipy/librosa resampling | faster-whisper handles internally | faster-whisper automatically resamples input to 16kHz |
| SRT/VTT format generation | Complex subtitle library | Simple string formatting (see code above) | SRT and VTT are trivial text formats; a library adds unnecessary dependency |
| Language detection | External language ID model | `info.language` from faster-whisper transcribe() | Whisper detects language natively from the first 30 seconds |
| Batched segment processing | Custom chunking logic | `BatchedInferencePipeline` from faster-whisper | Handles GPU batching of VAD-split segments efficiently |

**Key insight:** faster-whisper and WhisperX handle all the hard problems (timestamp alignment, speaker clustering, VAD, language detection) as built-in features. The handler's job is orchestration and format conversion, not DSP or ML.

## Common Pitfalls

### Pitfall 1: WhisperX + faster-whisper Dependency Conflicts

**What goes wrong:** `pip install whisperx` may install an incompatible version of faster-whisper or CTranslate2, causing import errors or CUDA failures at runtime.
**Why it happens:** WhisperX pins certain dependency ranges that can conflict with standalone faster-whisper installations. The onnxruntime vs onnxruntime-gpu conflict is well-documented.
**How to avoid:** Install in this exact order: (1) PyTorch+torchaudio with cu124 index, (2) faster-whisper, (3) whisperx. Use `--no-deps` for whisperx if needed and install its dependencies manually. Test the import chain in the Docker build.
**Warning signs:** `ImportError` or `RuntimeError` mentioning CTranslate2, onnxruntime, or CUDA during container startup.

### Pitfall 2: pyannote Gated Model Fails Silently

**What goes wrong:** Worker starts without HF_TOKEN or with a token that hasn't accepted the pyannote model agreement. Diarization requests fail at runtime with opaque authentication errors.
**Why it happens:** pyannote/speaker-diarization-3.1 is a gated model on HuggingFace. Users must: (1) create an HF token, (2) visit the model page, (3) accept the user agreement. Missing any step causes 403 errors.
**How to avoid:** Try loading the diarization pipeline at startup. If it fails, set `diarize_pipeline = None` and log a clear warning. When diarization is requested without the pipeline, return a helpful error message explaining the three required steps.
**Warning signs:** Diarization works in local testing (developer's token) but fails in production deployment (user forgot to set HF_TOKEN in RunPod).

### Pitfall 3: Whisper Hallucinations on Long Audio

**What goes wrong:** Transcription includes repeated phrases not in the source audio, or silently skips 10-40 second segments of speech.
**Why it happens:** Whisper processes 30-second chunks internally. Without VAD, silence triggers hallucinations. Chunk boundaries can fall mid-sentence.
**How to avoid:** Enable `vad_filter=True` by default (do not make users opt in). Use `vad_parameters=dict(min_silence_duration_ms=500)` as sensible default. For very long files (>30 min), consider using BatchedInferencePipeline for better chunk handling.
**Warning signs:** Transcription output contains repeated phrases; output word count is significantly lower than expected for the audio duration.

### Pitfall 4: Segment Generator Consumed Before Format Conversion

**What goes wrong:** `model.transcribe()` returns a generator. If iterated once for logging/debugging and then passed to format conversion, the second iteration yields nothing.
**Why it happens:** Python generators are single-use iterators.
**How to avoid:** Immediately materialize: `segments = list(segments)`. Do this once, then pass the list to all downstream consumers (diarization, format conversion, response building).
**Warning signs:** Empty transcription output despite valid audio input; inconsistent behavior between first and subsequent requests.

### Pitfall 5: VRAM Accumulation Across Requests

**What goes wrong:** GPU memory grows with each request until OOM crash.
**Why it happens:** faster-whisper and especially WhisperX diarization allocate variable-size tensors per request. PyTorch CUDA allocator fragments memory.
**How to avoid:** Call `torch.cuda.empty_cache()` after every request. Set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` as env var in Dockerfile. Log VRAM usage per request for monitoring.
**Warning signs:** Worker handles first 20 requests fine, then starts failing; nvidia-smi shows growing memory between requests.

### Pitfall 6: Docker Image Exceeds 10GB

**What goes wrong:** PyTorch + CTranslate2 + WhisperX + pyannote + wav2vec2 dependencies create a massive image, causing 60s+ cold starts.
**Why it happens:** PyTorch alone is 2-4GB. WhisperX adds pyannote, torch dependencies, and alignment model dependencies.
**How to avoid:** Never bake model weights into the image. Use `nvidia/cuda:12.4.1-runtime-ubuntu22.04` (not -devel). Install PyTorch with `--index-url https://download.pytorch.org/whl/cu124`. Use `--no-cache-dir` for all pip installs. Target under 8GB image size. Consider a non-diarization preset that skips WhisperX entirely for smaller image size.
**Warning signs:** `docker images` shows >10GB; cold start >30s on RunPod.

## Code Examples

### Complete Transcription Flow

```python
# transcribe.py
import dataclasses
from faster_whisper import WhisperModel

def transcribe_audio(
    model: WhisperModel,
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

    Returns dict with 'segments', 'language', 'language_probability', 'duration'.
    """
    segments_gen, info = model.transcribe(
        audio_path,
        language=language,
        task=task,
        word_timestamps=word_timestamps,
        vad_filter=vad_filter,
        beam_size=beam_size,
        temperature=temperature,
        condition_on_previous_text=False,  # Reduces hallucination
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
        "duration_after_vad": round(info.duration_after_vad, 3) if info.duration_after_vad else None,
    }
```

### Handler with Diarization and Format Output

```python
# handler.py (core handler function)
def handler(job):
    job_input = job["input"]
    audio_path = None

    try:
        # Resolve audio input
        audio_path = resolve_audio_input(job_input)

        # Extract parameters
        language = job_input.get("language")
        task = job_input.get("task", "transcribe")  # "transcribe" or "translate"
        word_timestamps = job_input.get("word_timestamps", True)
        output_format = job_input.get("output_format", "json")  # json, text, srt, vtt
        enable_diarization = job_input.get("diarize", False)

        # Transcribe
        result = transcribe_audio(
            model, audio_path,
            language=language,
            task=task,
            word_timestamps=word_timestamps,
        )

        # Optional diarization
        if enable_diarization:
            diarization_result = process_with_diarization(
                audio_path, result["segments"], job_input
            )
            if "warning" in diarization_result:
                result["warning"] = diarization_result["warning"]
            else:
                result["segments"] = diarization_result["segments"]

        # Format output
        if output_format == "text":
            result["text"] = segments_to_text(result["segments"])
        elif output_format == "srt":
            result["srt"] = segments_to_srt(result["segments"])
        elif output_format == "vtt":
            result["vtt"] = segments_to_vtt(result["segments"])
        # "json" returns segments as-is

        return result

    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Transcription failed: {str(e)}"}
    finally:
        if audio_path:
            cleanup_audio(audio_path)
        # Memory cleanup
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
```

### API Input/Output Contract

```json
// Input (single file)
{
    "input": {
        "audio_url": "https://example.com/podcast.mp3",
        "language": null,
        "task": "transcribe",
        "word_timestamps": true,
        "output_format": "json",
        "diarize": false,
        "beam_size": 5,
        "temperature": 0.0,
        "min_speakers": null,
        "max_speakers": null
    }
}

// Input (batch)
{
    "input": {
        "audio_urls": [
            "https://example.com/file1.mp3",
            "https://example.com/file2.mp3"
        ],
        "language": "en",
        "output_format": "srt"
    }
}

// Output (JSON format with diarization)
{
    "segments": [
        {
            "id": 0,
            "start": 0.0,
            "end": 3.52,
            "text": " Hello, how are you today?",
            "speaker": "SPEAKER_00",
            "words": [
                {"start": 0.0, "end": 0.42, "word": " Hello,", "probability": 0.95},
                {"start": 0.5, "end": 0.72, "word": " how", "probability": 0.98}
            ]
        }
    ],
    "language": "en",
    "language_probability": 0.9876,
    "duration": 125.4,
    "duration_after_vad": 118.2
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| OpenAI Whisper (original) | faster-whisper (CTranslate2) | 2023 | 4x faster, 50% less VRAM, INT8 quantization |
| Whisper large-v3 for all use cases | large-v3-turbo as default | 2024-10 | 8x faster than large-v3, equivalent to large-v2 accuracy |
| onnxruntime in pyannote | Pure PyTorch (speaker-diarization-3.1) | 2024 | Eliminates onnxruntime dependency conflicts |
| Manual Whisper + pyannote integration | WhisperX as unified pipeline | 2023+ | Handles word-to-speaker alignment automatically |
| Segment-level timestamps only | Word-level timestamps default | 2023+ | Enables precise subtitle generation and speaker attribution |
| faster-whisper NamedTuples | faster-whisper dataclasses | 2024 | Use `dataclasses.asdict()` instead of `._asdict()` |

**Deprecated/outdated:**
- `whisper` (OpenAI original): 4x slower, higher VRAM. Use faster-whisper.
- `pyannote/speaker-diarization-3.0`: Uses onnxruntime, causes conflicts. Use 3.1 (pure PyTorch).
- `Segment._asdict()`: Deprecated in faster-whisper. Use `dataclasses.asdict(segment)`.

## Open Questions

1. **WhisperX image size impact**
   - What we know: faster-whisper alone is lightweight (CTranslate2 + small Python package). WhisperX adds PyTorch, pyannote-audio, wav2vec2 alignment models, and their transitive dependencies.
   - What's unclear: Exact Docker image size with full WhisperX stack vs faster-whisper only.
   - Recommendation: Build both Dockerfile variants during implementation. If WhisperX pushes the image over 10GB, consider a separate "diarization" preset that includes it, and a lightweight "transcription-only" preset without it.

2. **WhisperX 3.8 vs 3.3 branch**
   - What we know: PyPI shows both 3.3.4 and 3.8.2 released on similar dates. The 3.8.x branch appears to be the main line.
   - What's unclear: Whether 3.8.x has breaking changes vs 3.3.x or if they're parallel tracks.
   - Recommendation: Use 3.8.2 (latest) and test. Pin the exact version in requirements.txt.

3. **VRAM usage with diarization enabled**
   - What we know: faster-whisper turbo INT8 uses ~3GB. pyannote diarization pipeline adds its own model to VRAM.
   - What's unclear: Combined peak VRAM when running transcription + diarization on the same GPU.
   - Recommendation: Test on T4 (16GB) during implementation. If it doesn't fit, document that diarization requires A4000+ and adjust hub.json presets accordingly.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=7.0 |
| Config file | `worker-whisper/pyproject.toml` (create in Wave 0) |
| Quick run command | `cd worker-whisper && python -m pytest tests/ -x -q` |
| Full suite command | `cd worker-whisper && python -m pytest tests/ -v` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STT-01 | Transcribe with selectable model sizes | unit (mock model) | `pytest tests/test_transcribe.py::test_transcribe_basic -x` | No -- Wave 0 |
| STT-02 | Word-level timestamps in output | unit | `pytest tests/test_transcribe.py::test_word_timestamps -x` | No -- Wave 0 |
| STT-03 | SRT/VTT/text output formats | unit | `pytest tests/test_format_output.py -x` | No -- Wave 0 |
| STT-04 | Language auto-detection | unit | `pytest tests/test_transcribe.py::test_language_detection -x` | No -- Wave 0 |
| STT-05 | Translation to English | unit | `pytest tests/test_transcribe.py::test_translate_task -x` | No -- Wave 0 |
| STT-06 | VAD enabled by default | unit | `pytest tests/test_transcribe.py::test_vad_default_enabled -x` | No -- Wave 0 |
| STT-07 | Diarization with graceful degradation | unit | `pytest tests/test_transcribe.py::test_diarization_graceful -x` | No -- Wave 0 |
| STT-08 | Batch processing multiple files | unit | `pytest tests/test_handler.py::test_batch_processing -x` | No -- Wave 0 |
| STT-09 | hub.json presets valid | unit | `pytest tests/test_hub.py::test_hub_json_valid -x` | No -- Wave 0 |

### Sampling Rate

- **Per task commit:** `cd worker-whisper && python -m pytest tests/ -x -q`
- **Per wave merge:** `cd worker-whisper && python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `worker-whisper/pyproject.toml` -- pytest config, project metadata
- [ ] `worker-whisper/tests/conftest.py` -- shared fixtures (mock WhisperModel, mock segments)
- [ ] `worker-whisper/tests/test_transcribe.py` -- covers STT-01 through STT-07
- [ ] `worker-whisper/tests/test_format_output.py` -- covers STT-03
- [ ] `worker-whisper/tests/test_handler.py` -- covers STT-08
- [ ] `worker-whisper/tests/test_hub.py` -- covers STT-09
- [ ] Framework install: `pip install pytest>=7.0` -- should be in dev dependencies

## Sources

### Primary (HIGH confidence)

- [faster-whisper GitHub (SYSTRAN)](https://github.com/SYSTRAN/faster-whisper) -- API documentation, Segment/Word dataclass fields, transcribe() parameters, VAD filter, BatchedInferencePipeline
- [faster-whisper PyPI](https://pypi.org/project/faster-whisper/) -- version 1.2.1, CUDA 12/cuDNN 9 requirement
- [WhisperX GitHub (m-bain)](https://github.com/m-bain/whisperX) -- DiarizationPipeline API, forced alignment, word-speaker assignment
- [whisperx PyPI](https://pypi.org/project/whisperx/) -- version 3.8.2, Python >=3.10 requirement
- [pyannote/speaker-diarization-3.1 HuggingFace](https://huggingface.co/pyannote/speaker-diarization-3.1) -- gated model, HF_TOKEN requirement, user agreement, MIT license, pure PyTorch (no onnxruntime)
- [RunPod worker-faster_whisper](https://github.com/runpod-workers/worker-faster_whisper) -- official RunPod STT worker (reference for input/output format, confirmed no diarization support)

### Secondary (MEDIUM confidence)

- [Dembrane/runpod-whisper](https://github.com/Dembrane/runpod-whisper) -- community WhisperX RunPod worker (reference implementation with diarization)
- [jim60105/docker-whisperX](https://github.com/jim60105/docker-whisperX) -- WhisperX Docker build patterns, multi-stage approach
- [Modal: Choosing Whisper variants](https://modal.com/blog/choosing-whisper-variants) -- faster-whisper vs alternatives comparison
- [faster-whisper CUDA compatibility issue #1086](https://github.com/SYSTRAN/faster-whisper/issues/1086) -- CTranslate2 4.5+ requires CUDA 12.3+ with cuDNN 9
- [whisperx install issue #1051](https://github.com/m-bain/whisperX/issues/1051) -- dependency conflict workaround (install faster-whisper first)

### Tertiary (LOW confidence)

- WhisperX 3.8.x vs 3.3.x branch differences -- could not find explicit changelog; using latest (3.8.2) based on PyPI recency
- Combined VRAM usage (faster-whisper + pyannote diarization on same GPU) -- not benchmarked; estimated based on individual component sizes

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- faster-whisper is the de facto standard, RunPod's official worker validates the choice
- Architecture: HIGH -- dual-mode (transcription + optional diarization) is the obvious pattern; template files from Phase 1 provide proven foundation
- Pitfalls: HIGH -- dependency conflicts, gated model access, hallucinations, and memory leaks are all well-documented with verified workarounds
- Output formatting: HIGH -- SRT/VTT are simple, well-defined text formats

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (stable domain; faster-whisper and WhisperX are mature)
