---
phase: 3
slug: tts-enhancement
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | RunPod integration tests (.runpod/tests.json) + manual |
| **Config file** | none — existing TTS worker pattern |
| **Quick run command** | `python -c "from engines.kokoro_engine import blend_voices; print('import ok')"` |
| **Full suite command** | Manual: send blend request to running worker |
| **Estimated runtime** | ~5 seconds (import check) |

---

## Sampling Rate

- **After every task commit:** Run quick import check
- **After every plan wave:** Manual blend test with running worker
- **Before `/gsd:verify-work`:** Full manual test with multiple blends
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | TTS-01 | unit | `python -c "from engines.kokoro_engine import blend_voices"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] No new test framework needed — existing TTS worker uses .runpod/tests.json integration tests

*Existing infrastructure covers phase requirements with manual verification.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Blended voice is audibly distinct from single voices | TTS-01 | Requires human audio perception | Generate same text with single voice and blended voice, compare |
| Cross-language blend rejection | TTS-01 | Requires running engine | Send blend request with mixed-language voices, verify error |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
