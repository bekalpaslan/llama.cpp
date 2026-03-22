---
phase: 1
slug: shared-worker-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 0 | INFRA-01 | unit | `pytest tests/test_audio_utils.py -x` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 0 | INFRA-02 | unit | `pytest tests/test_download_model.py -x` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 1 | INFRA-01 | unit | `pytest tests/test_audio_utils.py -x` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 1 | INFRA-02 | unit | `pytest tests/test_download_model.py -x` | ❌ W0 | ⬜ pending |
| 01-02-03 | 02 | 1 | INFRA-03 | manual | `docker build --platform linux/amd64 -t test .` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_audio_utils.py` — stubs for INFRA-01 (URL download, base64 decode, format detection)
- [ ] `tests/test_download_model.py` — stubs for INFRA-02 (single file download, snapshot download, cache fallback)
- [ ] `tests/conftest.py` — shared fixtures (temp dirs, sample audio files)
- [ ] `pytest` — install if no test framework detected

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Docker image size under 8GB | INFRA-03 | Requires full Docker build with CUDA base | Build image, run `docker images` to verify size |
| GPU inference works in container | INFRA-03 | Requires NVIDIA GPU hardware | Run container on RunPod or local CUDA GPU |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
