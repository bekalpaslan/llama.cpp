---
phase: 04-voice-cloning-worker
plan: 02
subsystem: voice-cloning
tags: [runpod-handler, chatterbox, voice-cloning, tdd, vram-cleanup, reference-validation]

# Dependency graph
requires:
  - phase: 04-voice-cloning-worker
    plan: 01
    provides: validate_reference_audio(), load_model(), clone_voice(), encode_output(), audio_utils
provides:
  - handler() RunPod serverless entry point wiring all voice cloning modules
  - Module-level Chatterbox model pre-loading for zero-latency first request
  - HF_HOME volume caching for persistent model weights across cold starts
affects: [04-03 dockerfile and hub.json]

# Tech tracking
tech-stack:
  added: []
  patterns: [module-level model loading with patched import for testability, reference_audio key mapping to audio_utils keys]

key-files:
  created:
    - worker-voice-clone/handler.py
    - worker-voice-clone/tests/test_handler.py
  modified: []

key-decisions:
  - "Module-level load_model patched before import for test isolation (same pattern as worker-whisper)"
  - "Handler maps reference_audio_url/base64 to audio_url/audio_base64 keys for resolve_audio_input compatibility"

patterns-established:
  - "Voice cloning handler pattern: validate text -> resolve reference -> validate quality -> clone -> encode -> respond"
  - "Mock load_model before handler import using with-patch context manager at test module level"

requirements-completed: [VC-01, VC-02, VC-03, VC-04]

# Metrics
duration: 4min
completed: 2026-03-14
---

# Phase 4 Plan 02: Handler Integration Summary

**RunPod serverless handler wiring reference validation, Chatterbox cloning, and 48kHz output encoding with 16 handler tests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-14T13:01:54Z
- **Completed:** 2026-03-14T13:05:49Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files created:** 2

## Accomplishments
- handler.py wires validate_reference.py, voice_clone.py, and audio_utils.py into a complete RunPod serverless handler
- Module-level Chatterbox model loading ensures zero-latency first request (pre-loaded at cold start)
- HF_HOME set to /runpod-volume/.cache/huggingface for persistent model weight caching
- 16 handler tests covering input validation, success paths (URL + base64), custom parameter forwarding, cleanup on success/error, VRAM cleanup, exception handling, and module guard
- Full test suite: 32 passed, 1 skipped across all 3 test files (validation + voice_clone + handler)

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: Implement handler.py with tests (TDD)**
   - `4643c7a` (test): add failing tests for handler module -- 16 tests covering all handler behavior
   - `3c1d72e` (feat): implement handler.py wiring validation, cloning, and output encoding -- all 32 tests pass

## Files Created/Modified
- `worker-voice-clone/handler.py` - RunPod serverless handler: text validation, reference audio resolution/validation, Chatterbox cloning, 48kHz output encoding, VRAM cleanup
- `worker-voice-clone/tests/test_handler.py` - 16 tests: input validation (3), validation failure (1), success paths (5), cleanup (4), error handling (1), module guard (1)

## Decisions Made
- **Module-level load_model patching for tests:** Used `with patch("voice_clone.load_model")` context manager before importing handler, matching the established pattern from worker-whisper where module-level model loading must be mocked before import.
- **Reference audio key mapping:** Handler maps `reference_audio_url` to `audio_url` and `reference_audio_base64` to `audio_base64` to maintain compatibility with the template's resolve_audio_input() interface without modifying the shared utility.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- handler.py is complete and tested, ready for Dockerfile and hub.json packaging (Plan 03)
- All core Python modules are in place: handler.py, validate_reference.py, voice_clone.py, audio_utils.py, download_model.py
- Full test suite green (32 passed, 1 skipped for ffmpeg on Windows dev)

## Self-Check: PASSED

All files verified present. All commit hashes verified in git log.

---
*Phase: 04-voice-cloning-worker*
*Completed: 2026-03-14*
