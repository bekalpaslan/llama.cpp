# Architecture Research

**Domain:** Audio AI inference workers (TTS, STT, voice cloning) on RunPod Serverless
**Researched:** 2026-03-14
**Confidence:** HIGH

## Standard Architecture

### System Overview

Each audio worker follows the same proven pattern as the existing llama.cpp worker -- a self-contained Docker container with an inference engine, a RunPod handler, and a model downloader. The key difference: audio workers do not need a long-running subprocess server. They load a Python model directly in-process.

```
                          RunPod Workers Hub (this repo)
                    ┌─────────────────────────────────────┐
                    │  .runpod/hub.json (registry links)  │
                    └──────┬──────────┬──────────┬────────┘
                           │          │          │
              ┌────────────┘    ┌─────┘    ┌─────┘
              v                 v          v
   ┌──────────────────┐  ┌──────────┐  ┌──────────────────┐
   │  whisper-worker   │  │tts-worker│  │voice-clone-worker│
   │  (separate repo)  │  │(sep repo)│  │  (separate repo) │
   └──────────────────┘  └──────────┘  └──────────────────┘

Each worker repo has the same 3-file structure:

   ┌─────────────────────────────────────────────┐
   │               Docker Container               │
   │                                               │
   │  ┌─────────────────────────────────────────┐ │
   │  │         download_model.py                │ │
   │  │  (HuggingFace download + volume cache)   │ │
   │  └────────────────┬────────────────────────┘ │
   │                   │ model path                │
   │  ┌────────────────v────────────────────────┐ │
   │  │           handler.py                     │ │
   │  │  ┌───────────────────────────────────┐  │ │
   │  │  │  Module-level: load model to GPU  │  │ │
   │  │  └───────────────┬───────────────────┘  │ │
   │  │                  │                       │ │
   │  │  ┌───────────────v───────────────────┐  │ │
   │  │  │  handler(job) / stream_handler()  │  │ │
   │  │  │  - Decode input (URL/base64)      │  │ │
   │  │  │  - Run inference                  │  │ │
   │  │  │  - Encode output (base64/S3 URL)  │  │ │
   │  │  └───────────────────────────────────┘  │ │
   │  └─────────────────────────────────────────┘ │
   │                                               │
   │  Dockerfile (multi-stage CUDA build)          │
   └───────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `download_model.py` | Download model weights from HuggingFace, cache on network volume, return local path | Reusable across all workers with minor adaptation (GGUF-specific logic removed, generic weight download) |
| `handler.py` | Load model at module level, accept jobs, run inference, return results | Worker-specific: each engine has different Python APIs |
| `Dockerfile` | Multi-stage build: compile CUDA deps in builder, slim runtime with model + handler | Base image varies per engine (PyTorch CUDA vs custom builds) |
| `.runpod/hub.json` | RunPod Hub template config: env vars, presets, GPU recommendations | Same schema across all workers |

## Critical Architectural Difference: Audio vs LLM Workers

The existing llama.cpp worker uses a **sidecar subprocess pattern**: it spawns `llama-server` as a child process and proxies HTTP requests to it. Audio workers should NOT use this pattern. They should use **direct in-process inference** instead.

**Why:** Audio inference engines (faster-whisper, Kokoro, F5-TTS, Chatterbox) are Python-native libraries. There is no separate server binary to spawn. The model loads directly into the Python process via PyTorch/CTranslate2, and inference is a function call, not an HTTP proxy.

```
LLM Worker (existing):                Audio Workers (new):

handler.py                            handler.py
    │                                     │
    │ HTTP proxy                          │ direct call
    v                                     v
llama-server (subprocess)             model.transcribe() / model.generate()
    │                                     │
    v                                     v
GPU (CUDA)                            GPU (CUDA)
```

This simplification means: no health-check polling loop, no subprocess management, no port conflicts. The model loads once at module level and stays in GPU memory for the worker's lifetime.

## Recommended Project Structure (per worker repo)

```
worker-whisper/                        # or worker-tts/, worker-voice-clone/
├── Dockerfile                         # Multi-stage CUDA build
├── handler.py                         # RunPod handler + model loading
├── download_model.py                  # HuggingFace download with volume caching
├── requirements.txt                   # Python dependencies
├── .runpod/
│   └── hub.json                       # RunPod Hub template + presets
├── tests/
│   ├── test_handler.py                # Unit tests for handler logic
│   └── test_input.json                # Sample input payloads
└── README.md                          # Setup, build, deploy instructions
```

### Structure Rationale

- **Flat structure:** Matches the existing llama.cpp worker. No `src/` directory needed -- these are 2-3 file workers, not frameworks.
- **`tests/`:** Enables local testing with `python handler.py --rp_serve_api` (RunPod's local test mode).
- **`.runpod/hub.json`:** Required for RunPod Hub publishing. Contains presets per model variant.

## Architectural Patterns

### Pattern 1: Module-Level Model Loading

**What:** Load the inference model once at import time, keep it in GPU memory across all job invocations.
**When to use:** Always. RunPod serverless workers persist between jobs (they are not true "functions" -- the container stays alive for multiple jobs until idle timeout).
**Trade-offs:** Fast inference (no reload per job) but higher cold-start time. Cold start is acceptable because RunPod charges per-second and users expect a startup delay.

**Example (STT):**
```python
from faster_whisper import WhisperModel
from download_model import download_model

# Module-level: runs once on container start
model_path = download_model(repo_id=HF_REPO_ID)
model = WhisperModel(model_path, device="cuda", compute_type="float16")

def handler(job):
    # model is already loaded and warm
    segments, info = model.transcribe(audio_path, beam_size=5)
    return {"text": " ".join(s.text for s in segments)}
```

**Example (TTS):**
```python
import torch
from kokoro import KModel  # or equivalent API

model_path = download_model(repo_id=HF_REPO_ID)
model = KModel(model_path).to("cuda")

def handler(job):
    text = job["input"]["text"]
    audio = model.generate(text, voice=job["input"].get("voice", "default"))
    return {"audio_base64": base64_encode(audio)}
```

### Pattern 2: Dual Input Mode (URL + Base64)

**What:** Accept audio input as either a public URL or base64-encoded data. This is the established pattern across all RunPod audio workers.
**When to use:** Any worker that receives audio input (STT, voice cloning reference audio).
**Trade-offs:** URLs are better for large files (avoids 10/20MB payload limit), base64 is simpler for small clips. Support both.

**Example:**
```python
import base64
import tempfile
import requests

def resolve_audio_input(job_input):
    """Download or decode audio to a temp file path."""
    if "audio_url" in job_input:
        r = requests.get(job_input["audio_url"], timeout=60)
        r.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(r.content)
        return tmp.name
    elif "audio_base64" in job_input:
        data = base64.b64decode(job_input["audio_base64"])
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(data)
        return tmp.name
    else:
        raise ValueError("Provide 'audio_url' or 'audio_base64'")
```

### Pattern 3: Output Encoding Strategy

**What:** Return audio output as base64 by default, with optional S3 upload for large files.
**When to use:** TTS and voice cloning workers that produce audio output.
**Trade-offs:** Base64 increases payload size by ~33% but keeps the response self-contained. S3 upload adds latency but handles arbitrarily large files. RunPod's response payload limit is 20MB.

**Strategy:**
1. Short audio (<30s): Return base64 directly in response JSON
2. Long audio (>30s): Upload to S3/R2 and return URL
3. Let the user choose via an `output_format` parameter

**Example:**
```python
import base64
import io
import soundfile as sf

def encode_audio_output(audio_array, sample_rate, output_format="wav"):
    buf = io.BytesIO()
    sf.write(buf, audio_array, sample_rate, format=output_format)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")
```

## Data Flow

### STT Worker (Speech-to-Text)

```
Client Request
    │
    │  {"audio_url": "https://...", "language": "en", "model": "large-v3"}
    v
RunPod Queue ──> Worker Container
                     │
                     ├─ resolve_audio_input()
                     │    └─ Download URL / decode base64 → temp .wav file
                     │
                     ├─ model.transcribe(audio_path)
                     │    └─ faster-whisper processes on GPU
                     │    └─ Returns segments with timestamps
                     │
                     ├─ (optional) Align word timestamps
                     │    └─ WhisperX alignment model
                     │
                     ├─ (optional) Speaker diarization
                     │    └─ pyannote.audio pipeline
                     │
                     └─ Return JSON response
                          │
                          v
                     {"text": "...", "segments": [...], "language": "en"}
```

### TTS Worker (Text-to-Speech)

```
Client Request
    │
    │  {"text": "Hello world", "voice": "af_heart", "format": "wav"}
    v
RunPod Queue ──> Worker Container
                     │
                     ├─ Validate text input
                     │    └─ Check length limits, sanitize
                     │
                     ├─ model.generate(text, voice)
                     │    └─ Kokoro/Chatterbox processes on GPU
                     │    └─ Returns audio numpy array + sample rate
                     │
                     ├─ Encode output
                     │    └─ numpy → WAV/MP3 → base64
                     │
                     └─ Return JSON response
                          │
                          v
                     {"audio_base64": "UklGR...", "format": "wav",
                      "sample_rate": 24000, "duration_seconds": 2.1}
```

### Voice Clone Worker

```
Client Request
    │
    │  {"text": "Clone this voice", "reference_audio_url": "https://...",
    │   "reference_text": "Original transcript"}
    v
RunPod Queue ──> Worker Container
                     │
                     ├─ resolve_audio_input(reference_audio)
                     │    └─ Download reference clip → temp file
                     │
                     ├─ model.synthesize(text, reference_audio, reference_text)
                     │    └─ F5-TTS / Chatterbox / XTTS-v2 on GPU
                     │    └─ Extracts speaker embedding from reference
                     │    └─ Generates new speech in cloned voice
                     │
                     ├─ Encode output
                     │    └─ numpy → WAV → base64
                     │
                     └─ Return JSON response
                          │
                          v
                     {"audio_base64": "...", "format": "wav",
                      "sample_rate": 24000, "duration_seconds": 5.3}
```

### Key Data Flows

1. **Audio input flow:** Client provides URL or base64 -> handler downloads/decodes to temp file -> inference engine reads file -> temp file cleaned up after processing
2. **Audio output flow:** Inference engine returns numpy array -> handler encodes to WAV/MP3 bytes -> base64-encode for JSON response (or upload to S3 and return URL for large outputs)
3. **Model loading flow:** Container starts -> `download_model.py` checks network volume cache -> downloads from HuggingFace if missing -> loads model to GPU VRAM -> model persists for all subsequent jobs

## Worker-Specific Architecture Details

### STT Worker (faster-whisper)

```
┌─────────────────────────────────────────────────────┐
│                  STT Worker                          │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  faster-whisper (CTranslate2 engine)          │   │
│  │  - Whisper large-v3 / large-v3-turbo          │   │
│  │  - float16 on GPU, int8 on CPU               │   │
│  │  - ~4.5 GB VRAM for large-v3                  │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  Optional modules (loaded on demand):                │
│  ┌────────────────┐  ┌──────────────────────────┐   │
│  │ whisperx align  │  │ pyannote.audio diarize   │   │
│  │ (word timestamps│  │ (speaker identification) │   │
│  │  via wav2vec2)  │  │  requires HF token)      │   │
│  └────────────────┘  └──────────────────────────┘   │
│                                                      │
│  Dockerfile base: nvidia/cuda:12.4.1-runtime         │
│  Key deps: faster-whisper, ctranslate2               │
│  VRAM: 4-5 GB (large-v3), 1-2 GB (small/medium)     │
│  GPU: Any CUDA GPU (T4 sufficient for large-v3)      │
└─────────────────────────────────────────────────────┘
```

**Presets:** Model size variants (tiny, base, small, medium, large-v3, large-v3-turbo, distil-large-v3). Different GPU tiers map to different model sizes.

### TTS Worker (Kokoro)

```
┌─────────────────────────────────────────────────────┐
│                   TTS Worker                         │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  Kokoro TTS (82M params, StyleTTS2 arch)      │   │
│  │  - PyTorch inference on CUDA                  │   │
│  │  - <2 GB VRAM                                 │   │
│  │  - 35-100x realtime on GPU                    │   │
│  │  - Model file: ~350 MB                        │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  Text processing pipeline:                           │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────┐ │
│  │ misaki G2P │→ │ phonemize   │→ │ chunk+stitch │ │
│  │ (grapheme  │  │ (phoneme    │  │ (30s segment │ │
│  │  to phone) │  │  sequences) │  │  boundary)   │ │
│  └────────────┘  └─────────────┘  └──────────────┘ │
│                                                      │
│  Dockerfile base: pytorch/pytorch:*-cuda12*          │
│  Key deps: kokoro (pip), misaki                      │
│  VRAM: <2 GB                                         │
│  GPU: Any CUDA GPU (even GTX 1060 works)             │
└─────────────────────────────────────────────────────┘
```

**Presets:** Voice variants (af_heart, af_sky, am_adam, etc.), language variants (EN, JA, ZH, KO, FR). All use the same model weights -- voice is selected at inference time via voice ID.

### Voice Clone Worker (Chatterbox or F5-TTS)

```
┌─────────────────────────────────────────────────────┐
│              Voice Clone Worker                      │
│                                                      │
│  Option A: Chatterbox (recommended)                  │
│  ┌──────────────────────────────────────────────┐   │
│  │  Chatterbox-Turbo (350M params)               │   │
│  │  - Zero-shot voice cloning from 5s audio      │   │
│  │  - Sub-200ms latency                          │   │
│  │  - MIT licensed (commercial OK)               │   │
│  │  - Emotion control via exaggeration param     │   │
│  │  - ~4-6 GB VRAM estimated                     │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  Option B: F5-TTS                                    │
│  ┌──────────────────────────────────────────────┐   │
│  │  F5-TTS v1 (335M params)                      │   │
│  │  - Flow matching architecture                 │   │
│  │  - Zero-shot cloning from few seconds         │   │
│  │  - RTF 0.15 (fast enough for interactive)     │   │
│  │  - Apache 2.0 licensed                        │   │
│  │  - ~4-8 GB VRAM estimated                     │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  Input pipeline:                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ Reference     │→ │ Speaker      │→ │ Generate  │ │
│  │ audio decode  │  │ embedding    │  │ new speech│ │
│  │ (URL/base64)  │  │ extraction   │  │ in voice  │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
│                                                      │
│  Dockerfile base: pytorch/pytorch:*-cuda12*          │
│  VRAM: 4-8 GB                                        │
│  GPU: RTX A4000+ recommended                        │
└─────────────────────────────────────────────────────┘
```

**Presets:** Unlike TTS, voice clone workers have fewer presets (usually just the model variant). The "voice" comes from the user's reference audio, not from preset voice IDs.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-10 concurrent users | Single RunPod serverless endpoint per worker type. Default min workers = 0 (scale to zero). Cold starts are acceptable. |
| 10-100 concurrent users | Set min workers = 1 to keep one warm instance. Enable RunPod's FlashBoot for faster cold starts. Use network volumes to eliminate model download time. |
| 100+ concurrent users | Set max workers higher. Consider separate endpoints for different model sizes (e.g., whisper-small for quick jobs, whisper-large for quality). Pre-warm multiple instances. |

### Scaling Priorities

1. **First bottleneck: Cold start time.** Model downloads from HuggingFace can take minutes. Mitigation: bake models into Docker image during build (increases image size but eliminates download), or use network volumes.
2. **Second bottleneck: GPU VRAM contention.** Audio models are small (2-8 GB VRAM) but if you add diarization or multiple models, you can exceed GPU memory. Mitigation: load optional models (pyannote, alignment) lazily, only when requested.

## Anti-Patterns

### Anti-Pattern 1: Subprocess Server for Python-Native Models

**What people do:** Spawn a FastAPI/Gradio server as a subprocess (mimicking the llama-server pattern) and proxy requests to it.
**Why it's wrong:** Adds latency, complexity, and failure modes. Audio models are Python libraries -- they don't need a separate HTTP server. The RunPod handler IS the server.
**Do this instead:** Load the model at module level and call it directly in the handler function.

### Anti-Pattern 2: Downloading Models at Request Time

**What people do:** Download the model inside the handler function, re-downloading for every job.
**Why it's wrong:** Adds 1-10 minutes of download time per request. Wastes bandwidth and money.
**Do this instead:** Download at module level (runs once on cold start). Cache on network volume. Or bake models into the Docker image.

### Anti-Pattern 3: Returning Large Audio as Inline Base64 Without Size Checks

**What people do:** Always return audio as base64 in the JSON response, even for long audio (minutes of TTS output).
**Why it's wrong:** RunPod response payloads have limits (~20MB for runsync). A 5-minute WAV at 24kHz is ~14MB raw, ~19MB base64. Exceeds limits easily.
**Do this instead:** Check output size. For short audio (<30s), return base64. For long audio, upload to S3/R2/RunPod storage and return the URL. Make this configurable.

### Anti-Pattern 4: Monorepo for All Workers

**What people do:** Put STT, TTS, and voice clone handlers in the same repo and Docker image.
**Why it's wrong:** Each worker has different Python deps (faster-whisper vs kokoro vs chatterbox), different CUDA library needs, different model weights. A combined image would be enormous (10+ GB) and slower to build/deploy. Different release cycles get tangled.
**Do this instead:** Separate repos per worker type. Share patterns via documentation or a template repo, not code coupling.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| HuggingFace Hub | `huggingface_hub.hf_hub_download()` at startup | Same pattern as existing llama.cpp worker. Some models (pyannote) require HF token for gated access. |
| RunPod Network Volume | Mount at `/runpod-volume/models` | Cache downloaded models across cold starts. Same path convention as existing worker. |
| S3-Compatible Storage | Upload large audio outputs via `boto3` | Optional. For TTS/voice-clone outputs exceeding 20MB payload limit. User provides credentials via env vars. |
| Docker Hub / GHCR | `docker push` in CI | Publish worker images. Same as existing worker pattern. |
| RunPod Hub | `.runpod/hub.json` in each repo | Register each worker type with presets on RunPod Hub. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Hub registry (this repo) <-> Worker repos | Documentation links only | No code dependency. Hub registry links to published Docker images. |
| handler.py <-> download_model.py | Function call (import) | `download_model()` returns a file path string. Same interface for all workers. |
| handler.py <-> inference engine | Direct Python API call | No HTTP, no subprocess. Model object loaded at module level, called in handler. |
| Worker <-> RunPod SDK | `runpod.serverless.start({"handler": fn})` | Standard RunPod pattern. SDK handles job queue, retries, timeout. |

## Build Order (Dependencies Between Components)

The following build order is recommended based on component dependencies:

```
Phase 1: Shared Foundation
    └─ Generalize download_model.py (remove GGUF-specific logic)
    └─ Create worker template repo with common patterns

Phase 2: STT Worker (fastest to ship, best understood ecosystem)
    └─ faster-whisper is mature, well-documented, simple API
    └─ Direct parallel to existing llama.cpp worker
    └─ No audio output encoding needed (returns JSON text)

Phase 3: TTS Worker (depends on audio output encoding patterns from Phase 2 learnings)
    └─ Kokoro is tiny (82M), fast, high quality
    └─ Requires audio output encoding (base64/S3)
    └─ This pattern then reusable for voice clone worker

Phase 4: Voice Clone Worker (depends on both input AND output audio patterns)
    └─ Needs reference audio input (from STT patterns)
    └─ Needs audio output (from TTS patterns)
    └─ Most complex: combines input + output audio handling
    └─ Model choice (Chatterbox vs F5-TTS) may need evaluation

Phase 5: Hub Registry Update
    └─ Update this repo to link all published workers
    └─ Update .runpod/hub.json or create registry format
```

**Why this order:**
- STT is text-in/text-out (simplest data flow, no audio encoding on output)
- TTS is text-in/audio-out (adds output encoding, but input is simple)
- Voice clone is audio-in/audio-out (most complex, benefits from patterns established in phases 2-3)
- Each phase builds on patterns validated in the previous phase

## Sources

- [RunPod faster-whisper worker (official)](https://github.com/runpod-workers/worker-faster_whisper) - Reference implementation for STT on RunPod
- [Dembrane/runpod-whisper (WhisperX)](https://github.com/Dembrane/runpod-whisper) - WhisperX-based RunPod worker with diarization
- [bes-dev TTS RunPod worker](https://github.com/bes-dev/tts-runpod-serverless-worker) - XTTS v2 RunPod serverless worker
- [XTTS RunPod worker](https://github.com/mehdi-elion/runpod_tts) - Another XTTS-v2 implementation
- [faster-whisper (SYSTRAN)](https://github.com/SYSTRAN/faster-whisper) - Core STT engine, CTranslate2-based
- [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) - Reference Kokoro TTS server architecture
- [Kokoro-82M on HuggingFace](https://huggingface.co/hexgrad/Kokoro-82M) - Model weights and documentation
- [F5-TTS](https://github.com/SWivid/F5-TTS) - Flow-matching TTS with voice cloning
- [Chatterbox (Resemble AI)](https://github.com/resemble-ai/chatterbox) - SOTA open-source TTS with voice cloning
- [RunPod handler documentation](https://docs.runpod.io/serverless/workers/handlers/overview) - Official handler pattern
- [RunPod storage overview](https://docs.runpod.io/serverless/storage/overview) - Payload limits and S3 integration
- [WhisperX](https://github.com/m-bain/whisperX) - Word-level timestamps and speaker diarization
- [Best open-source TTS models 2026 (BentoML)](https://www.bentoml.com/blog/exploring-the-world-of-open-source-text-to-speech-models) - Model comparison
- [Best open-source STT models 2026 (Northflank)](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks) - STT benchmarks

---
*Architecture research for: Audio AI inference workers on RunPod Serverless*
*Researched: 2026-03-14*
