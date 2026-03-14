---
phase: 2
slug: stt-worker
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | worker-whisper/pyproject.toml |
| **Quick run command** | `cd worker-whisper && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd worker-whisper && python -m pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd worker-whisper && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd worker-whisper && python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | STT-01 | unit | `pytest tests/test_transcribe.py -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | STT-02, STT-03 | unit | `pytest tests/test_output_formats.py -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | STT-04, STT-05, STT-06 | unit | `pytest tests/test_transcribe.py -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | STT-07 | unit | `pytest tests/test_diarization.py -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | STT-08 | unit | `pytest tests/test_batch.py -x` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 2 | STT-09 | manual | Review hub.json presets | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_transcribe.py` — stubs for STT-01, STT-04, STT-05, STT-06
- [ ] `tests/test_output_formats.py` — stubs for STT-02, STT-03
- [ ] `tests/test_diarization.py` — stubs for STT-07
- [ ] `tests/test_batch.py` — stubs for STT-08
- [ ] `tests/conftest.py` — shared fixtures (mock whisper model, sample audio)
- [ ] `pytest` — install via pyproject.toml

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| RunPod Hub deployment | STT-09 | Requires RunPod account and live deployment | Push image, create endpoint, test with sample audio |
| GPU inference on real hardware | STT-01 | Requires NVIDIA GPU | Run handler with real audio on GPU machine |
| Diarization accuracy | STT-07 | Requires multi-speaker audio evaluation | Test with known multi-speaker audio, verify speaker labels |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
