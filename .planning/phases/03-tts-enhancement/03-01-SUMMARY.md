---
phase: 03-tts-enhancement
plan: 01
subsystem: tts
tags: [kokoro, voice-blending, torch, tensor-arithmetic, tts]

# Dependency graph
requires:
  - phase: 01-shared-worker-foundation
    provides: Reusable audio worker template pattern
provides:
  - Standalone voice_blend.py module with parse_voice_spec, validate_blend_request, blend_voices
  - Patched kokoro_engine.py with _resolve_voice() for weighted blending
  - Patched handler.py with blend validation before generation
  - Updated tests.json with 4 voice blending test cases
  - Integration README with syntax docs and API examples
affects: [04-voice-cloning-worker, 05-hub-registry]

# Tech tracking
tech-stack:
  added: []
  patterns: [tensor-weighted-sum-blending, voice-spec-parsing, lazy-torch-import]

key-files:
  created:
    - tts-voice-mixing/voice_blend.py
    - tts-voice-mixing/test_voice_blend.py
    - tts-voice-mixing/patches/kokoro_engine.py
    - tts-voice-mixing/patches/handler.py
    - tts-voice-mixing/patches/tests.json
    - tts-voice-mixing/README.md
  modified: []

key-decisions:
  - "Colon-weight syntax (af_heart:70,af_bella:30) for intuitive percentage-style blending"
  - "Lazy torch import in blend_voices() to keep module importable without GPU for validation and testing"
  - "MAX_BLEND_VOICES=5 to prevent diminishing-returns voice mud"
  - "Cross-language blend rejection at handler level before GPU compute"

patterns-established:
  - "Voice spec parsing: comma-split then colon-split with weight normalization"
  - "Patch-based integration: complete drop-in replacement files rather than diffs"
  - "TDD with mocked pipeline: unittest.mock for load_voice, torch.allclose for tensor verification"

requirements-completed: [TTS-01]

# Metrics
duration: 4min
completed: 2026-03-14
---

# Phase 3 Plan 1: Voice Blending Module Summary

**Weighted Kokoro voice blending via tensor arithmetic with colon-weight syntax, 20-test pytest suite, and drop-in patched TTS worker files**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-14T11:59:32Z
- **Completed:** 2026-03-14T12:04:13Z
- **Tasks:** 2
- **Files created:** 6

## Accomplishments

- Voice blend module with three public functions: parse_voice_spec, validate_blend_request, blend_voices
- 20 pytest tests covering all parsing, validation, and tensor blending behaviors
- Drop-in patched kokoro_engine.py with _resolve_voice() method integrating blend logic
- Drop-in patched handler.py with validate_blend_request() call before engine.generate()
- Updated tests.json with 7 total test cases (3 original + 4 voice blending)
- Integration README with syntax docs, validation rules, and API examples

## Task Commits

Each task was committed atomically:

1. **Task 1: Voice blend module with full test suite** (TDD)
   - `6f59a8b` (test: add failing tests for voice blend module)
   - `428b8ba` (feat: implement voice blend module with parse, validate, blend)
2. **Task 2: Patched TTS worker files and integration README** - `34ee050` (feat)

## Files Created/Modified

- `tts-voice-mixing/voice_blend.py` - Core blend module: parse_voice_spec, validate_blend_request, blend_voices, MAX_BLEND_VOICES
- `tts-voice-mixing/test_voice_blend.py` - 20 pytest tests covering all behaviors
- `tts-voice-mixing/patches/kokoro_engine.py` - Drop-in replacement with _resolve_voice() for weighted blending
- `tts-voice-mixing/patches/handler.py` - Drop-in replacement with blend validation in Kokoro path
- `tts-voice-mixing/patches/tests.json` - 7 RunPod test cases including 4 voice blending scenarios
- `tts-voice-mixing/README.md` - Integration guide with syntax, steps, API examples

## Decisions Made

- Colon-weight syntax (`af_heart:70,af_bella:30`) chosen over parenthesized syntax (`af_bella(2)+af_sky(1)`) for intuitive percentage-style blending
- Lazy torch import in `blend_voices()` keeps module importable without GPU for validation-only use and testing
- `MAX_BLEND_VOICES=5` to cap blending at a useful range (2-3 recommended, up to 5 allowed)
- Cross-language blend rejection happens at handler level before GPU compute to avoid wasting resources
- Patch-based integration (complete drop-in files) rather than diffs for simpler deployment

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Integration requires copying files to the tts-worker repo per the README instructions.

## Next Phase Readiness

- Voice blending module is ready for integration into the tts-worker repo
- The patched files are complete drop-in replacements requiring only file copy operations
- Phase 4 (Voice Cloning Worker) can proceed independently
- No blockers identified

## Self-Check: PASSED

All 6 files verified present. All 3 commits verified in git log.

---
*Phase: 03-tts-enhancement*
*Completed: 2026-03-14*
