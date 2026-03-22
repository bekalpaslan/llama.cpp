# RunPod Workers Hub

## What This Is

A central registry and collection of RunPod Serverless worker templates. Currently hosts a llama.cpp-based LLM inference worker with 36 model presets. Expanding to include audio workers (TTS, STT, voice cloning) as separate repos, all discoverable through RunPod Hub.

## Core Value

One-click deployment of AI inference workers on RunPod — any model type, any GPU, minimal configuration.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Inferred from existing codebase. -->

- ✓ GGUF model serving via llama.cpp with OpenAI-compatible API — existing
- ✓ 36 model presets configurable via environment variables — existing
- ✓ Auto-detection of best GGUF quantization when filename not specified — existing
- ✓ Sync and streaming response modes — existing
- ✓ Three input formats: chat messages, simple prompt, OpenAI passthrough — existing
- ✓ Multi-GPU architecture support (T4 through H100) — existing
- ✓ Model caching on RunPod network volumes — existing
- ✓ Docker Hub and RunPod Hub publishing — existing
- ✓ Per-model context size optimization based on VRAM — existing

### Active

<!-- Current scope. Building toward these. -->

- [ ] Hub registry structure linking multiple worker repos
- [ ] Whisper-based speech-to-text worker (separate repo)
- [ ] TTS worker using Kokoro/Bark (separate repo)
- [ ] Voice cloning worker (separate repo)
- [ ] Shared worker template/pattern for new worker repos
- [ ] RunPod Hub publishing for all audio workers

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Landing page / website — RunPod Hub is the discovery mechanism
- Image generation workers — not in current scope, audio first
- Embeddings/RAG workers — not in current scope
- Monorepo structure — decided on separate repos per worker type

## Context

- The llama.cpp worker is mature and published (`alpaslanbek/llamacpp-worker`)
- This repo will evolve from a single worker into the hub registry linking all worker repos
- Each new worker follows the same pattern: Dockerfile + handler.py + model download + RunPod serverless SDK
- Audio workers will target the same GPU fleet (T4-H100) but with different inference engines
- All workers use the same deployment model: Docker image → RunPod Hub template → one-click deploy

## Constraints

- **Platform**: RunPod Serverless — all workers must conform to RunPod's handler/dispatch pattern
- **GPU**: NVIDIA CUDA only — workers must compile for SM 75/80/86/89/90
- **Container**: linux/amd64 Docker images — RunPod requirement
- **Registry**: `.runpod/hub.json` format for RunPod Hub publishing
- **Repos**: Separate repos per worker type — linked from this hub registry

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Separate repos per worker | Different build deps, release cycles, CI pipelines per inference engine | — Pending |
| This repo becomes hub registry | Central place to discover all workers, already has RunPod Hub config | — Pending |
| Audio workers first | User's priority; TTS/STT/voice cloning before image gen or embeddings | — Pending |
| RunPod Hub only (no website) | Simplicity; RunPod Hub handles discovery and deployment | — Pending |

---
*Last updated: 2026-03-14 after initialization*
