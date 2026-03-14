---
phase: 01-shared-worker-foundation
plan: 02
subsystem: infra
tags: [docker, cuda, pytorch, ffmpeg, runpod-handler, hub-json]

# Dependency graph
requires:
  - phase: 01-shared-worker-foundation
    provides: "Generalized download_model.py and audio_utils.py from Plan 01"
provides:
  - "Template Dockerfile with CUDA 12.4 runtime base, PyTorch, ffmpeg, libsndfile"
  - "Handler skeleton wiring download_model and audio_utils into RunPod handler pattern"
  - "RunPod hub.json template with preset structure"
  - "Sample test_input.json with URL and base64 example payloads"
  - "requirements.txt with base audio worker dependencies"
affects: [02-stt-worker, 03-tts-enhancement, 04-voice-cloning-worker]

# Tech tracking
tech-stack:
  added: [torch, torchaudio, ffmpeg, libsndfile1]
  patterns: [single-stage-cuda-runtime, runpod-handler-pattern, audio-worker-template]

key-files:
  created:
    - worker-template/Dockerfile
    - worker-template/handler.py
    - worker-template/requirements.txt
    - worker-template/.runpod/hub.json
    - worker-template/test_input.json
  modified: []

key-decisions:
  - "Single-stage Dockerfile (not two-stage like llama.cpp) because audio workers use PyTorch libraries, not compiled C++"
  - "CUDA 12.4 runtime base (not -devel) to minimize image size"
  - "Handler skeleton has placeholder TODO comments for engine-specific code rather than abstract base classes"

patterns-established:
  - "Audio worker Dockerfile: CUDA runtime -> apt install ffmpeg/libsndfile -> pip install PyTorch cu124 -> pip install requirements.txt -> COPY handler"
  - "Handler pattern: module-level download_model -> define handler with try/finally cleanup_audio -> runpod.serverless.start"
  - "hub.json template: presets array with env vars (HF_REPO_ID, MODEL_NAME), GPU spec, and volume_size"

requirements-completed: [INFRA-03]

# Metrics
duration: 3min
completed: 2026-03-14
---

# Phase 1 Plan 02: Template Dockerfile and Handler Skeleton Summary

**Single-stage CUDA runtime Dockerfile with PyTorch/ffmpeg, handler skeleton wiring shared utilities into RunPod pattern, and hub.json template for audio workers**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-14T05:40:00Z
- **Completed:** 2026-03-14T05:44:35Z
- **Tasks:** 2 (1 auto + 1 checkpoint)
- **Files modified:** 5

## Accomplishments
- Template Dockerfile using nvidia/cuda:12.4.1-runtime-ubuntu22.04 with PyTorch cu124, ffmpeg, and libsndfile -- no model weights baked in
- Handler skeleton demonstrating correct wiring of download_model and audio_utils with RunPod handler pattern, try/finally cleanup, and clear TODO placeholders
- Complete worker-template/ directory ready for copy-paste into new worker repos (STT, TTS, Voice Cloning)
- RunPod hub.json template and sample test inputs for local development

## Task Commits

Each task was committed atomically:

1. **Task 1: Template Dockerfile, handler skeleton, and supporting files** - `9cd3e1c` (feat)
2. **Task 2: Verify complete audio worker template** - checkpoint:human-verify (approved)

## Files Created/Modified
- `worker-template/Dockerfile` - Single-stage CUDA runtime build for PyTorch audio workers
- `worker-template/handler.py` - Handler skeleton importing download_model, audio_utils with RunPod pattern
- `worker-template/requirements.txt` - Base dependencies (runpod, huggingface-hub, requests, soundfile, numpy)
- `worker-template/.runpod/hub.json` - RunPod Hub config template with example preset
- `worker-template/test_input.json` - Sample payloads with URL and base64 audio input examples

## Decisions Made
- Used single-stage Dockerfile (not two-stage like llama.cpp) because PyTorch audio workers import Python libraries directly rather than compiling C++ binaries
- Chose CUDA 12.4 runtime base (not -devel) to keep image size under 8GB
- Handler skeleton uses inline TODO comments for engine customization rather than abstract classes, keeping the template simple and copy-paste friendly

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Complete worker-template/ directory is ready to be copied into new worker repos
- Phase 2 (STT Worker) can copy the template and replace TODO placeholders with faster-whisper engine code
- Phase 3 (TTS Enhancement) and Phase 4 (Voice Cloning) can use the same template as starting point
- All 20 tests from Plan 01 continue to pass, utilities are stable

## Self-Check: PASSED

All 5 created files verified present. Task commit (9cd3e1c) verified in git log.

---
*Phase: 01-shared-worker-foundation*
*Completed: 2026-03-14*
