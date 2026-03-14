# Requirements: RunPod Workers Hub

**Defined:** 2026-03-14
**Core Value:** One-click deployment of AI inference workers on RunPod — any model type, any GPU, minimal configuration.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Shared Infrastructure

- [x] **INFRA-01**: Worker accepts audio input via URL download or base64 encoding
- [x] **INFRA-02**: Worker template provides generalized model download utility (adapted from llama.cpp worker's download_model.py)
- [x] **INFRA-03**: Worker Dockerfile follows slim multi-stage build pattern for minimal image size

### STT (Speech-to-Text)

- [ ] **STT-01**: User can transcribe audio using faster-whisper with selectable model sizes (turbo, large-v3)
- [ ] **STT-02**: Transcription output includes word-level timestamps
- [ ] **STT-03**: User can get output in plain text, SRT, or VTT subtitle formats
- [ ] **STT-04**: Worker auto-detects spoken language across 50+ languages
- [ ] **STT-05**: Worker can translate non-English audio to English text
- [ ] **STT-06**: VAD (Voice Activity Detection) is enabled by default to prevent hallucination
- [ ] **STT-07**: User can identify who said what via speaker diarization (WhisperX + pyannote)
- [ ] **STT-08**: User can submit multiple audio files in a single job for batch transcription
- [ ] **STT-09**: Worker published to RunPod Hub with model presets in hub.json

### TTS (Text-to-Speech) Enhancements

- [ ] **TTS-01**: User can blend multiple voices with weighted mixing (Kokoro voice mixing)

### Voice Cloning

- [ ] **VC-01**: User can clone a voice from a 5-30s reference audio clip (zero-shot)
- [ ] **VC-02**: User can generate cloned speech in multiple languages (cross-lingual synthesis)
- [ ] **VC-03**: Worker validates reference audio quality before inference (duration, sample rate, SNR checks)
- [ ] **VC-04**: Worker outputs audio at 48kHz in WAV and MP3 formats
- [ ] **VC-05**: Worker published to RunPod Hub with GPU presets in hub.json

### Hub Registry

- [ ] **HUB-01**: This repo serves as central registry linking all published worker repos
- [ ] **HUB-02**: Registry includes links, descriptions, and deployment info for each worker type

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### STT

- **STT-10**: Forced alignment for precise word boundaries (wav2vec2)
- **STT-11**: Large file optimization for 3hr+ audio
- **STT-12**: Multi-engine toggle (faster-whisper vs WhisperX)

### TTS

- **TTS-02**: Word-level timestamps in TTS output for lip-sync
- **TTS-03**: Chatterbox as additional TTS engine
- **TTS-04**: Streaming audio output via WebSocket

### Voice Cloning

- **VC-06**: Multi-engine support (Chatterbox + GPT-SoVITS)
- **VC-07**: Few-shot fine-tuning mode (1-5 min reference audio)
- **VC-08**: Emotion/style control in cloned voice
- **VC-09**: Speaker embedding cache for repeated cloning
- **VC-10**: Voice conversion (audio-to-audio, RVC)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Landing page / website | RunPod Hub is the discovery mechanism |
| Image generation workers | Audio workers first per project scope |
| Embeddings/RAG workers | Not in current scope |
| Monorepo structure | Separate repos per worker for independent release cycles |
| Real-time streaming STT | RunPod serverless is request-response, not persistent connections |
| Built-in training pipelines | Wrong workload pattern for serverless inference workers |
| WebUI for any worker | RunPod console handles UI; don't add frontend deps |
| Monolithic audio worker | Separate workers per domain for independent scaling |
| S3 output for large audio | Deferred; URL/base64 input is v1, S3 output is v2 |
| VRAM monitoring/cleanup | Deferred; basic torch.cuda.empty_cache() in handler, full monitoring v2 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 1 | Complete |
| INFRA-03 | Phase 1 | Complete |
| STT-01 | Phase 2 | Pending |
| STT-02 | Phase 2 | Pending |
| STT-03 | Phase 2 | Pending |
| STT-04 | Phase 2 | Pending |
| STT-05 | Phase 2 | Pending |
| STT-06 | Phase 2 | Pending |
| STT-07 | Phase 2 | Pending |
| STT-08 | Phase 2 | Pending |
| STT-09 | Phase 2 | Pending |
| TTS-01 | Phase 3 | Pending |
| VC-01 | Phase 4 | Pending |
| VC-02 | Phase 4 | Pending |
| VC-03 | Phase 4 | Pending |
| VC-04 | Phase 4 | Pending |
| VC-05 | Phase 4 | Pending |
| HUB-01 | Phase 5 | Pending |
| HUB-02 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 20 total
- Mapped to phases: 20
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-14*
*Last updated: 2026-03-14 after initial definition*
