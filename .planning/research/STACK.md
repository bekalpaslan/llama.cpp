# Stack Research: Audio AI Inference Workers

**Domain:** GPU serverless audio inference (TTS, STT, Voice Cloning) on RunPod
**Researched:** 2026-03-14
**Confidence:** HIGH (STT), MEDIUM-HIGH (TTS), MEDIUM (Voice Cloning)

## Recommended Stack

### Speech-to-Text (STT) Worker

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| faster-whisper | 1.2.1 | Core STT inference engine | 4x faster than OpenAI Whisper, uses CTranslate2 for optimized GPU inference. INT8 quantization reduces VRAM to ~3GB. Battle-tested: RunPod's own official worker uses it. |
| Whisper large-v3-turbo | - | Default STT model | 809M params, ~6GB VRAM FP16. 8x faster than large-v3 with equivalent accuracy to large-v2. Best speed/accuracy tradeoff for production. |
| Whisper large-v3 | - | High-accuracy STT model (preset) | 1.55B params, ~10GB VRAM. Maximum accuracy when speed is secondary. Offer as a premium preset. |
| CTranslate2 | >=4.5.0 | Inference runtime (dependency of faster-whisper) | Handles CUDA kernel optimization, quantization, batch scheduling. Requires CUDA 12+ and cuDNN 9. |

**Confidence:** HIGH -- faster-whisper is the de facto standard. RunPod themselves ship an official `worker-faster_whisper`. The model choices (large-v3-turbo, large-v3) are OpenAI's latest and well-benchmarked.

**VRAM requirements:**
- large-v3-turbo with INT8: ~3GB -- runs on any RunPod GPU (T4+)
- large-v3-turbo with FP16: ~6GB -- comfortable on T4 (16GB)
- large-v3 with FP16: ~10GB -- needs A4000+ (16GB+)

### Text-to-Speech (TTS) Worker

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Chatterbox TTS | 0.1.6 (PyPI: chatterbox-tts) | Primary TTS engine | MIT license. 350M-500M params. Voice cloning from 10s clip. Emotion control. 23 languages (multilingual variant). 6-10GB VRAM. Best all-around choice for a commercial-use RunPod worker. |
| Kokoro | 0.9.4 (PyPI: kokoro) | Lightweight/fast TTS preset | 82M params, <1GB VRAM. Sub-300ms generation. Best for high-throughput, low-latency needs. No voice cloning. Apache 2.0 (code) with model-specific license. |
| F5-TTS | 1.1.17 (PyPI: f5-tts) | Voice cloning TTS preset | 335M params, ~6.4GB VRAM. Zero-shot voice cloning from short audio reference. Flow-matching architecture. CC-BY-NC-4.0 model license (non-commercial). |
| PyTorch | >=2.4.0 | Deep learning framework | Required by all TTS models. Pin to match CUDA version in Docker image. |

**Confidence:** MEDIUM-HIGH -- The TTS landscape moves fast. Chatterbox is the strongest pick for a commercial worker because:
1. MIT license (no restrictions)
2. Voice cloning built-in
3. Three model variants (original, multilingual, turbo) covering different use cases
4. Actively maintained by Resemble AI (a funded company)
5. Reasonable VRAM (6-10GB fits A4000/T4)

Kokoro is the speed champion but lacks voice cloning. F5-TTS has superior voice cloning quality but its CC-BY-NC model license limits commercial use.

### Voice Cloning Worker

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Chatterbox TTS (Turbo) | 0.1.6 | Primary voice cloning | Same as TTS but focused on cloning use case. 350M params, ~6GB VRAM. Takes 10s reference clip. MIT license. OpenAI-compatible API pattern available. |
| RVC (Retrieval-based Voice Conversion) | v2 (pip: rvc-inferpy) | Voice-to-voice conversion | Different paradigm: converts existing audio to target voice rather than text-to-speech. 4GB+ VRAM. Real-time capable (~90ms latency). Requires pre-trained voice model. |

**Confidence:** MEDIUM -- Voice cloning is best delivered as a feature of TTS workers (Chatterbox does both). A standalone voice cloning worker only makes sense for the voice conversion use case (RVC), which is a different product category (voice changers, song covers). Recommendation: bundle voice cloning into the TTS worker, consider a separate RVC worker only if there is demand.

### Shared Infrastructure

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| runpod SDK | >=1.7.0 | Serverless handler framework | Same SDK as existing llama.cpp worker. Maintains consistency. |
| huggingface-hub | >=0.25.0 | Model downloading | Same as existing worker. Enables `download_model.py` pattern reuse. |
| nvidia/cuda:12.4.1-runtime-ubuntu22.04 | 12.4.1 | Docker base image | Same as existing worker. Compatible with PyTorch 2.4+, CTranslate2 4.5+, all target GPUs. Consistency across worker fleet. |
| soundfile | >=0.12.0 | Audio I/O | Read/write WAV, FLAC, OGG. Lightweight. Required by most audio models. |
| base64 (stdlib) | - | Audio encoding for API responses | RunPod serverless returns JSON. Audio bytes must be base64-encoded. Standard pattern across RunPod audio workers. |

## Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ffmpeg | system package | Audio format conversion | Pre-process input audio (MP3, M4A, etc. to WAV). Install via apt in Dockerfile. |
| scipy | >=1.11.0 | Audio resampling | When input sample rate doesn't match model expectations (e.g., 44.1kHz to 16kHz for Whisper). |
| numpy | >=1.24.0 | Audio array manipulation | Dependency of most audio libraries. Pin compatible version. |
| librosa | >=0.10.0 | Audio feature extraction | Only if needed for advanced preprocessing. Heavy dependency -- avoid unless required. |
| pydub | >=0.25.1 | Audio format conversion (Python) | Simpler alternative to raw ffmpeg subprocess calls. Wraps ffmpeg. |
| requests | >=2.31.0 | HTTP client | Same as existing worker, for health checks if using subprocess model. |

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| **faster-whisper** (STT) | whisper.cpp | whisper.cpp is C/C++ like llama.cpp -- excellent for CPU but faster-whisper's CTranslate2 is better optimized for NVIDIA GPUs. RunPod's official worker uses faster-whisper. The Python ecosystem is also easier to integrate with TTS models. |
| **faster-whisper** (STT) | insanely-fast-whisper | Uses HuggingFace transformers + FlashAttention. Good for batch processing but faster-whisper has lower per-request latency and better memory efficiency for serverless (cold start matters). |
| **faster-whisper** (STT) | WhisperX | WhisperX uses faster-whisper under the hood, then adds VAD + forced alignment + diarization. Overkill for a basic STT worker. Offer whisper alignment as a feature flag rather than using WhisperX as the engine. |
| **Chatterbox** (TTS) | XTTS-v2 | XTTS-v2 has excellent voice cloning but Coqui Public Model License prohibits commercial use and Coqui (the company) shut down in Jan 2024. No one can sell commercial licenses. Dead project risk. |
| **Chatterbox** (TTS) | Orpheus TTS | 3B param LLM-based TTS. Excellent quality but needs 12-16GB VRAM and depends on vLLM for efficient inference, adding significant complexity. Best quality but worst resource efficiency. |
| **Chatterbox** (TTS) | Dia / Dia2 | Dia is great for dialogue/multi-speaker but narrow use case. Dia2 requires `uv` and CUDA 12.8+, which conflicts with our CUDA 12.4 base image. English only. |
| **Chatterbox** (TTS) | Kokoro (as primary) | Kokoro is fast but no voice cloning. For a TTS worker, users expect cloning. Use Kokoro as a "fast" preset, not the primary engine. |
| **Chatterbox** (TTS) | Bark | Lower quality than Chatterbox, slower inference, larger VRAM footprint. Was innovative in 2023 but surpassed by 2025 models. |
| **Chatterbox** (Voice Clone) | OpenVoice v2 | Known driver incompatibilities with 40-series GPUs. Less active development. Conda-centric install is harder to Dockerize cleanly. |
| **Chatterbox** (Voice Clone) | F5-TTS | Superior zero-shot cloning quality but CC-BY-NC-4.0 model license prevents commercial use. Cannot recommend for a product meant to be deployed commercially. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| XTTS-v2 | Coqui Public Model License (non-commercial). Company shut down Jan 2024. No commercial license available. Community-maintained but legally risky for a commercial product. | Chatterbox (MIT license, active development) |
| OpenAI Whisper (original) | 4x slower than faster-whisper for same accuracy. Higher VRAM usage. No INT8 quantization support. | faster-whisper |
| Bark | Slow inference (~10-20x real-time), high VRAM (8-12GB), lower quality than 2025 alternatives. Was good in 2023, surpassed now. | Chatterbox or Kokoro |
| Coqui TTS (library) | Coqui shut down. Library is archived/community-maintained. Dependencies are getting stale. | Chatterbox-tts (pip) |
| whisper.cpp for GPU workers | C++ binary approach would work (like llama.cpp pattern) but CUDA support is less mature than CTranslate2. Python ecosystem integration is harder. Would be a good fit for CPU-only workers. | faster-whisper for GPU |
| vLLM (for Orpheus TTS) | Adding vLLM as a dependency for a TTS worker introduces massive complexity -- it's an LLM serving engine. Only justified if Orpheus is the primary model, but Chatterbox gives 80% quality at 20% complexity. | Chatterbox with direct PyTorch inference |
| Dia2 | Requires CUDA 12.8+ (our base image is 12.4). English only. Requires `uv` package manager. Too many incompatibilities with existing infrastructure. | Dia 1.6B if dialogue TTS is needed (works with CUDA 12.6, but still experimental) |

## Stack Patterns by Worker Type

### STT Worker

**Architecture:** Python handler + faster-whisper library (no subprocess needed)
- Unlike llama.cpp (subprocess → binary server), faster-whisper runs as a Python library
- Load model at module level (same pattern as `handler.py`)
- Accept audio as base64 string or URL
- Return transcription as JSON with timestamps

**Dockerfile pattern:**
```
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04
# Install Python, ffmpeg, pip
# pip install faster-whisper runpod huggingface-hub
# Copy handler.py, download_model.py
```

**Input format:**
```json
{
  "audio_base64": "<base64-encoded-audio>",
  "model": "large-v3-turbo",
  "language": "en",
  "word_timestamps": true
}
```

**Output format:**
```json
{
  "text": "transcribed text",
  "segments": [{"start": 0.0, "end": 2.5, "text": "transcribed"}],
  "language": "en"
}
```

### TTS Worker

**Architecture:** Python handler + Chatterbox library (direct PyTorch inference)
- Load model at module level on CUDA
- Accept text + optional reference audio (base64) for voice cloning
- Return audio as base64-encoded WAV
- Support model selection via env vars (original, multilingual, turbo)

**Dockerfile pattern:**
```
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04
# Install Python, pip, system audio libs
# pip install chatterbox-tts torch torchaudio runpod
# Copy handler.py
```

**Input format:**
```json
{
  "text": "Hello world",
  "voice_reference_base64": "<optional-base64-audio>",
  "model": "turbo",
  "language": "en"
}
```

**Output format:**
```json
{
  "audio_base64": "<base64-encoded-wav>",
  "sample_rate": 24000,
  "duration_seconds": 1.5
}
```

### Voice Cloning Worker (if standalone)

**Architecture:** Same as TTS but voice reference is required, not optional.
- Could also use RVC for voice-to-voice conversion
- Different input: source audio + target voice reference
- RVC requires pre-trained voice models (different model distribution pattern)

## Version Compatibility Matrix

| Component | Compatible CUDA | Compatible PyTorch | Notes |
|-----------|----------------|-------------------|-------|
| faster-whisper 1.2.1 | 12.0+ (needs cuDNN 9) | N/A (uses CTranslate2) | CTranslate2 4.5+ requires CUDA 12.3+ |
| chatterbox-tts 0.1.6 | 12.1+ | 2.4+ | Tested on CUDA 12.6, works with 12.4 |
| kokoro 0.9.4 | 12.0+ | 2.0+ | Very lightweight, minimal CUDA requirements |
| f5-tts 1.1.17 | 12.0+ | 2.4+ | pip install torch with matching CUDA |
| nvidia/cuda:12.4.1-runtime-ubuntu22.04 | 12.4 | 2.4+ | Same base image as llama.cpp worker |

**Critical compatibility note:** All recommended libraries work with CUDA 12.4, matching the existing llama.cpp worker's base image. This is important for fleet consistency.

## Installation (per worker)

### STT Worker
```bash
# System dependencies (in Dockerfile)
apt-get install -y ffmpeg

# Python packages
pip install faster-whisper>=1.2.1 runpod>=1.7.0 huggingface-hub>=0.25.0 requests>=2.31.0
```

### TTS Worker
```bash
# System dependencies (in Dockerfile)
apt-get install -y ffmpeg libsndfile1

# Python packages -- install PyTorch first with CUDA
pip install torch>=2.4.0 torchaudio>=2.4.0 --index-url https://download.pytorch.org/whl/cu124
pip install chatterbox-tts>=0.1.2 runpod>=1.7.0 huggingface-hub>=0.25.0 soundfile>=0.12.0
```

### Optional TTS preset: Kokoro (lightweight)
```bash
pip install kokoro>=0.9.4 soundfile>=0.12.0
# Also needs espeak-ng: apt-get install -y espeak-ng
```

## GPU Sizing Guide (for RunPod Hub presets)

### STT Presets
| Model | VRAM Required | Recommended GPU | Cold Start |
|-------|---------------|-----------------|------------|
| large-v3-turbo (INT8) | ~3GB | NVIDIA T4 (16GB) | ~15s |
| large-v3-turbo (FP16) | ~6GB | NVIDIA T4 (16GB) | ~15s |
| large-v3 (FP16) | ~10GB | NVIDIA RTX A4000 (16GB) | ~20s |
| large-v3 (INT8) | ~5GB | NVIDIA T4 (16GB) | ~20s |

### TTS Presets
| Model | VRAM Required | Recommended GPU | Cold Start |
|-------|---------------|-----------------|------------|
| Chatterbox Turbo | ~6GB | NVIDIA RTX A4000 (16GB) | ~30s |
| Chatterbox Original | ~8GB | NVIDIA RTX A4000 (16GB) | ~30s |
| Chatterbox Multilingual | ~8GB | NVIDIA RTX A4000 (16GB) | ~30s |
| Kokoro-82M | <1GB | NVIDIA T4 (16GB) | ~10s |

## Sources

- [faster-whisper PyPI](https://pypi.org/project/faster-whisper/) -- version 1.2.1 confirmed, CUDA 12+/cuDNN 9 requirement
- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper) -- architecture, CTranslate2 dependency
- [Whisper large-v3-turbo HuggingFace](https://huggingface.co/openai/whisper-large-v3-turbo) -- 809M params, accuracy benchmarks
- [Chatterbox GitHub (Resemble AI)](https://github.com/resemble-ai/chatterbox) -- MIT license, v0.1.2, inference API
- [chatterbox-tts PyPI](https://pypi.org/project/chatterbox-tts/) -- v0.1.6, dependencies
- [Kokoro PyPI](https://pypi.org/project/kokoro/) -- v0.9.4, 82M params
- [F5-TTS GitHub](https://github.com/SWivid/F5-TTS) -- v1.1.17, 335M params, CC-BY-NC license
- [Orpheus TTS GitHub](https://github.com/canopyai/Orpheus-TTS) -- Apache 2.0, 3B params, vLLM dependency
- [Dia GitHub (Nari Labs)](https://github.com/nari-labs/dia) -- 1.6B params, CUDA 12.6 requirement
- [Dia2 GitHub](https://github.com/nari-labs/dia2) -- CUDA 12.8+ requirement, Apache 2.0
- [RunPod worker-faster_whisper](https://github.com/runpod-workers/worker-faster_whisper) -- official RunPod STT worker pattern
- [RunPod TTS tutorial](https://docs.runpod.io/tutorials/sdks/python/101/generator) -- streaming handler pattern
- [XTTS-v2 license discussion](https://huggingface.co/coqui/XTTS-v2/discussions/106) -- non-commercial license, Coqui shutdown
- [RunPod SDK PyPI](https://pypi.org/project/runpod/) -- v1.8.1
- [BentoML TTS comparison 2026](https://www.bentoml.com/blog/exploring-the-world-of-open-source-text-to-speech-models) -- ecosystem overview
- [Modal Whisper variants comparison](https://modal.com/blog/choosing-whisper-variants) -- faster-whisper vs alternatives
- [Resemble AI voice cloning tools 2026](https://www.resemble.ai/best-open-source-ai-voice-cloning-tools/) -- landscape overview

---
*Stack research for: Audio AI Inference Workers (RunPod Serverless)*
*Researched: 2026-03-14*
