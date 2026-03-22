# Project Research Summary

**Project:** RunPod Audio AI Workers (TTS, STT, Voice Cloning)
**Domain:** GPU serverless audio inference on RunPod Serverless
**Researched:** 2026-03-14
**Confidence:** HIGH (STT), MEDIUM-HIGH (TTS, Voice Cloning)

## Executive Summary

This project expands an existing RunPod Workers Hub (built around a llama.cpp LLM worker) into a fleet of audio AI workers covering Speech-to-Text (STT), Text-to-Speech (TTS), and Voice Cloning. The established pattern — a three-file Docker worker with a RunPod handler, a HuggingFace model downloader, and a hub.json preset registry — is proven, consistent, and directly extensible. The critical architectural shift is that audio workers use direct in-process PyTorch inference rather than the subprocess server pattern used by llama.cpp, making them simpler to implement but requiring careful memory management.

The recommended technology choices are settled for STT (faster-whisper + Whisper large-v3-turbo, with WhisperX for diarization as the key differentiator vs. RunPod's official worker) and TTS (Chatterbox as primary engine for voice cloning capability + MIT license, Kokoro as a speed preset). Voice cloning is the highest-value gap in the RunPod Hub ecosystem — no maintained, high-quality open-source workers exist — and is best delivered via Chatterbox (MIT, English-focused, fast) initially. The TTS worker is noted as already shipped in the research context, so STT and Voice Cloning are the primary new builds.

The dominant risks are all infrastructure-level and affect every audio worker equally: RunPod's 10MB payload limit kills naive base64 audio I/O, PyTorch GPU memory leaks accumulate across requests and cause OOM crashes in production, and bloated Docker images (from PyTorch + CUDA + model weights) create intolerable cold starts. All three risks must be solved at the shared template level before building any individual worker. Addressing them first is the single most important sequencing decision.

## Key Findings

### Recommended Stack

The core stack reuses the existing worker's infrastructure (RunPod SDK >=1.7.0, HuggingFace Hub >=0.25.0, nvidia/cuda:12.4.1-runtime-ubuntu22.04 base image) and adds engine-specific Python libraries. All recommended libraries are CUDA 12.4-compatible, maintaining fleet consistency. PyTorch >=2.4.0 is the inference runtime for TTS and voice cloning workers; CTranslate2 (via faster-whisper) handles STT with better GPU memory efficiency than PyTorch-based alternatives.

The key licensing decision: Chatterbox TTS (MIT) is the only commercial-safe choice that combines voice cloning and TTS in a single maintained library. F5-TTS has better zero-shot cloning quality but its CC-BY-NC-4.0 model license prevents commercial use. XTTS-v2 is legally dead (Coqui shut down, no commercial license available). These licensing constraints are not ambiguous — they are hard blockers for any commercially deployed worker.

**Core technologies:**
- faster-whisper 1.2.1: STT inference — 4x faster than OpenAI Whisper, CTranslate2 INT8 quantization fits on T4 GPU, RunPod's own official worker uses it
- WhisperX: Speaker diarization + forced word alignment — the primary differentiator over RunPod's official faster_whisper worker, which lacks diarization entirely
- Chatterbox TTS 0.1.6: TTS + voice cloning — MIT license (commercial OK), voice cloning from 10s clip, 6-10GB VRAM, actively maintained by Resemble AI
- Kokoro 0.9.4: Lightweight TTS preset — 82M params, <1GB VRAM, sub-300ms generation, no voice cloning but speed champion
- PyTorch >=2.4.0: Deep learning runtime — required by Chatterbox, Kokoro; pin with CUDA 12.4 wheel index
- runpod SDK >=1.7.0: Handler framework — same as existing worker, maintains consistency
- soundfile + ffmpeg: Audio I/O — read/write WAV/FLAC/OGG, convert MP3/M4A inputs

### Expected Features

**Must have (table stakes) — STT Worker:**
- Audio input via URL or base64 (standard RunPod pattern; URL required for large files)
- Multiple Whisper model sizes (turbo default, large-v3 for quality preset)
- Word-level timestamps (every commercial STT API includes these)
- SRT/VTT/plain-text output (subtitle generation is the top STT use case)
- Language auto-detection and translation to English (native Whisper capabilities)
- VAD enabled by default (prevents hallucinations on silence; critical for production)
- Speaker diarization via WhisperX (THE differentiator — RunPod's official worker lacks this)

**Must have (table stakes) — Voice Cloning Worker:**
- Zero-shot voice cloning from 5-30s reference audio (core value proposition)
- Text + reference audio input (standard API contract)
- Cross-lingual synthesis (EN, CN, JP, KR via GPT-SoVITS or equivalent)
- 48kHz audio output (commercial-quality; matches ElevenLabs benchmark)
- WAV + MP3 output formats
- Reference audio quality validation (reject noisy/short clips before compute is wasted)

**Should have (competitive differentiators):**
- STT: Forced alignment (precise word boundaries via wav2vec2) — for subtitle/dubbing workflows
- STT: Batch transcription (multiple files per job) — podcast/meeting archive processing
- STT: Large file optimization (3hr+ audio) — content creator use case
- Voice Cloning: Chatterbox as second engine — English-focused speed option alongside quality-first primary
- Voice Cloning: Emotion/style control — CosyVoice2/GPT-SoVITS capability for creative users
- Voice Cloning: Speaker embedding cache — skip re-processing on repeated cloning requests
- TTS: Word-level timestamps in output — enables lip-sync and karaoke from TTS

**Defer to v2+:**
- STT: Multi-engine toggle (faster-whisper vs WhisperX) — add when engine-specific tuning is needed
- Voice Cloning: Voice conversion (audio-to-audio, RVC) — different product category, warrants separate worker
- Voice Cloning: Real-time voice conversion — requires RunPod Pods, not serverless
- TTS: Streaming audio output — WebSocket handler conflicts with sync handler pattern
- Any: Monolithic worker combining TTS + STT + cloning — conflicting deps, massive image, no independent scaling

**Anti-features (do not build):**
- In-worker training pipelines — wrong workload pattern for serverless inference
- WebUI for any worker — RunPod console handles UI; do not add frontend deps
- Monolithic audio worker — separate repos and images per domain is the correct pattern

### Architecture Approach

Each audio worker is a self-contained Docker container deployed to a separate repository. The three-file structure (handler.py, download_model.py, Dockerfile) from the existing llama.cpp worker is reused with one critical difference: audio workers do not spawn a subprocess server. They load the inference model directly into the Python process at module level (GPU-resident, persistent across jobs) and call it as a library function. This is simpler than the llama.cpp pattern — no health-check polling loop, no port management — but requires explicit GPU memory management that the subprocess model handled automatically via OS-level cleanup.

**Major components:**
1. Shared audio utilities (download_model.py adaptation, URL/base64 input resolver, audio resampler, output encoder, S3 upload fallback) — foundation reused by all three workers
2. STT Worker (handler.py + faster-whisper + optional WhisperX pipeline) — transcription, timestamps, optional diarization
3. TTS Worker (handler.py + Chatterbox/Kokoro + audio output encoder) — text-to-speech with voice selection and optional cloning
4. Voice Cloning Worker (handler.py + Chatterbox or GPT-SoVITS + reference audio validation + audio output encoder) — zero-shot voice cloning as the primary value
5. Hub Registry (this repo's hub.json or updated registry) — links all published workers with presets

### Critical Pitfalls

1. **RunPod 10MB payload limit kills audio I/O** — Never return audio as inline base64 for anything beyond short test clips. Build S3/URL output path first, use base64 only as fallback for <7MB outputs. Address in Phase 1 (shared template) before any audio worker is built.

2. **GPU memory leaks cause OOM crashes in production** — PyTorch-based audio models accumulate CUDA memory across requests. Set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, call `torch.cuda.empty_cache()` after every request, log VRAM usage per request, and implement a request-count circuit breaker for known-leaking engines. Test each engine with 100+ sequential requests before publishing.

3. **Docker image bloat creates 60s+ cold starts** — PyTorch + CUDA + audio libraries easily exceeds 15GB when combined with baked-in model weights. Never bake model weights into the image. Use nvidia/cuda:12.4.1-runtime (not -devel), install PyTorch with the cu124 wheel index only, target <8GB image size. Measure cold start time as a release gate.

4. **Whisper hallucinations and missing segments on long audio** — Always enable `vad_filter=True` in faster-whisper; without it, silence triggers hallucinations. Use overlap-stride chunking for audio >5 minutes. Return word-level timestamps by default so callers can detect gaps. Test with 30-minute files before publishing.

5. **Voice cloning quality collapses silently on bad reference audio** — The model never errors on noisy/short reference clips — it just produces garbage output. Validate reference audio upfront: require >=5 seconds, >=16kHz sample rate, estimated SNR >=20dB, single-speaker detection. Return quality metrics (SNR, speaker similarity score) in the response.

## Implications for Roadmap

Based on research, the build order is unambiguous: shared infrastructure problems must be solved before any individual worker is built, since every audio worker inherits the same payload, memory, and image-size risks.

### Phase 1: Shared Worker Foundation

**Rationale:** All three audio worker types share the same infrastructure risks (payload limits, memory leaks, image bloat, audio I/O utilities). Solving these once in a template prevents shipping broken patterns into each worker. The architecture research explicitly recommends this order — the llama.cpp worker's download_model.py pattern needs audio-specific adaptation, and the audio I/O utility (URL resolver, resampler, S3 uploader) is consumed by every subsequent phase.

**Delivers:** Worker template repo with generalized download_model.py, audio I/O utilities (URL/base64 input resolver, resampler, S3 upload with base64 fallback), VRAM monitoring helper, URL validation (SSRF prevention), structured startup with try/except model loading, and a slim Dockerfile pattern targeting <8GB image size.

**Addresses:** Audio input via URL or base64 (table stakes for all workers), multiple output formats, S3-compatible storage integration.

**Avoids:** Payload limit failures (Pitfall 1), VRAM leak crashes (Pitfall 2), image bloat cold starts (Pitfall 3), SSRF via audio URLs (security pitfall).

### Phase 2: STT Worker (Speech-to-Text)

**Rationale:** STT is the simplest data flow (audio-in, JSON-out — no audio encoding on output), best-understood ecosystem (faster-whisper is mature and well-documented), and has the clearest differentiator story (speaker diarization via WhisperX). It builds directly on Phase 1 utilities without adding output audio complexity. Shipping it first validates the shared template patterns before they are reused in more complex workers.

**Delivers:** worker-whisper repository with faster-whisper STT, WhisperX diarization, word timestamps, SRT/VTT/plain-text output, VAD enabled by default, multiple Whisper model presets in hub.json (turbo default on T4, large-v3 for quality on A4000), and streaming progress for long files.

**Uses:** faster-whisper 1.2.1, WhisperX, pyannote-audio (gated HuggingFace model — requires HF_TOKEN env var), shared audio utilities from Phase 1.

**Implements:** STT worker architecture component from ARCHITECTURE.md.

**Avoids:** Whisper long-audio hallucinations (Pitfall 4, enable VAD by default), sample rate mismatches (Pitfall 5, resample to 16kHz at input), engine load failures (Pitfall 7, wrap model init in try/except with GPU diagnostics).

### Phase 3: TTS Worker Enhancement (if not already complete)

**Rationale:** Research notes the TTS worker is already shipped (Kokoro/Dia/F5 engines). This phase assesses what gaps remain vs. the feature research findings — specifically word-level timestamps, voice mixing, and whether Chatterbox should be added as a fourth engine. If the existing worker already covers table stakes, this phase may be lightweight.

**Delivers:** Assessment of existing TTS worker against table stakes checklist, addition of any missing features (format parameter, word-level timestamps, Chatterbox engine if justified), updated hub.json presets.

**Uses:** Chatterbox TTS 0.1.6 (if added), existing Kokoro/F5 engines, shared audio utilities from Phase 1.

**Avoids:** Missing format options (common TTS gap from "Looks Done But Isn't" checklist), audio output size limit without S3 fallback.

### Phase 4: Voice Cloning Worker

**Rationale:** Voice cloning is audio-in/audio-out — the most complex data flow, combining Phase 1's input audio handling with Phase 3's output audio encoding. It must come last. It is also the highest-value gap in the RunPod Hub ecosystem (zero maintained quality workers exist). Chatterbox is the recommended primary engine (MIT license, commercial-safe), with GPT-SoVITS as a multilingual quality option for v1.x.

**Delivers:** worker-voice-clone repository with Chatterbox zero-shot voice cloning, reference audio quality validation (duration, SNR, sample rate checks), cross-language synthesis, 48kHz WAV + MP3 output, quality metrics in response (speaker similarity score, reference SNR), hub.json presets (A4000 GPU minimum), SSRF-validated URL input.

**Uses:** Chatterbox TTS 0.1.6, shared audio utilities from Phase 1 (input resolver, resampler, S3 uploader, URL validator), output encoding from Phase 3 patterns.

**Implements:** Voice Clone Worker architecture component from ARCHITECTURE.md.

**Avoids:** Voice cloning quality collapse from bad reference audio (Pitfall 6, validate before inference), payload limits for long synthesized audio (Pitfall 1, S3 upload path required), VRAM leaks (Pitfall 2, test with 50+ sequential requests).

### Phase 5: Hub Registry Update

**Rationale:** After all three worker types are published to Docker Hub, the hub registry (this repo) needs to link them. This is a coordination phase, not development.

**Delivers:** Updated hub.json or registry links in this repo pointing to published worker images for STT, TTS, and Voice Cloning. Documentation update in README.

**Avoids:** Registry fragmentation — each worker should be discoverable from a central registry entry point.

### Phase Ordering Rationale

- Phase 1 is non-negotiable as the foundation: the payload limit and memory leak pitfalls affect every audio worker equally and must be solved before any worker is built.
- Phase 2 (STT) before Phase 4 (Voice Clone) because STT is audio-in/text-out — the simpler output pattern. Voice cloning is audio-in/audio-out and reuses patterns from both STT (input handling) and TTS (output encoding).
- Phase 3 (TTS) is potentially a no-op if the shipped worker already covers the checklist; its position between STT and Voice Cloning ensures output encoding patterns are validated before Voice Cloning reuses them.
- Phase 5 is always last — it depends on all workers being published.

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 4 (Voice Cloning):** Engine selection needs validation. Research recommends Chatterbox as primary and GPT-SoVITS as multilingual option, but GPT-SoVITS has complex installation requirements and the research did not verify its CUDA 12.4 compatibility. Chatterbox's multilingual capability (listed as 23 languages in STACK.md) may reduce the need for GPT-SoVITS entirely. Run engine comparison before committing to architecture.
- **Phase 4 (Voice Cloning):** pyannote-audio for reference audio speaker detection requires a gated HuggingFace model and user token. Explore lightweight alternatives (energy-based heuristics, silero speaker count estimation) that avoid the token requirement for this validation use case.
- **Phase 2 (STT) — diarization:** pyannote-audio requires a HuggingFace token for model access (gated model). Worker must handle the case where HF_TOKEN is not provided — diarization should degrade gracefully (skip, return warning) rather than fail the job.

Phases with standard patterns (skip research-phase):

- **Phase 1 (Shared Template):** The download_model.py pattern, Dockerfile slim-image approach, and RunPod SDK handler pattern are all well-documented in the existing worker. Extend, do not redesign.
- **Phase 2 (STT Core):** faster-whisper is battle-tested. The RunPod official worker-faster_whisper is a direct reference implementation. Standard patterns apply.
- **Phase 5 (Hub Registry):** hub.json schema is established and documented. No research needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH (STT), MEDIUM-HIGH (TTS/VC) | faster-whisper is the de facto standard with official RunPod backing. Chatterbox is new (0.1.6) but MIT-licensed and Resemble AI-backed. F5-TTS and Kokoro are well-benchmarked. |
| Features | MEDIUM-HIGH | Competitor feature matrix is well-researched. The "TTS worker already shipped" context means TTS feature completeness needs verification against actual shipped code, not research assumptions. |
| Architecture | HIGH | The existing llama.cpp worker provides a proven pattern. Audio-specific adaptations (in-process inference, audio I/O utilities) are straightforward extensions of established patterns. |
| Pitfalls | HIGH | All critical pitfalls are verified against GitHub issues, RunPod documentation, and community reports. Payload limits and memory leak issues are documented in specific GitHub issue threads. |

**Overall confidence:** HIGH for STT and shared infrastructure. MEDIUM-HIGH for TTS/Voice Cloning due to rapidly evolving ecosystem.

### Gaps to Address

- **TTS worker current state:** Research mentions TTS is "already shipped" with Kokoro/Dia/F5 but does not verify what is actually implemented. Before Phase 3, audit the existing worker against the table stakes checklist (format parameter, S3 output, memory cleanup, VAD-equivalent for TTS) to determine actual scope.
- **GPT-SoVITS vs Chatterbox for Voice Cloning:** Research lists GPT-SoVITS as the voice cloning primary recommendation in FEATURES.md but STACK.md and ARCHITECTURE.md lean toward Chatterbox. This inconsistency needs resolution before Phase 4 begins. Recommend Chatterbox as v1 primary (simpler install, MIT license, CUDA 12.4 confirmed), GPT-SoVITS as v1.x addition pending compatibility verification.
- **pyannote-audio HF token dependency:** Speaker diarization (the key STT differentiator) requires a gated HuggingFace model. The handler must be designed to degrade gracefully when HF_TOKEN is absent — not a blocker, but must be designed in from the start.
- **Whisper large-v3-turbo memory spec discrepancy:** STACK.md says turbo is 809M params / ~6GB VRAM FP16, but ARCHITECTURE.md says STT worker uses ~4.5GB for large-v3. Verify actual VRAM usage for large-v3-turbo INT8 on T4 before publishing GPU recommendations in hub.json presets.

## Sources

### Primary (HIGH confidence)
- [faster-whisper GitHub (SYSTRAN)](https://github.com/SYSTRAN/faster-whisper) — STT engine architecture, CTranslate2 dependency, CUDA requirements
- [RunPod worker-faster_whisper (official)](https://github.com/runpod-workers/worker-faster_whisper) — reference STT implementation on RunPod
- [RunPod Endpoint Configurations](https://docs.runpod.io/serverless/endpoints/endpoint-configurations) — payload limits (10MB runsync, 1MB streaming yield), timeout constraints
- [RunPod S3-Compatible API](https://docs.runpod.io/storage/s3-api) — large output handling pattern
- [Chatterbox GitHub (Resemble AI)](https://github.com/resemble-ai/chatterbox) — MIT license, v0.1.6, inference API
- [WhisperX GitHub](https://github.com/m-bain/whisperX) — diarization + forced alignment capabilities
- [faster-whisper memory issues #660, #249](https://github.com/SYSTRAN/faster-whisper/issues/660) — GPU memory leak verification
- [Kokoro-FastAPI memory issue #262](https://github.com/remsky/Kokoro-FastAPI/issues/262) — TTS memory leak verification

### Secondary (MEDIUM confidence)
- [BentoML TTS comparison 2026](https://www.bentoml.com/blog/exploring-the-world-of-open-source-text-to-speech-models) — ecosystem overview, model comparisons
- [Modal: Choosing Whisper Variants](https://modal.com/blog/choosing-whisper-variants) — faster-whisper vs alternatives
- [Resemble AI: Best Open Source Voice Cloning Tools 2026](https://www.resemble.ai/best-open-source-ai-voice-cloning-tools/) — landscape overview
- [Northflank: Best Open Source STT 2026](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks) — STT benchmarks
- [Fish Audio: Voice Cloning Guide](https://fish.audio/blog/voice-cloning-guide/) — reference audio quality requirements
- [Deepgram: Open Source TTS Production Deployment Guide](https://deepgram.com/learn/open-source-text-to-speech-production-guide) — production patterns

### Tertiary (LOW confidence — needs validation)
- Chatterbox 23-language multilingual claim — sourced from PyPI/README, not independently benchmarked; validate before using multilingual capability as a feature selling point
- GPT-SoVITS v4 CUDA 12.4 compatibility — listed as supporting CUDA 12+ but not verified against the exact 12.4.1 runtime base image used in this worker fleet

---
*Research completed: 2026-03-14*
*Ready for roadmap: yes*
