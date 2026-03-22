# Feature Research: Audio AI Workers (TTS, STT, Voice Cloning)

**Domain:** RunPod Serverless Audio AI Workers
**Researched:** 2026-03-14
**Confidence:** MEDIUM-HIGH

## Context

This research covers the feature landscape for three audio worker types being added to the RunPod Workers Hub: Text-to-Speech (TTS), Speech-to-Text (STT), and Voice Cloning. The TTS worker is already shipped (Kokoro/Dia/F5). STT and Voice Cloning workers are not started. RunPod already has a first-party `worker-faster_whisper` in their official `runpod-workers` org -- our STT worker needs to meaningfully differentiate or we skip it. Voice cloning has zero official templates, making it a high-value gap.

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or broken.

#### STT Worker

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Audio input via URL or base64 | Every RunPod audio worker uses this dual-input pattern | LOW | Standard RunPod pattern; URL for large files, base64 for small |
| Multiple Whisper model sizes | RunPod's own worker supports tiny through large-v3+turbo; users expect choice | LOW | Bake a default (large-v3-turbo) but allow override via env var |
| Word-level timestamps | Every commercial STT API (Deepgram, AssemblyAI, Google) includes these | MEDIUM | faster-whisper supports this natively; WhisperX adds better alignment |
| Language auto-detection | Users send audio without knowing the language; 50+ languages expected | LOW | Built into Whisper natively |
| Multiple output formats (plain text, SRT, VTT) | Subtitle generation is the #1 STT use case on RunPod | LOW | Format conversion is trivial once you have timestamped segments |
| Translation to English | Whisper's native capability; users expect it for multilingual content | LOW | Built into faster-whisper |
| Voice Activity Detection (VAD) | Prevents hallucination on silence; critical for production quality | LOW | Silero VAD is standard; enable by default |
| Configurable decoding params (temperature, beam size) | Power users need control over quality vs speed tradeoff | LOW | Pass through to faster-whisper |

#### TTS Worker (already shipped -- validating completeness)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Text input, audio output (base64 or URL) | Fundamental I/O contract | LOW | Already implemented |
| Multiple voice selection | Users expect a voice gallery, not a single voice | LOW | Kokoro has 50+ voices; already implemented |
| Multiple output formats (WAV, MP3, OGG) | Different use cases need different formats | LOW | Already implemented |
| Speed/pitch control | Basic prosody control expected by all TTS users | LOW | Already implemented via Kokoro |
| Long-form text handling (auto-chunking) | Users send full articles/scripts, not just sentences | MEDIUM | Already implemented |

#### Voice Cloning Worker

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Zero-shot cloning from reference audio (3-30s) | This IS the core product; users provide a clip, get cloned speech | HIGH | GPT-SoVITS/Chatterbox handle this natively |
| Text + reference audio input | Standard API contract: "say this text in that voice" | LOW | Handler design; both audio and text in job input |
| Audio input via URL or base64 | Same dual-input pattern as all audio workers | LOW | Standard RunPod pattern |
| Cross-lingual synthesis | Clone a voice in one language, generate speech in another | MEDIUM | GPT-SoVITS supports EN/CN/JP/KR natively |
| Quality audio output (24kHz minimum, 48kHz preferred) | Users compare against ElevenLabs; low quality = instant churn | MEDIUM | GPT-SoVITS v4 outputs 48kHz natively |
| Multiple output formats | WAV, MP3 at minimum | LOW | Post-processing with ffmpeg |

### Differentiators (Competitive Advantage)

Features that set our workers apart from RunPod's official templates and community workers.

#### STT Worker

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Speaker diarization (who said what) | RunPod's official faster_whisper worker does NOT support diarization; this is the biggest gap. Meeting transcription, podcast processing, interview analysis all need this | HIGH | Requires pyannote-audio; needs HuggingFace token for model access. WhisperX integrates this. Major differentiator |
| Forced alignment (precise word boundaries) | Standard Whisper timestamps drift; forced alignment via wav2vec2 gives frame-accurate timing. Essential for subtitle/karaoke/dubbing workflows | MEDIUM | WhisperX's core feature; runs wav2vec2 alignment after transcription |
| Batch transcription (multiple files per job) | Process a whole podcast season or meeting archive in one API call; no official worker supports this | MEDIUM | Accept array of audio URLs; process sequentially or parallelize |
| Large file handling (1GB+, 3hr+) | RunPod's worker struggles with long audio; WhisperX handles 3hr files. Content creators need this for full-length videos | MEDIUM | Intelligent chunking + VAD + stitching |
| Multi-engine support (faster-whisper + WhisperX) | Let users choose speed vs features: faster-whisper for raw speed, WhisperX for diarization+alignment | HIGH | Two engines in one worker; selection via env var, following the hub pattern |
| Pre-built model presets per use case | "Podcast Transcription" preset (large-v3, diarization on, SRT output) vs "Quick Subtitle" preset (turbo, no diarization, VTT output) | LOW | Just env var combinations in hub.json; zero code |

#### TTS Worker (potential additions)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Word-level timestamps in output | Enables lip-sync, karaoke, subtitle alignment from TTS output | LOW | Kokoro already supports this via Kokoro-FastAPI |
| Voice mixing (weighted blend of voices) | Create unique voices by blending existing ones; creative use case | MEDIUM | Kokoro supports this natively |
| Streaming audio output | Real-time audio delivery for conversational AI, voice agents | HIGH | Requires RunPod WebSocket streaming handler |
| SSML-like control tags | Fine-grained pronunciation, emphasis, pauses in generated speech | MEDIUM | Would need to parse and translate to engine-native format |

#### Voice Cloning Worker

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Multi-engine support (GPT-SoVITS + Chatterbox) | GPT-SoVITS for quality+multilingual, Chatterbox for speed+English. No single engine wins everything | HIGH | Two engines; same pattern as TTS worker. Engine selection via env var |
| Few-shot fine-tuning mode (1-5 min audio) | Zero-shot is fast but lower quality; users with 1-5 min of clean audio get dramatically better results with fine-tuning | HIGH | GPT-SoVITS excels here; needs training step (10-30 min on GPU) |
| Voice conversion (audio-to-audio) | Input audio in voice A, output same content in voice B. Huge for dubbing, podcasting, content localization | HIGH | Seed-VC or RVC can do this. Different from TTS-based cloning |
| Emotion/style control | Generate same text with different emotions (happy, sad, neutral, excited) | MEDIUM | CosyVoice2 and GPT-SoVITS v4 support this |
| Speaker embedding extraction | Return the speaker embedding vector so users can reuse it across requests without re-uploading reference audio | MEDIUM | Saves time on repeated cloning; store embedding, skip processing |
| Real-time voice conversion | Low-latency (<200ms) voice transformation for live streaming/gaming | HIGH | RVC specializes in this; requires careful latency optimization |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems. Deliberately NOT building these.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Built-in training pipeline in STT worker | Users want to fine-tune Whisper on their domain | Massively increases Docker image size, complicates handler, training is a different workload pattern than inference | Separate `whisper-trainer` worker if demand exists; keep inference workers lean |
| Real-time streaming STT (WebSocket) | Voice assistants, live captioning need real-time | RunPod serverless is request-response, not persistent connections. WebSocket support exists but adds massive complexity. Cold starts kill the use case | Use RunPod Pods (not serverless) for real-time STT; our worker targets batch/async |
| Multi-model ensemble (run 3 models, pick best result) | Higher accuracy through consensus | 3x GPU cost, 3x latency, marginal accuracy gain. Users don't want to pay for this | Offer the best single model (large-v3-turbo) as default |
| Voice cloning model training from scratch | Users want to train on 100+ hours for maximum quality | This is a research workload, not a serverless inference task. Docker image would be 50GB+. Training takes hours | Provide few-shot fine-tuning (1-5 min audio) which covers 95% of use cases |
| DRM/watermarking of cloned voices | Enterprise compliance, prevent misuse | Adds latency, requires complex infrastructure, fragmented standards. Not our problem to solve at the inference layer | Document ethical use guidelines; let users add watermarking in post-processing |
| UI/WebUI for any worker | Users want a visual interface for testing | Increases attack surface, adds frontend dependencies, increases image size. RunPod has its own console UI | Provide clean API docs and example curl commands; RunPod console handles the UI |
| Monolithic audio worker (TTS + STT + cloning in one) | Seems convenient to have everything in one image | Massive Docker image (20-50GB), conflicting dependencies between engines, slow cold starts, can't scale components independently | Separate workers per domain; link them in the hub registry |

## Feature Dependencies

```
[STT: Audio Input Handling]
    |-- requires --> [URL/Base64 parsing] (shared utility)
    |-- requires --> [Model Download/Cache] (shared pattern from llama.cpp worker)

[STT: Speaker Diarization]
    |-- requires --> [STT: Basic Transcription]
    |-- requires --> [STT: Word Timestamps]
    |-- requires --> [pyannote-audio models + HF token]

[STT: Forced Alignment]
    |-- requires --> [STT: Basic Transcription]
    |-- requires --> [wav2vec2 alignment model]

[STT: SRT/VTT Output]
    |-- requires --> [STT: Word Timestamps]

[Voice Clone: Zero-Shot Synthesis]
    |-- requires --> [Voice Clone: Reference Audio Processing]
    |-- requires --> [Voice Clone: Text Processing]

[Voice Clone: Few-Shot Fine-Tuning]
    |-- requires --> [Voice Clone: Zero-Shot Synthesis]
    |-- enhances --> [Voice Clone: Quality] (dramatically)

[Voice Clone: Voice Conversion]
    |-- independent of --> [Voice Clone: Text-Based Synthesis]
    |-- requires --> [Separate engine: RVC or Seed-VC]

[Voice Clone: Speaker Embedding Cache]
    |-- requires --> [Voice Clone: Zero-Shot Synthesis]
    |-- enhances --> [Voice Clone: Repeated Requests] (skip re-processing)

[TTS: Streaming Output]
    |-- requires --> [RunPod WebSocket handler]
    |-- conflicts with --> [Simple sync handler pattern]
```

### Dependency Notes

- **Diarization requires word timestamps:** You need aligned words before you can assign them to speakers.
- **SRT/VTT requires timestamps:** Subtitle formats are meaningless without timing data.
- **Few-shot fine-tuning enhances zero-shot:** The zero-shot pipeline must work first; fine-tuning improves it.
- **Voice conversion is independent of TTS-based cloning:** These are fundamentally different pipelines (audio-in-audio-out vs text-in-audio-out).
- **Streaming conflicts with sync pattern:** RunPod has two handler types (sync and generator). Streaming requires the generator handler, which changes the response contract.

## MVP Definition

### STT Worker -- Launch With (v1)

- [ ] **faster-whisper transcription** -- Core value; fast, accurate STT
- [ ] **Multiple model sizes** (turbo default, large-v3 for quality) -- User choice
- [ ] **Word-level timestamps** -- Table stakes for any modern STT
- [ ] **SRT/VTT/plain text output** -- Subtitle generation is the top use case
- [ ] **Language detection + translation** -- Built into Whisper, free to enable
- [ ] **VAD enabled by default** -- Prevents hallucination, production-quality
- [ ] **Audio input via URL or base64** -- Standard RunPod pattern
- [ ] **Speaker diarization via WhisperX** -- THE differentiator vs RunPod's official worker. Without this, there is no reason to use our worker over theirs

### STT Worker -- Add After Validation (v1.x)

- [ ] **Batch transcription** (multiple files per job) -- When users request it
- [ ] **Forced alignment mode** -- When subtitle/dubbing users appear
- [ ] **Large file optimization** (3hr+ handling) -- When content creators adopt

### STT Worker -- Future Consideration (v2+)

- [ ] **Multi-engine toggle** (faster-whisper vs WhisperX) -- When engine-specific tuning matters
- [ ] **Custom vocabulary/context biasing** -- When domain-specific users appear

### Voice Cloning Worker -- Launch With (v1)

- [ ] **Zero-shot voice cloning** from 5-30s reference audio -- Core value proposition
- [ ] **GPT-SoVITS engine** -- Best open-source quality, multilingual
- [ ] **Text + reference audio input** -- Standard I/O contract
- [ ] **Cross-lingual synthesis** (EN, CN, JP, KR) -- Built into GPT-SoVITS
- [ ] **48kHz audio output** -- GPT-SoVITS v4 native; matches commercial quality
- [ ] **WAV + MP3 output formats** -- Minimum viable output options
- [ ] **Audio input via URL or base64** -- Standard RunPod pattern

### Voice Cloning Worker -- Add After Validation (v1.x)

- [ ] **Chatterbox engine** (second engine) -- When English-only speed use case emerges
- [ ] **Few-shot fine-tuning mode** -- When users want higher quality with more audio
- [ ] **Emotion/style control** -- When creative/entertainment users adopt
- [ ] **Speaker embedding cache** -- When repeated-cloning pattern appears

### Voice Cloning Worker -- Future Consideration (v2+)

- [ ] **Voice conversion (audio-to-audio)** -- Different product, may warrant separate worker
- [ ] **Real-time voice conversion** -- Requires Pods, not serverless
- [ ] **RVC engine integration** -- If music/singing voice conversion demand emerges

### TTS Worker -- Already Shipped, Potential v1.x Additions

- [ ] **Word-level timestamps in output** -- Low effort, high value for lip-sync
- [ ] **Voice mixing** -- Kokoro supports natively
- [ ] **Additional engine: Chatterbox** -- Already have Kokoro/Dia/F5

## Feature Prioritization Matrix

### STT Worker

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Basic transcription (faster-whisper) | HIGH | LOW | P1 |
| Word-level timestamps | HIGH | LOW | P1 |
| SRT/VTT output | HIGH | LOW | P1 |
| Language detection | HIGH | LOW | P1 |
| VAD | HIGH | LOW | P1 |
| Speaker diarization | HIGH | HIGH | P1 (differentiator) |
| Translation to English | MEDIUM | LOW | P1 |
| Batch transcription | MEDIUM | MEDIUM | P2 |
| Forced alignment | MEDIUM | MEDIUM | P2 |
| Large file handling (3hr+) | MEDIUM | MEDIUM | P2 |
| Multi-engine toggle | LOW | HIGH | P3 |

### Voice Cloning Worker

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Zero-shot voice cloning | HIGH | HIGH | P1 |
| Cross-lingual synthesis | HIGH | LOW (built-in) | P1 |
| 48kHz output quality | HIGH | LOW (native v4) | P1 |
| Multiple output formats | MEDIUM | LOW | P1 |
| Second engine (Chatterbox) | MEDIUM | HIGH | P2 |
| Few-shot fine-tuning | MEDIUM | HIGH | P2 |
| Emotion/style control | MEDIUM | MEDIUM | P2 |
| Speaker embedding cache | LOW | MEDIUM | P2 |
| Voice conversion (audio-to-audio) | MEDIUM | HIGH | P3 |
| Real-time conversion | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

### STT Landscape on RunPod

| Feature | RunPod Official (worker-faster_whisper) | Dembrane (WhisperX) | Our Approach |
|---------|----------------------------------------|---------------------|--------------|
| Basic transcription | Yes | Yes | Yes |
| Word timestamps | Yes (optional) | Yes (forced alignment) | Yes (default on) |
| Speaker diarization | **NO** | Yes | **Yes -- key differentiator** |
| SRT/VTT output | Yes | Limited | Yes |
| Translation | Yes | Yes | Yes |
| VAD | Optional | Yes (Silero) | Default on |
| Model selection | 10 models | Fixed | Preset-based (hub.json) |
| Large file support | Limited | 3hr+ | Optimized |
| Maintained (2025+) | Sporadic updates | Active | Active |

### Voice Cloning Landscape on RunPod

| Feature | OpenVoice Worker | Chatterbox Worker (community) | Our Approach |
|---------|-----------------|-------------------------------|--------------|
| Zero-shot cloning | Yes | Yes | Yes (GPT-SoVITS v4) |
| Voice quality | Medium | High (English) | High (multilingual) |
| Multilingual | Limited | English-focused | EN/CN/JP/KR |
| Few-shot fine-tuning | No | No | Planned (v1.x) |
| Voice conversion | No | No | Planned (v2) |
| Maintained | Abandoned | Fragmented | Active |
| RunPod Hub presets | No | No | Yes (hub.json) |
| Engine flexibility | Single engine | Single engine | Multi-engine |

### TTS Landscape on RunPod (for context)

| Feature | RunPod XTTS Workers | Our TTS Worker (shipped) | Notes |
|---------|---------------------|--------------------------|-------|
| Engine variety | XTTS only | Kokoro + Dia + F5 | We win on variety |
| Voice count | Limited | 50+ (Kokoro) | We win |
| Quality | Medium | High | Kokoro is SOTA for size |
| Maintained | Most abandoned | Active | We win |
| Hub presets | None | 3 presets | We win |

## Sources

### STT Research
- [RunPod Official Faster Whisper Worker](https://github.com/runpod-workers/worker-faster_whisper) -- Feature baseline and gaps identified
- [WhisperX](https://github.com/m-bain/whisperX) -- Diarization + forced alignment capabilities
- [Modal: Choosing Whisper Variants](https://modal.com/blog/choosing-whisper-variants) -- Comparison of faster-whisper vs WhisperX vs insanely-fast-whisper
- [Modal: Top Open Source STT Models](https://modal.com/blog/open-source-stt) -- 2025 landscape
- [Together AI: Whisper APIs](https://www.together.ai/blog/speech-to-text-whisper-apis) -- Commercial feature expectations
- [Deepgram: Whisper vs Deepgram](https://deepgram.com/learn/whisper-vs-deepgram) -- Feature comparison
- [AssemblyAI: Best APIs for Real-Time Speech Recognition 2026](https://www.assemblyai.com/blog/best-api-models-for-real-time-speech-recognition-and-transcription) -- Industry expectations

### Voice Cloning Research
- [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) -- v3/v4 features, API spec
- [GPT-SoVITS v3/v4 Features Wiki](https://github.com/RVC-Boss/GPT-SoVITS/wiki/GPT%E2%80%90SoVITS%E2%80%90v3v4%E2%80%90features) -- 48kHz output, quality improvements
- [Resemble AI: Best Open Source Voice Cloning Tools 2026](https://www.resemble.ai/best-open-source-ai-voice-cloning-tools/) -- Landscape overview
- [SiliconFlow: Best Models for Voice Cloning](https://www.siliconflow.com/articles/en/best-open-source-models-for-voice-cloning) -- Fish Speech, CosyVoice2, IndexTTS-2
- [RunPod: RVC Deployment Guide](https://www.runpod.io/articles/guides/ai-engineer-guide-rvc-cloud) -- RVC on RunPod patterns
- [Chatterbox](https://github.com/resemble-ai/chatterbox) -- Speed-focused English cloning

### TTS Research
- [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) -- Feature reference for Kokoro capabilities
- [Speechmatics: Best TTS APIs 2026](https://www.speechmatics.com/company/articles-and-news/best-tts-apis-in-2025-top-12-text-to-speech-services-for-developers) -- Commercial feature expectations

### RunPod Platform
- [RunPod Serverless Overview](https://docs.runpod.io/serverless/overview) -- Handler patterns, I/O constraints
- [RunPod Worker Template](https://github.com/runpod-workers/worker-template) -- Standard worker structure

---
*Feature research for: RunPod Audio AI Workers (TTS, STT, Voice Cloning)*
*Researched: 2026-03-14*
