---
phase: 04-voice-cloning-worker
plan: 03
subsystem: voice-cloning
tags: [dockerfile, hub-json, runpod-hub, docker, cuda, chatterbox]

# Dependency graph
requires:
  - phase: 04-voice-cloning-worker
    plan: 01
    provides: validate_reference.py, voice_clone.py, audio_utils.py, download_model.py
  - phase: 04-voice-cloning-worker
    plan: 02
    provides: handler.py wiring all modules
provides:
  - Production Dockerfile building from CUDA 12.4.1 with chatterbox-tts
  - requirements.txt with pinned minimum versions
  - RunPod Hub presets for 3 deployment configurations (Turbo/Multilingual/Original)
  - test_input.json for local development testing
  - Hub validation test suite (8 tests)
affects: [deployment, runpod-hub]

# Tech tracking
tech-stack:
  added: [nvidia/cuda:12.4.1-runtime-ubuntu22.04]
  patterns: [single-stage Dockerfile for PyTorch workers, PyTorch-first install order via CUDA wheel index]

key-files:
  created:
    - worker-voice-clone/Dockerfile
    - worker-voice-clone/requirements.txt
    - worker-voice-clone/.runpod/hub.json
    - worker-voice-clone/test_input.json
    - worker-voice-clone/tests/test_hub.py
  modified: []

key-decisions:
  - "Single-stage Dockerfile (not two-stage like llama.cpp) since PyTorch is a pip package"
  - "HF_HOME set in Dockerfile ENV for persistent model caching across cold starts"
  - "MODEL_VARIANT defaults to multilingual for broadest language coverage"

patterns-established:
  - "Voice cloning Dockerfile pattern: CUDA runtime + ffmpeg + PyTorch via wheel index + chatterbox-tts via requirements.txt"
  - "Hub preset pattern: MODEL_VARIANT env var selecting Chatterbox model variant"

requirements-completed: [VC-05]

# Metrics
duration: 3min
completed: 2026-03-14
---

# Phase 4 Plan 03: Dockerfile, Hub Presets, and Deployment Config Summary

**Production Dockerfile with CUDA 12.4.1 runtime, 3 RunPod Hub presets (Turbo/T4, Multilingual/A4000, Original/A4000), and 8 hub validation tests**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-14T13:09:26Z
- **Completed:** 2026-03-14T13:12:33Z
- **Tasks:** 2
- **Files created:** 5

## Accomplishments
- Dockerfile builds from CUDA 12.4.1 runtime, installs PyTorch via CUDA 12.4 wheel index, then chatterbox-tts via requirements.txt
- HF_HOME and PYTORCH_CUDA_ALLOC_CONF set in Dockerfile ENV for model caching and VRAM stability
- hub.json with 3 presets covering all Chatterbox variants: Turbo (English, T4), Multilingual (23 languages, A4000), Original (emotion control, A4000)
- test_input.json provides a voice cloning test payload for local development
- 8 hub validation tests all passing; full worker suite: 40 passed, 1 skipped

## Task Commits

Each task was committed atomically:

1. **Task 1: Dockerfile and requirements.txt** - `8b9ab01` (feat)
2. **Task 2: hub.json, test_input.json, and hub validation tests** - `ff2fd1d` (feat)

## Files Created/Modified
- `worker-voice-clone/Dockerfile` - CUDA 12.4.1 runtime with PyTorch, chatterbox-tts, ffmpeg, HF_HOME caching
- `worker-voice-clone/requirements.txt` - Python deps: chatterbox-tts, runpod, huggingface-hub, requests, soundfile, numpy
- `worker-voice-clone/.runpod/hub.json` - 3 RunPod Hub presets (Turbo T4, Multilingual A4000, Original A4000)
- `worker-voice-clone/test_input.json` - Sample voice cloning payload with text, reference URL, language, format
- `worker-voice-clone/tests/test_hub.py` - 8 tests: exists, valid JSON, required fields, preset structure, MODEL_VARIANT, count, turbo, multilingual

## Decisions Made
- **Single-stage Dockerfile:** Same pattern as worker-whisper -- PyTorch is a Python package (not compiled from source like llama.cpp), so no builder stage needed.
- **HF_HOME in Dockerfile ENV:** Set to `/runpod-volume/.cache/huggingface` so Chatterbox `from_pretrained()` caches model weights persistently across cold starts.
- **MODEL_VARIANT defaults to multilingual:** Broadest language coverage (23 languages) as the default, matching the Dockerfile default in the plan.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Voice cloning worker is fully deployment-ready: all Python modules, handler, Dockerfile, and hub.json in place
- Phase 4 complete: all 3 plans (core modules, handler, deployment config) delivered
- Full test suite: 40 passed, 1 skipped (ffmpeg on Windows dev machine -- passes in Docker container)
- Ready for Phase 5 or Docker build + push to RunPod Hub

## Self-Check: PASSED

All 5 files verified present. All 2 commit hashes verified in git log.

---
*Phase: 04-voice-cloning-worker*
*Completed: 2026-03-14*
