---
phase: 04-voice-cloning-worker
plan: 01
subsystem: voice-cloning
tags: [chatterbox, torchaudio, soundfile, voice-cloning, snr-validation, tdd]

# Dependency graph
requires:
  - phase: 01-shared-worker-foundation
    provides: worker-template with download_model.py and audio_utils.py
provides:
  - validate_reference_audio() with duration, sample rate, SNR validation
  - load_model() for Chatterbox turbo/original/multilingual variants
  - clone_voice() wrapper for Chatterbox model.generate()
  - encode_output() with 24kHz to 48kHz upsampling and WAV/MP3 encoding
  - Shared test fixtures (sample_audio_bytes, mock_chatterbox_model)
affects: [04-02 handler integration, 04-03 dockerfile and hub.json]

# Tech tracking
tech-stack:
  added: [chatterbox-tts, torchaudio]
  patterns: [energy-based SNR estimation, dynamic model import via importlib, speech-like test fixtures with silence gaps]

key-files:
  created:
    - worker-voice-clone/validate_reference.py
    - worker-voice-clone/voice_clone.py
    - worker-voice-clone/pyproject.toml
    - worker-voice-clone/tests/conftest.py
    - worker-voice-clone/tests/test_validate_reference.py
    - worker-voice-clone/tests/test_voice_clone.py
    - worker-voice-clone/tests/__init__.py
  modified:
    - worker-voice-clone/download_model.py (copied from template)
    - worker-voice-clone/audio_utils.py (copied from template)

key-decisions:
  - "Speech-like test fixtures with silence gaps for realistic energy-based SNR estimation"
  - "Dynamic model import via importlib.import_module() instead of conditional top-level imports"
  - "Copied template utilities verbatim (same pattern as Phase 2)"

patterns-established:
  - "Energy-based SNR validation pattern: frame audio, compare lowest-energy (noise) to highest-energy (signal) frames"
  - "Dynamic Chatterbox variant loading via importlib with variant-to-module-path mapping dict"

requirements-completed: [VC-01, VC-02, VC-03, VC-04]

# Metrics
duration: 8min
completed: 2026-03-14
---

# Phase 4 Plan 01: Core Voice Cloning Modules Summary

**Reference audio validation with SNR/duration/sample-rate checks and Chatterbox voice cloning wrapper with 48kHz output encoding**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-14T12:48:40Z
- **Completed:** 2026-03-14T12:57:29Z
- **Tasks:** 2
- **Files created:** 9

## Accomplishments
- validate_reference_audio() rejects clips outside 5-60s, below 16kHz, and below 15dB SNR with actionable error messages
- load_model() dynamically imports all 3 Chatterbox variants (turbo, original, multilingual) via importlib
- clone_voice() wraps model.generate() passing language_id, exaggeration, cfg_weight
- encode_output() resamples 24kHz to 48kHz via torchaudio.functional.resample and supports WAV and MP3 formats
- Full TDD test suite: 17 tests (16 pass, 1 skip for ffmpeg on dev machine)

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: validate_reference.py with tests**
   - `28d5ab9` (test): scaffold worker-voice-clone and add failing validation tests
   - `11e2190` (feat): implement validate_reference.py with all 8 tests passing

2. **Task 2: voice_clone.py with tests**
   - `4ddc7f5` (test): add failing tests for voice_clone module
   - `d789186` (feat): implement voice_clone.py with all 9 tests passing

## Files Created/Modified
- `worker-voice-clone/validate_reference.py` - Reference audio validation (duration, sample rate, SNR checks)
- `worker-voice-clone/voice_clone.py` - Chatterbox wrapper (load_model, clone_voice, encode_output)
- `worker-voice-clone/download_model.py` - HuggingFace model download utility (copied from template)
- `worker-voice-clone/audio_utils.py` - Audio I/O utilities with SSRF protection (copied from template)
- `worker-voice-clone/pyproject.toml` - Project config with pytest settings
- `worker-voice-clone/tests/conftest.py` - Shared fixtures (sample_audio_bytes factory, mock_chatterbox_model)
- `worker-voice-clone/tests/test_validate_reference.py` - 8 tests for VC-03 validation logic
- `worker-voice-clone/tests/test_voice_clone.py` - 9 tests for VC-01, VC-02, VC-04 cloning and encoding
- `worker-voice-clone/tests/__init__.py` - Test package init

## Decisions Made
- **Speech-like test fixtures:** Pure sine wave gives uniform frame energy (0dB SNR). Updated fixture to generate bursts of tone with near-silent gaps, mimicking real speech for realistic SNR estimation testing.
- **Dynamic model import:** Used `importlib.import_module()` with a variant-to-module-path mapping dict instead of conditional top-level imports. This keeps the module importable without chatterbox installed (important for testing).
- **Copied template utilities verbatim:** Same decision as Phase 2 -- download_model.py and audio_utils.py work as-is for voice cloning.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test fixture for SNR estimation compatibility**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Pure sine wave test fixture produced uniform frame energy, making energy-based SNR estimation return 0dB for clean audio (all frames have equal energy, so signal/noise ratio is 1:1)
- **Fix:** Updated sample_audio_bytes fixture to generate speech-like audio with alternating 1s tone bursts and 0.5s near-silent gaps, giving the SNR estimator distinct signal and noise frames
- **Files modified:** worker-voice-clone/tests/conftest.py
- **Verification:** All 8 validation tests pass with realistic SNR values
- **Committed in:** 11e2190

**2. [Rule 3 - Blocking] Installed missing torchaudio dependency**
- **Found during:** Task 2 (GREEN phase)
- **Issue:** torchaudio not installed in dev environment, causing ModuleNotFoundError on import
- **Fix:** Ran `pip install torchaudio`
- **Files modified:** None (system dependency)
- **Verification:** voice_clone.py imports successfully, all tests pass
- **Committed in:** d789186

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes necessary for correct test execution. No scope creep.

## Issues Encountered
- MP3 encoding test (test_encode_output_mp3) is skipped on Windows dev machine because ffmpeg is not available. This is expected -- the test uses `pytest.mark.skipif(not shutil.which("ffmpeg"))` and will pass in the Docker container where ffmpeg is installed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- validate_reference.py and voice_clone.py are ready for handler integration (Plan 02)
- conftest.py fixtures available for handler tests
- All core voice cloning logic is tested and working

## Self-Check: PASSED

All 9 files verified present. All 4 commit hashes verified in git log.

---
*Phase: 04-voice-cloning-worker*
*Completed: 2026-03-14*
