---
phase: 02-stt-worker
plan: 03
subsystem: stt
tags: [dockerfile, docker, hub-json, runpod-hub, cuda, pytorch, faster-whisper, whisperx]

# Dependency graph
requires:
  - phase: 02-stt-worker
    plan: 01
    provides: "transcribe.py, format_output.py, download_model.py, audio_utils.py"
  - phase: 02-stt-worker
    plan: 02
    provides: "handler.py with diarization and batch processing"
provides:
  - "Production Dockerfile with correct dependency install order for STT worker"
  - "RunPod Hub presets for turbo (T4), large-v3 (A4000), and turbo+diarize (A4000)"
  - "Sample test payload for local development"
  - "Hub.json validation test suite"
affects: [02-stt-worker]

# Tech tracking
tech-stack:
  added: []
  patterns: [dockerfile-install-order, hub-json-presets, hub-validation-tests]

key-files:
  created:
    - worker-whisper/Dockerfile
    - worker-whisper/requirements.txt
    - worker-whisper/.runpod/hub.json
    - worker-whisper/test_input.json
    - worker-whisper/tests/test_hub.py
  modified: []

key-decisions:
  - "Separate RUN commands for faster-whisper and whisperx in Dockerfile to enforce install order and avoid dependency conflicts"
  - "Three hub.json presets covering turbo/INT8 on T4, large-v3/FP16 on A4000, and turbo+diarize on A4000"
  - "MODEL_NAME defaults to 'whisper-stt' in Dockerfile ENV (not 'default' like template)"

patterns-established:
  - "Dockerfile install order: PyTorch -> faster-whisper -> whisperx -> remaining deps via requirements.txt"
  - "Hub validation tests: pathlib-based relative path to hub.json, pytest fixture for parsed data"

requirements-completed: [STT-09]

# Metrics
duration: 3min
completed: 2026-03-14
---

# Phase 2 Plan 03: Dockerfile and Deployment Configuration Summary

**Production Dockerfile with ordered dependency installation (PyTorch -> faster-whisper -> whisperx), 3 RunPod Hub presets (turbo/large-v3/diarize), and 8 hub validation tests**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-14T06:30:59Z
- **Completed:** 2026-03-14T06:34:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Production Dockerfile with correct dependency install order preventing faster-whisper/whisperx conflicts
- RunPod Hub configuration with 3 presets: turbo INT8 on T4, large-v3 FP16 on A4000, turbo+diarize on A4000
- Sample test_input.json with Gettysburg Address audio URL for local development testing
- 8 hub validation tests ensuring hub.json structure integrity
- All 43 tests pass across the complete STT worker test suite

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Dockerfile and requirements.txt** - `eb3086b` (feat)
2. **Task 2: Create hub.json presets, test inputs, and hub validation tests** - `0f20bfd` (feat)

## Files Created/Modified
- `worker-whisper/Dockerfile` - Production Docker build with CUDA 12.4.1 runtime, ordered dependency installation, all 5 Python files COPYed
- `worker-whisper/requirements.txt` - Pinned minimum versions for all non-PyTorch dependencies
- `worker-whisper/.runpod/hub.json` - RunPod Hub presets for 3 deployment configurations
- `worker-whisper/test_input.json` - Sample payload for local development and testing
- `worker-whisper/tests/test_hub.py` - 8 validation tests for hub.json structure and content

## Decisions Made
- Separate RUN commands for faster-whisper and whisperx to enforce installation order per RESEARCH.md Pitfall 1
- Three presets in hub.json: turbo on T4 for cost-effective transcription, large-v3 on A4000 for maximum accuracy, turbo+diarize on A4000 for speaker identification
- MODEL_NAME defaults to "whisper-stt" in Dockerfile (distinct from template's "default")
- PYTORCH_CUDA_ALLOC_CONF set in Dockerfile ENV (redundant with handler.py module-level setting, but ensures coverage even if handler code changes)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. HF_TOKEN is optional (diarization degrades gracefully without it).

## Next Phase Readiness
- Phase 2 (STT Worker) is complete: all 3 plans executed, 43 tests passing
- worker-whisper/ is build-ready: `docker build --platform linux/amd64 -t whisper-stt .`
- All 9 STT requirements (STT-01 through STT-09) are satisfied
- Ready for Phase 3 planning/execution

## Self-Check: PASSED

All 5 created files verified present. Both task commits (eb3086b, 0f20bfd) verified in git log.

---
*Phase: 02-stt-worker*
*Completed: 2026-03-14*
