# Pitfalls Research

**Domain:** Audio AI inference workers (TTS, STT, voice cloning) on RunPod Serverless
**Researched:** 2026-03-14
**Confidence:** HIGH (verified against RunPod docs, GitHub issues, community reports)

## Critical Pitfalls

### Pitfall 1: RunPod 10MB Payload Limit Kills Audio I/O

**What goes wrong:**
Audio files (both input and output) exceed RunPod's fixed 10MB payload limit. A 30-second WAV at 44.1kHz/16-bit is ~2.5MB raw, but base64 encoding adds 33% overhead. Longer audio, higher sample rates, or multi-channel audio quickly blows past 10MB. The streaming yield limit is even worse at 1MB per chunk. Developers build the handler returning base64 audio, it works for short clips in testing, then fails on real-world inputs.

**Why it happens:**
The llama.cpp worker pattern returns JSON directly -- text is small. Developers carry this pattern into audio workers without realizing that audio binary data is fundamentally different. RunPod's payload limits are fixed and cannot be increased.

**How to avoid:**
- **Input:** Accept audio via URL (S3, GCS, or RunPod's own S3-compatible API) rather than base64. Download inside the handler. URL-based input supports >1GB files limited only by disk space and timeout.
- **Output:** Upload generated audio to cloud storage (RunPod S3 API or external bucket) from within the handler and return a presigned URL. Follow the pattern used by `runpod-workers/worker-comfyui`: check for `BUCKET_ENDPOINT_URL` env var, upload if configured, fall back to base64 only for tiny outputs.
- **Fallback:** For outputs under ~7MB pre-encoding (~5MB base64), base64 is acceptable. But always build the S3 upload path first.

**Warning signs:**
- Handler tests only use short audio clips (< 5 seconds)
- No cloud storage integration in the handler
- Error messages like "payload too large" or truncated responses in production

**Phase to address:**
Phase 1 (shared worker template) -- establish the URL-in/URL-out pattern before building any audio worker. Every audio worker inherits this pattern.

---

### Pitfall 2: GPU Memory Leaks in Long-Running Audio Workers

**What goes wrong:**
Audio models (especially TTS) leak GPU memory over successive requests. Kokoro TTS starts at 1.8GB VRAM after the first sentence, then climbs steadily -- memory is never released even after synthesis completes. Faster-whisper shows the same pattern: memory utilization grows to 100% until the container is OOM-killed. CUDA contexts accumulate fragments that `torch.cuda.empty_cache()` cannot reclaim.

**Why it happens:**
Unlike the llama.cpp worker (which runs a separate C++ server process with its own memory management), PyTorch-based audio models run in-process in Python. PyTorch's CUDA allocator fragments memory over many allocations/deallocations. TTS models create variable-length tensors per request (unlike LLMs with fixed KV-cache), making fragmentation worse. RunPod serverless workers are designed to handle many requests per cold start, so this compounds.

**How to avoid:**
- Set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` to reduce fragmentation.
- Call `torch.cuda.empty_cache()` after every request (necessary but not sufficient).
- For models with known leaks (Kokoro, faster-whisper): track VRAM usage via `torch.cuda.memory_allocated()` and force-restart the worker process after N requests or when VRAM exceeds a threshold (e.g., 80% of available).
- Consider running the inference engine as a subprocess (like the llama.cpp pattern) so the OS reclaims all memory on subprocess restart, rather than fighting Python/CUDA memory management.
- Set explicit `max_concurrent_requests: 1` in RunPod endpoint config for TTS workers -- concurrent requests multiply memory issues.

**Warning signs:**
- Worker handles first 10 requests fine, then starts failing
- OOM errors appear only in production, never in single-request testing
- nvidia-smi shows growing memory between requests with no decline

**Phase to address:**
Phase 1 (shared template) -- build memory monitoring into the base handler class. Phase 2 (per-engine) -- test each engine with 100+ sequential requests to verify stability.

---

### Pitfall 3: Docker Image Bloat Causes Catastrophic Cold Starts

**What goes wrong:**
PyTorch + CUDA + audio libraries (librosa, soundfile, scipy, transformers) + model weights baked into the image creates images exceeding 15-20GB. RunPod must pull this image on every cold start to a new worker. At datacenter speeds, a 20GB image takes 30-60+ seconds to pull. For a TTS request that takes 2 seconds of inference, users wait 30x longer for cold start than for actual work. Hub users see terrible first-request latency and churn.

**Why it happens:**
The llama.cpp worker avoids this because it compiles a static binary (no PyTorch) and downloads models at runtime. Audio workers need PyTorch, which alone is 2-4GB. Adding full CUDA toolkit, transformers, and audio processing libraries compounds the problem. Baking model weights into the image (tempting for "instant" startup) makes it catastrophically worse.

**How to avoid:**
- Never bake model weights into the Docker image. Download at startup (the pattern already established in `download_model.py`), cache on network volume.
- Use `nvidia/cuda:12.4.1-runtime-ubuntu22.04` (not `-devel-`). The runtime image is ~2GB smaller.
- Install PyTorch with only CUDA runtime, not the full toolkit: `pip install torch --index-url https://download.pytorch.org/whl/cu124` (not from default which may include full CUDA).
- Use multi-stage builds: compile any C extensions in a builder stage, copy only artifacts.
- Pin exact package versions to avoid pulling unnecessary transitive dependencies.
- Target image size under 8GB (ideally under 6GB) for reasonable cold starts with FlashBoot.

**Warning signs:**
- `docker images` shows image > 10GB
- Cold start times > 30 seconds in RunPod logs
- Model weights appear in Docker layers (check with `docker history`)

**Phase to address:**
Phase 1 (Dockerfile template) -- establish the slim image pattern before building any worker. Measure cold start time as a release gate.

---

### Pitfall 4: Whisper Hallucinations and Missing Segments on Long Audio

**What goes wrong:**
Whisper processes audio in 30-second chunks internally. On long-form audio (>5 minutes), it can: (a) hallucinate repeated text that does not exist in the audio, (b) skip entire 10-40 second segments of speech without warning, (c) produce different transcriptions for the same file depending on `chunk_length` and `hop_length` parameters. There is no error -- the output simply silently omits or fabricates content.

**Why it happens:**
Whisper's attention mechanism was designed for short utterances. Long-form transcription is a post-hoc chunking strategy, not a native capability. Chunk boundaries can fall mid-sentence, confusing the model. Without VAD (Voice Activity Detection), silence and background noise get fed to the model as "speech" to transcribe, triggering hallucinations. The overlap/stride between chunks directly affects boundary accuracy.

**How to avoid:**
- Always enable VAD preprocessing: `vad_filter=True` in faster-whisper. This filters silence before feeding to Whisper, dramatically reducing hallucinations.
- Use `chunk_length=30` with `stride_length_s=(4, 2)` (left stride 4s, right stride 2s) for overlap at boundaries. Test with your specific audio types.
- Implement audio duration limits per request (e.g., 2 hours max) and document them.
- For very long files, implement server-side chunking with overlap and deduplication in the handler, rather than relying on Whisper's internal chunking.
- Return word-level timestamps so callers can verify coverage: gaps in timestamps reveal skipped segments.
- Consider offering both `whisper-large-v3-turbo` (faster, good accuracy) and `whisper-large-v3` (slower, better accuracy) as separate presets.

**Warning signs:**
- Transcription output contains repeated phrases not in the source audio
- Transcription is significantly shorter than expected for the audio duration
- Users report "missing parts" in transcriptions

**Phase to address:**
Phase 2 (STT worker) -- VAD must be enabled by default. Test with files >10 minutes. Include timestamp output in the default response format.

---

### Pitfall 5: Sample Rate Mismatches Between Models and Input/Output

**What goes wrong:**
Different audio models operate at different native sample rates: Whisper expects 16kHz, Kokoro outputs 24kHz, F5-TTS outputs 24kHz, Bark outputs 24kHz, RVC operates at 40kHz or 48kHz. When input audio arrives at a different sample rate than the model expects (or output is saved without matching the model's native rate), you get: degraded quality, artifacts, pitch shifting, or outright crashes. Resampling in the wrong direction (upsampling low-quality to high sample rate) wastes bandwidth without improving quality.

**Why it happens:**
Developers test with their own recordings (usually 44.1kHz or 48kHz) and everything works because libraries silently resample. But the silent resampling can introduce artifacts, and the developer never validates output quality programmatically. Users then send 8kHz phone recordings or 96kHz studio recordings and get unexpected results.

**How to avoid:**
- Explicitly resample all input audio to the model's native rate at the start of the handler using `librosa.resample()` or `torchaudio.transforms.Resample`.
- Document the native sample rate per engine/preset in the API response metadata.
- Output audio at the model's native sample rate (don't upsample for aesthetics).
- For STT: accept any sample rate, always downsample to 16kHz before feeding to Whisper.
- For TTS: return at the model's native rate, include `sample_rate` in the response JSON.
- For voice cloning: validate reference audio sample rate and quality before processing. Reject or warn on sample rates below 16kHz.

**Warning signs:**
- Audio output sounds "metallic" or has artifacts
- Different behavior between test audio and user-submitted audio
- No explicit resampling code in the handler

**Phase to address:**
Phase 1 (shared template) -- standardize audio I/O utilities (load, resample, validate, encode). Phase 2 (per-engine) -- verify sample rates per model.

---

### Pitfall 6: Voice Cloning Reference Audio Quality Not Validated

**What goes wrong:**
Voice cloning quality is almost entirely dependent on reference audio quality. Users submit noisy recordings, multi-speaker audio, music-contaminated clips, or sub-3-second samples. The model runs without error but produces garbage output -- robotic voices, wrong speaker characteristics, or unintelligible speech. Users blame the service, not their input. This is the #1 source of user complaints for voice cloning services.

**Why it happens:**
Voice cloning models accept any audio tensor without validation. There is no built-in quality gate. The model extracts speaker embeddings regardless of audio quality, but poor-quality embeddings produce poor output. Quality scales roughly linearly from 3-15 seconds of reference, then plateaus. Above ~30dB SNR is the practical threshold for reliable cloning.

**How to avoid:**
- Validate reference audio before processing:
  - Minimum duration: 5 seconds (recommended 10-15 seconds)
  - Maximum duration: 60 seconds (longer does not help and wastes compute)
  - Single speaker detection: use a speaker diarization check or energy-based heuristic
  - SNR estimation: reject audio with estimated SNR < 20dB
  - Sample rate: require >= 16kHz
- Return quality metrics alongside the cloned output (speaker similarity score, SNR estimate)
- Provide clear API documentation specifying reference audio requirements
- Pre-process reference audio: normalize volume, trim silence, apply light noise reduction

**Warning signs:**
- Handler accepts reference audio without any validation
- No documentation about reference audio requirements
- Users consistently rate output quality as poor despite model working correctly

**Phase to address:**
Phase 3 (voice cloning worker) -- build audio validation utilities into the handler. Include a "reference audio quality" score in the response.

---

### Pitfall 7: No Graceful Handling of Model Load Failures Across Engines

**What goes wrong:**
With the multi-engine pattern (e.g., `TTS_ENGINE=kokoro`), a misconfigured engine env var or incompatible GPU architecture causes the model to fail to load at startup. The worker crashes with an opaque CUDA error, RunPod marks it as failed, spins up a new one, which also fails, creating a crash loop that burns GPU credits. Users see perpetual "IN_QUEUE" status.

**Why it happens:**
Audio models have more complex GPU requirements than LLMs. Some need specific CUDA compute capabilities, specific PyTorch versions, or specific CUDA toolkit versions. Engine A might work on an A5000 but Engine B needs an A100 for its attention mechanism. The handler crashes at module-level (like the current llama.cpp pattern) with no fallback or useful error reporting.

**How to avoid:**
- Wrap model loading in try/except at startup. On failure, set the worker to a "degraded" state that returns informative error messages for every request rather than crashing.
- Log the GPU architecture, VRAM, CUDA version, and PyTorch version at startup before attempting model load.
- Test each engine preset on every target GPU type (T4, A5000, A100, L4, L40S, H100) before publishing to Hub.
- Set a startup health check that returns the model load status (already done in llama.cpp worker with `/health` polling, but PyTorch-based workers need equivalent).
- Document minimum GPU requirements per preset in `hub.json`.

**Warning signs:**
- `hub.json` presets do not specify GPU requirements or specify overly broad ones
- No try/except around model initialization code
- Worker tested on only one GPU type

**Phase to address:**
Phase 1 (shared template) -- structured startup with error capture. Phase 2/3 (each worker) -- GPU compatibility matrix testing.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Base64 for all audio I/O | Simple handler, no cloud storage dependency | Breaks on any audio > ~7MB, hits payload limits | Only for MVP testing with short clips; must add S3 before Hub publishing |
| Baking model weights into Docker image | Zero download time at startup | 15-20GB images, 60s+ cold starts, image rebuild for every model update | Never -- download at runtime, cache on volume |
| Single `handler.py` without engine abstraction | Fast initial development | Cannot add new engines without rewriting handler; preset logic becomes spaghetti | Only if the worker will genuinely only ever support one model |
| Skipping audio validation on input | Fewer lines of code, faster handler | Garbage-in/garbage-out complaints, wasted GPU compute on unprocessable input | MVP phase only; add validation before Hub publishing |
| No memory monitoring between requests | Simpler handler code | Silent OOM crashes after N requests in production | Never -- at minimum log VRAM usage per request |
| Using `pip install torch` without specifying CUDA index | Works on dev machine | May pull CPU-only PyTorch or wrong CUDA version, adding 2GB of unnecessary packages | Never -- always pin to `--index-url https://download.pytorch.org/whl/cu124` |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| RunPod S3 API | Hardcoding AWS S3 endpoints, requiring users to bring their own bucket | Use RunPod's built-in S3-compatible API (`docs.runpod.io/storage/s3-api`). Credentials via `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` env vars. Fall back to base64 if not configured. |
| HuggingFace Hub (model download) | Using `from_pretrained()` which downloads to `~/.cache` (ephemeral in containers) | Use `hf_hub_download()` with explicit `local_dir` pointed at network volume path `/runpod-volume/models`, matching the established pattern in `download_model.py`. |
| RunPod Network Volume | Assuming volume is always mounted, crashing if missing | Check `os.path.isdir("/runpod-volume")` first, fall back to `/tmp/models`. Already done correctly in the llama.cpp worker -- replicate this pattern. |
| PyTorch CUDA initialization | Loading model at import time (module-level), before CUDA context is ready | Initialize CUDA explicitly (`torch.cuda.init()`) and log GPU info before model load. Wrap in try/except with informative error messages. |
| RunPod Serverless SDK | Not returning proper error format, causing "FAILED" job status with no user-visible message | Always return `{"error": "descriptive message"}` dict on failure, never raise unhandled exceptions. The SDK captures exceptions but the error message is often unhelpful. |
| Audio format libraries (soundfile, librosa) | Installing without system-level `libsndfile1` dependency | Add `apt-get install -y libsndfile1` in Dockerfile before `pip install soundfile`. Without it, import succeeds but reading WAV/FLAC fails at runtime. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading model per request instead of at startup | 5-30 second latency per request, GPU utilization spikes then drops | Load model once at module-level (startup), reuse for all requests. Follow the llama.cpp pattern of startup-then-serve. | Immediately -- first user request |
| No concurrent request limiting for TTS | GPU OOM on second concurrent request, both requests fail | Set `max_concurrency: 1` in RunPod endpoint config for TTS/voice cloning. Whisper can handle 2-3 concurrent with batching on larger GPUs. | At 2+ concurrent requests |
| Whisper VAD running on CPU when GPU is available | 2-3x slower transcription on long audio files | Configure faster-whisper with `device="cuda"` for the Silero VAD model. By default, VAD runs on CPU even when the main model is on GPU. | Audio files > 10 minutes |
| Returning full WAV when MP3 would suffice | 10x larger response payloads, S3 storage costs, slower downloads | Default to MP3 (or OGG/Opus) for TTS output, with `format` parameter to request WAV. Keep WAV as option for quality-sensitive use cases. | Response size exceeds 10MB payload limit |
| Not using network volume for model caching | Full model download on every cold start (2-10GB per engine) | Cache models on `/runpod-volume/models/`. Check cache first, download only if missing. The `download_model.py` pattern handles this. | Every cold start costs 30-120s extra |
| Running all TTS engines in one container | Massive image size (each engine adds 2-5GB), massive VRAM usage | One engine per preset/container. Select engine via env var, only load the selected engine at startup. | Image > 15GB, cold start > 60s |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Accepting arbitrary file URLs for STT input without validation | SSRF attacks -- worker can be used to probe internal RunPod network, access metadata endpoints | Validate URL scheme (https only), block private IP ranges (10.x, 172.16-31.x, 192.168.x, 169.254.x), set timeout on download, limit file size |
| Storing user audio on network volume without cleanup | Disk fills up, other users' audio may be accessible if volume is shared | Process audio in `/tmp`, delete after response. Never persist user audio on the network volume (only cache model weights there). |
| No rate limiting on voice cloning endpoint | Abuse for deepfake generation at scale, potential platform ToS violation | Document ethical use policy. Consider per-API-key rate limits via RunPod's built-in throttling. Log job metadata for audit trail. |
| Exposing HuggingFace token in error messages or logs | Token leaked, attacker gains access to private repos or gated models | Never log the `HF_TOKEN` value. Use `HF_TOKEN[:4]+"***"` in status messages. Set as RunPod secret, not plain env var. |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Returning audio as raw base64 string without metadata | User has to guess format, sample rate, duration. Cannot play without decoding. | Return structured JSON: `{"audio_url": "...", "format": "mp3", "sample_rate": 24000, "duration_seconds": 3.2}`. If base64: include format and sample rate. |
| No progress indication for long STT jobs | User submits 60-minute audio, sees no feedback for 5+ minutes, assumes it failed | Use RunPod's streaming/yield to report progress: `{"status": "processing", "progress": 0.45, "segments_completed": 27}` |
| TTS returns error for text > N characters without explaining the limit | User gets opaque error, has to guess why their request failed | Validate text length upfront, return clear message: `{"error": "Text exceeds maximum length of 5000 characters. Split into smaller segments."}` Include the limit in API docs and error response. |
| Voice cloning produces output without quality metrics | User cannot tell if poor output is due to bad reference audio or model limitations | Return quality indicators: `{"speaker_similarity": 0.82, "reference_audio_quality": "good", "snr_db": 35.2}` |
| STT returns only text without timestamps or segments | User cannot navigate long transcriptions, cannot sync with video/audio | Return segments with timestamps by default: `[{"start": 0.0, "end": 2.5, "text": "Hello world"}]`. Offer word-level timestamps as option. |

## "Looks Done But Isn't" Checklist

- [ ] **TTS Worker:** Often missing audio format options -- verify handler accepts `format` parameter (mp3/wav/ogg) and converts output accordingly
- [ ] **STT Worker:** Often missing VAD filter -- verify `vad_filter=True` is set, otherwise hallucinations on silence/noise sections
- [ ] **STT Worker:** Often missing long-audio handling -- verify with a 30+ minute file, check for missing segments in output
- [ ] **Voice Cloning:** Often missing reference audio validation -- verify handler rejects < 3 second clips, noisy audio, multi-speaker audio
- [ ] **All Audio Workers:** Often missing S3 upload for output -- verify large output (>5MB) is uploaded to storage and URL returned
- [ ] **All Audio Workers:** Often missing memory cleanup -- verify `torch.cuda.empty_cache()` called after each request, test with 50+ sequential requests
- [ ] **All Audio Workers:** Often missing error handling for corrupt audio input -- verify handler gracefully rejects invalid audio files (wrong format, truncated, zero-length)
- [ ] **Hub Presets:** Often missing GPU requirements -- verify each preset in `hub.json` specifies appropriate GPU tier (not just "any GPU")
- [ ] **Docker Image:** Often includes model weights -- verify `docker history` shows no large layers from model files; models should download at runtime
- [ ] **All Workers:** Often missing input validation -- verify handler rejects requests with missing required fields before GPU compute starts

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Base64 payload limit hit in production | LOW | Add S3 upload code path, deploy new image, existing API contract can add `audio_url` field alongside `audio_base64` for backward compatibility |
| GPU memory leak causing OOM in production | MEDIUM | Add `torch.cuda.empty_cache()` + VRAM monitoring as immediate fix. For persistent leaks, add subprocess restart logic (MEDIUM effort) or move to subprocess-based engine like llama.cpp pattern (HIGH effort) |
| Docker image too large (>15GB) | MEDIUM | Multi-stage Dockerfile rebuild, switch to runtime base image, remove baked-in weights. Requires image rebuild and re-push but no code changes |
| Whisper hallucinating on long audio | LOW | Enable VAD filter (`vad_filter=True`), tune chunk parameters. Config change, no architecture change needed |
| Wrong sample rate in output | LOW | Add explicit resampling in handler output path. Small code change, no architecture impact |
| Voice cloning quality complaints | MEDIUM | Add input validation layer (audio quality checks). Requires new validation code but does not change the inference pipeline |
| Engine fails on specific GPU type | MEDIUM | Add GPU compatibility check at startup, update `hub.json` GPU specifications. May require testing on multiple GPU types (time-consuming) |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 10MB payload limit (audio I/O) | Phase 1: Shared Template | Upload a 30-second WAV through the worker, verify URL returned (not base64) |
| GPU memory leaks | Phase 1: Shared Template (monitoring), Phase 2-3: Per-engine (testing) | Run 100 sequential requests, verify VRAM stays within 20% of initial value |
| Docker image bloat | Phase 1: Dockerfile Template | `docker images` shows < 8GB. Cold start measured < 15 seconds on RunPod |
| Whisper long-audio issues | Phase 2: STT Worker | Transcribe a 30-minute podcast, compare word count to actual spoken content |
| Sample rate mismatches | Phase 1: Shared audio utilities | Send 8kHz, 16kHz, 44.1kHz, 48kHz audio through each worker, verify consistent output quality |
| Voice cloning reference quality | Phase 3: Voice Cloning Worker | Submit 2-second noisy clip, verify rejection with helpful error message |
| Engine load failures | Phase 1: Shared Template (startup structure) | Start worker with invalid engine env var, verify informative error in job response (not crash loop) |
| SSRF via audio URLs | Phase 1: Shared Template (URL validation) | Attempt to fetch `http://169.254.169.254/latest/meta-data/`, verify rejection |
| No progress for long jobs | Phase 2: STT Worker (streaming progress) | Submit 60-minute audio, verify progress updates appear via RunPod status API |

## Sources

- [RunPod Endpoint Configurations (payload limits, timeouts)](https://docs.runpod.io/serverless/endpoints/endpoint-configurations)
- [RunPod: How to get around 10/20MB payload limit](https://www.answeroverflow.com/m/1199970565381967982)
- [RunPod GPU OOM Survival Guide](https://www.runpod.io/articles/guides/avoid-oom-crashes-for-large-models)
- [RunPod S3-Compatible API](https://docs.runpod.io/storage/s3-api)
- [RunPod: Guide to deploying RVC in the cloud](https://www.runpod.io/articles/guides/ai-engineer-guide-rvc-cloud)
- [Kokoro-FastAPI: Memory leak and performance issue (#262)](https://github.com/remsky/Kokoro-FastAPI/issues/262)
- [faster-whisper: Memory not releasing (#660)](https://github.com/SYSTRAN/faster-whisper/issues/660)
- [faster-whisper: High memory use (#249)](https://github.com/SYSTRAN/faster-whisper/issues/249)
- [faster-whisper: Audio segmentation behavior (#456)](https://github.com/SYSTRAN/faster-whisper/issues/456)
- [Whisper long-form transcription: missing segments](https://community.openai.com/t/whisper-leaves-out-chunks-of-speech-in-longer-transcript/715999)
- [F5-TTS: Minimal GPU memory requirements (#197)](https://github.com/SWivid/F5-TTS/issues/197)
- [Deepgram: Open Source TTS Production Deployment Guide](https://deepgram.com/learn/open-source-text-to-speech-production-guide)
- [Fish Audio: Voice Cloning Guide (reference audio quality)](https://fish.audio/blog/voice-cloning-guide/)
- [Cold starts: From 3-minute to ~20 seconds (Whisper on Lambda)](https://dev.to/aws-builders/from-3-minute-cold-starts-to-20-seconds-whisper-on-aws-lambda-efs-for-openclaw-9c5)
- [RunPod serverless Whisper pipeline guide](https://www.runpod.io/articles/guides/how-do-i-build-a-scalable-low-latency-speech-recognition-pipeline-on-runpod-using-whisper-and-gpus)

---
*Pitfalls research for: Audio AI inference workers (TTS, STT, voice cloning) on RunPod Serverless*
*Researched: 2026-03-14*
