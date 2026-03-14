# Roadmap: RunPod Workers Hub

## Overview

This roadmap expands the RunPod Workers Hub from a single llama.cpp LLM worker into a fleet of audio AI workers (STT, TTS, Voice Cloning) all discoverable through RunPod Hub. The build order is dependency-driven: shared infrastructure solves cross-cutting audio I/O and memory problems first, then STT (simplest data flow) validates the template, TTS enhancement adds voice mixing to the shipped worker, Voice Cloning delivers the highest-value gap in the RunPod ecosystem, and finally the hub registry links everything for discovery.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Shared Worker Foundation** - Reusable audio worker template with model download, audio I/O, and slim Dockerfile pattern
- [ ] **Phase 2: STT Worker** - Speech-to-text worker with faster-whisper, diarization, and subtitle output
- [ ] **Phase 3: TTS Enhancement** - Voice mixing capability added to the existing TTS worker
- [ ] **Phase 4: Voice Cloning Worker** - Zero-shot voice cloning worker with reference audio validation
- [ ] **Phase 5: Hub Registry** - Central registry linking all published worker repos for discovery

## Phase Details

### Phase 1: Shared Worker Foundation
**Goal**: All audio workers have a proven, reusable template that handles model downloading, audio input resolution, and slim containerization -- so each subsequent worker starts from working infrastructure instead of solving the same problems independently.
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03
**Success Criteria** (what must be TRUE):
  1. Worker can accept audio input via both URL download and base64 encoding, and the input resolver is importable by any worker repo
  2. Worker can download models from HuggingFace using the generalized download utility, with volume caching and fallback to /tmp (same pattern as llama.cpp worker)
  3. Docker image built from the template Dockerfile is under 8GB and follows multi-stage build with runtime-only CUDA base
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md — Core Python utilities: generalized download_model.py and audio_utils.py with full test suite
- [ ] 01-02-PLAN.md — Template Dockerfile, handler skeleton, and supporting files (hub.json, test inputs)

### Phase 2: STT Worker
**Goal**: Users can transcribe audio with word-level timestamps, subtitle output, automatic language detection, speaker diarization, and batch processing -- deployed as a RunPod serverless endpoint with one-click setup.
**Depends on**: Phase 1
**Requirements**: STT-01, STT-02, STT-03, STT-04, STT-05, STT-06, STT-07, STT-08, STT-09
**Success Criteria** (what must be TRUE):
  1. User can submit an audio file (URL or base64) and receive a transcription with word-level timestamps in their chosen format (plain text, SRT, or VTT)
  2. User can submit audio in any of 50+ languages and receive correct transcription with auto-detected language, or translate non-English audio to English text
  3. User can get speaker-attributed transcription (who said what) via diarization, with graceful degradation when HF_TOKEN is not configured
  4. User can submit multiple audio files in a single job and receive batch results, with VAD enabled by default to prevent hallucination on silence
  5. Worker is published to RunPod Hub with model presets (turbo on T4, large-v3 on A4000) and deployable via one-click
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD
- [ ] 02-03: TBD

### Phase 3: TTS Enhancement
**Goal**: Users of the existing TTS worker can blend multiple voices with weighted mixing for creative voice design.
**Depends on**: Phase 1
**Requirements**: TTS-01
**Success Criteria** (what must be TRUE):
  1. User can specify two or more Kokoro voices with weights and receive speech generated from the blended voice
  2. Blended voice output is audibly distinct from any single input voice, confirming mixing is functional
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

### Phase 4: Voice Cloning Worker
**Goal**: Users can clone any voice from a short reference audio clip and generate new speech in that voice -- deployed as a RunPod serverless endpoint with quality safeguards.
**Depends on**: Phase 1, Phase 3 (output audio encoding patterns)
**Requirements**: VC-01, VC-02, VC-03, VC-04, VC-05
**Success Criteria** (what must be TRUE):
  1. User can submit a 5-30 second reference audio clip plus text and receive synthesized speech in the cloned voice (zero-shot, no training required)
  2. User can generate cloned speech in multiple languages from the same reference clip (cross-lingual synthesis)
  3. Worker rejects reference audio that fails quality validation (too short, low sample rate, poor SNR) with actionable error messages before wasting GPU compute
  4. Output audio is 48kHz and available in both WAV and MP3 formats
  5. Worker is published to RunPod Hub with GPU presets in hub.json and deployable via one-click
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD

### Phase 5: Hub Registry
**Goal**: Users can discover all published RunPod workers (LLM, STT, TTS, Voice Cloning) from a single central registry with deployment info.
**Depends on**: Phase 2, Phase 3, Phase 4
**Requirements**: HUB-01, HUB-02
**Success Criteria** (what must be TRUE):
  1. This repo contains a registry that links to every published worker repo with descriptions, Docker image references, and deployment instructions
  2. A user visiting this repo can find and navigate to any worker type and understand how to deploy it on RunPod
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5
(Note: Phases 2 and 3 depend on Phase 1 but not on each other; they could run in parallel if desired.)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Shared Worker Foundation | 1/2 | In Progress | - |
| 2. STT Worker | 0/? | Not started | - |
| 3. TTS Enhancement | 0/? | Not started | - |
| 4. Voice Cloning Worker | 0/? | Not started | - |
| 5. Hub Registry | 0/? | Not started | - |
