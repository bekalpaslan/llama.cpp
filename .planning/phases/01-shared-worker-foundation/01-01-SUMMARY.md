---
phase: 01-shared-worker-foundation
plan: 01
subsystem: infra
tags: [huggingface-hub, audio-io, ssrf-prevention, pytest, numpy, soundfile]

# Dependency graph
requires:
  - phase: none
    provides: "First plan, no prior dependencies"
provides:
  - "Generalized HF model downloader with volume caching and snapshot support"
  - "Audio input resolver with URL download, base64 decode, and SSRF prevention"
  - "Audio output encoder (NumPy to base64 WAV)"
  - "Shared pytest fixtures for worker test suites"
affects: [01-shared-worker-foundation, 02-stt-worker, 03-tts-enhancement, 04-voice-cloning-worker]

# Tech tracking
tech-stack:
  added: [huggingface-hub, requests, soundfile, numpy, pytest]
  patterns: [volume-cache-fallback, ssrf-validation, streaming-download, tdd]

key-files:
  created:
    - worker-template/download_model.py
    - worker-template/audio_utils.py
    - worker-template/tests/test_download_model.py
    - worker-template/tests/test_audio_utils.py
    - worker-template/tests/conftest.py
    - worker-template/pyproject.toml
    - worker-template/tests/__init__.py
  modified: []

key-decisions:
  - "Adapted download_model from existing llama.cpp version, removing all GGUF-specific logic"
  - "Used repo_id.replace('/', '--') as subdirectory name for snapshot downloads"
  - "SSRF validation checks private, loopback, and link-local IPs via socket.getaddrinfo"
  - "Audio extension detection falls back from URL path to content-type header to .wav default"

patterns-established:
  - "Volume cache pattern: check /runpod-volume/models first, fallback to /tmp/models"
  - "SSRF prevention: validate resolved IPs before HTTP requests"
  - "TDD workflow: RED (failing tests) -> GREEN (implementation) -> commit"
  - "Shared fixtures in conftest.py: mock_hf_hub, sample_audio_bytes, tmp_model_dir"

requirements-completed: [INFRA-01, INFRA-02]

# Metrics
duration: 5min
completed: 2026-03-14
---

# Phase 1 Plan 01: Core Python Utilities Summary

**Generalized HF model downloader with volume caching and audio I/O utilities with SSRF prevention, built test-first with 20 passing tests**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-14T05:31:20Z
- **Completed:** 2026-03-14T05:36:39Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Generalized download_model.py supporting single-file (hf_hub_download) and full-repo (snapshot_download) downloads with volume caching
- Audio input resolver handling URL download with streaming and base64 decode, with SSRF prevention against private/loopback/link-local IPs
- Audio output encoder converting NumPy arrays to base64-encoded WAV with metadata (format, sample_rate, duration_seconds)
- Full pytest test suite with 20 tests covering all behaviors, shared fixtures in conftest.py

## Task Commits

Each task was committed atomically:

1. **Task 1: Test scaffold and generalized download_model.py** - `ff827d7` (feat)
2. **Task 2: Audio utilities module** - `155dbc4` (feat)

_Note: TDD tasks committed test+implementation together after GREEN phase._

## Files Created/Modified
- `worker-template/pyproject.toml` - Project config with dependencies and pytest settings
- `worker-template/download_model.py` - Generalized HF model downloader (no GGUF logic)
- `worker-template/audio_utils.py` - Audio input resolver, output encoder, cleanup utility
- `worker-template/tests/__init__.py` - Test package marker
- `worker-template/tests/conftest.py` - Shared fixtures (mock_hf_hub, sample_audio_bytes, tmp_model_dir)
- `worker-template/tests/test_download_model.py` - 8 tests for model download utility
- `worker-template/tests/test_audio_utils.py` - 12 tests for audio utilities

## Decisions Made
- Adapted download_model from existing llama.cpp version, stripping all GGUF-specific code (find_gguf_file, QUANT_PREFERENCE, list_repo_files, sys.exit)
- Used `repo_id.replace("/", "--")` as subdirectory name for snapshot downloads per research recommendation
- SSRF validation resolves hostname via socket.getaddrinfo and checks IP against private/loopback/link-local ranges
- Audio extension detection tries URL path first, then content-type header, defaults to .wav

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added os.path.getsize mocks to cache and download tests**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Tests failed because download_model.py calls os.path.getsize for logging, but the cached/downloaded files don't exist on the test machine
- **Fix:** Added monkeypatch.setattr for os.path.getsize in all tests that exercise cache hits or download paths
- **Files modified:** worker-template/tests/test_download_model.py
- **Verification:** All 8 download_model tests pass
- **Committed in:** ff827d7 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Necessary for test correctness on non-Linux platforms. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both core utilities (download_model.py, audio_utils.py) are complete and copy-paste ready for new worker repos
- Plan 01-02 (Template Dockerfile, handler skeleton, hub.json) can proceed immediately
- All 20 tests pass, providing a solid foundation for Phase 2+ workers

## Self-Check: PASSED

All 8 created files verified present. Both task commits (ff827d7, 155dbc4) verified in git log.

---
*Phase: 01-shared-worker-foundation*
*Completed: 2026-03-14*
