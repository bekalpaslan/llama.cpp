---
phase: 4
slug: voice-cloning-worker
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | worker-voice-clone/pyproject.toml |
| **Quick run command** | `cd worker-voice-clone && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd worker-voice-clone && python -m pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd worker-voice-clone && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd worker-voice-clone && python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | VC-03 | unit | `pytest tests/test_validate_reference.py -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | VC-01, VC-02, VC-04 | unit | `pytest tests/test_voice_clone.py -x` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | VC-01, VC-03 | unit | `pytest tests/test_handler.py -x` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 3 | VC-05 | unit | `pytest tests/test_hub.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_validate_reference.py` — stubs for VC-03 (duration, sample rate, SNR checks)
- [ ] `tests/test_voice_clone.py` — stubs for VC-01, VC-02, VC-04 (zero-shot cloning, cross-lingual, output format)
- [ ] `tests/test_handler.py` — stubs for handler routing and validation integration
- [ ] `tests/conftest.py` — shared fixtures (mock Chatterbox model, sample audio)
- [ ] `pytest` — install via pyproject.toml

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cloned voice sounds like reference | VC-01 | Requires human audio perception | Compare reference clip with generated output |
| Cross-lingual quality | VC-02 | Requires human listening | Generate same text in multiple languages, assess quality |
| RunPod Hub deployment | VC-05 | Requires RunPod account | Push image, create endpoint, test with sample audio |
| GPU inference on real hardware | VC-01 | Requires NVIDIA GPU | Run handler with real audio on GPU machine |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
