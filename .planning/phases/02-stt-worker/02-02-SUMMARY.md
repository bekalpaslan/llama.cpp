---
phase: 02-stt-worker
plan: 02
subsystem: stt
tags: [runpod-handler, whisperx, diarization, batch-processing, pyannote, tdd]

# Dependency graph
requires:
  - phase: 02-stt-worker
    plan: 01
    provides: "transcribe_audio, format_output utilities, audio_utils, shared test fixtures"
provides:
  - "RunPod serverless handler wiring transcription, diarization, and batch processing"
  - "WhisperX diarization with graceful degradation when HF_TOKEN absent"
  - "Batch audio processing via audio_urls with shared parameters"
  - "17 handler/diarization tests with comprehensive mocking"
affects: [02-stt-worker]

# Tech tracking
tech-stack:
  added: [whisperx]
  patterns: [graceful-degradation, batch-processing, finally-cleanup, tdd]

key-files:
  created:
    - worker-whisper/tests/test_handler.py
    - worker-whisper/tests/test_diarization.py
  modified:
    - worker-whisper/handler.py

key-decisions:
  - "runpod.serverless.start() guarded by __name__ == '__main__' for test importability"
  - "Diarization warning message includes HF_TOKEN, pyannote/speaker-diarization-3.1, and user agreement link"
  - "Batch processing reuses _process_single with synthetic single-input dicts per URL"
  - "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True set at module level if not already set"

patterns-established:
  - "Graceful degradation: optional features return warning dict instead of failing"
  - "Batch via loop: shared params extracted once, applied to each item individually"
  - "Finally-block cleanup: cleanup_audio + torch.cuda.empty_cache in every code path"

requirements-completed: [STT-07, STT-08]

# Metrics
duration: 5min
completed: 2026-03-14
---

# Phase 2 Plan 02: Handler with Diarization and Batch Processing Summary

**RunPod handler wiring transcription engine with WhisperX diarization (graceful HF_TOKEN degradation), batch URL processing, and 17 tests built TDD-style**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-14T06:22:12Z
- **Completed:** 2026-03-14T06:26:57Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments
- Complete RunPod handler with single audio (URL/base64), batch processing, and diarization
- WhisperX diarization pipeline with graceful degradation -- returns helpful warning message when HF_TOKEN absent, including pyannote model name and user agreement link
- Batch processing via audio_urls that applies shared parameters (language, output_format, etc.) to each URL
- VRAM cleanup via torch.cuda.empty_cache() and audio file cleanup in finally blocks on every code path
- 17 new tests (8 single handler + 4 batch + 5 diarization) all passing, 35 total with Plan 01

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement handler.py with diarization and batch processing (TDD)**
   - RED: `2036abd` (test) - 17 failing tests for handler, batch, and diarization
   - GREEN: `0f004e3` (feat) - full implementation passing all 35 tests

_Note: TDD task has separate RED and GREEN commits._

## Files Created/Modified
- `worker-whisper/handler.py` - Full RunPod handler: single/batch audio processing, diarization, format output, cleanup
- `worker-whisper/tests/test_handler.py` - 12 tests: single audio URL/base64, output formats, missing input, error cleanup, CUDA cache, batch processing
- `worker-whisper/tests/test_diarization.py` - 5 tests: diarize with/without pipeline, not requested, min/max speakers, warning content

## Decisions Made
- `runpod.serverless.start()` guarded by `__name__ == "__main__"` so handler module can be imported by tests without triggering the RunPod worker loop
- Diarization warning message is intentionally detailed: includes "HF_TOKEN", "pyannote/speaker-diarization-3.1", and user agreement instructions
- Batch processing implemented as loop over `_process_single()` with synthetic single-input dicts, keeping each item isolated with its own cleanup
- `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` set at module level to avoid CUDA memory fragmentation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed runpod.serverless.start() blocking test imports**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Module-level `runpod.serverless.start()` call caused `SystemExit: 1` when handler.py was imported during testing (RunPod tried to start local worker and failed)
- **Fix:** Wrapped in `if __name__ == "__main__"` guard -- standard pattern for RunPod workers run via `python handler.py`
- **Files modified:** worker-whisper/handler.py
- **Verification:** All 35 tests pass, module imports cleanly
- **Committed in:** 0f004e3 (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor fix to make module importable for testing. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. HF_TOKEN is optional (diarization degrades gracefully without it).

## Next Phase Readiness
- handler.py is complete and ready for Dockerfile integration in Plan 02-03
- All 35 tests pass (Plan 01 + Plan 02), providing a stable foundation
- Module-level model loading handles missing CUDA/faster-whisper gracefully (warns and sets model=None)
- Diarization pipeline loading handles missing whisperx/HF_TOKEN gracefully

## Self-Check: PASSED

All 3 files verified present. Both task commits (2036abd, 0f004e3) verified in git log.

---
*Phase: 02-stt-worker*
*Completed: 2026-03-14*
