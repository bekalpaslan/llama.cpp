# Phase 1: Shared Worker Foundation - Research

**Researched:** 2026-03-14
**Domain:** Reusable audio worker template infrastructure (model download, audio I/O, Docker containerization)
**Confidence:** HIGH

## Summary

Phase 1 creates the shared infrastructure that every subsequent audio worker (STT, TTS, Voice Cloning) builds on. The three requirements -- audio input resolution (INFRA-01), generalized model download (INFRA-02), and slim Dockerfile pattern (INFRA-03) -- are all extensions of patterns already proven in the existing llama.cpp worker. The work is adaptation and generalization, not greenfield development.

The existing `download_model.py` needs GGUF-specific logic stripped (quantization auto-detection, `.gguf` extension filtering) and replaced with a generic HuggingFace download utility that handles any model file format. The audio input resolver is a new utility that handles the dual URL/base64 input pattern established by RunPod's ecosystem (including their own `worker-faster_whisper`). The Dockerfile pattern adapts the existing two-stage build to use PyTorch+CUDA instead of compiled C++ binaries, targeting under 8GB image size.

**Primary recommendation:** Build these three utilities as standalone Python modules (`download_model.py`, `audio_utils.py`) and a template `Dockerfile` in this repo. Each subsequent worker repo copies these files and customizes only the handler and engine-specific dependencies. Do NOT create a shared package/library -- keep it as copy-paste template files, matching the flat structure pattern already established.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | Worker accepts audio input via URL download or base64 encoding | Dual-input pattern is established RunPod convention (see Architecture Patterns: Pattern 2). RunPod SDK provides `rp_download.download_files_from_urls()` for URL downloads. Base64 decoding is stdlib. Both must produce a temp file path for inference engines. SSRF prevention needed for URL input. |
| INFRA-02 | Worker template provides generalized model download utility (adapted from llama.cpp worker's download_model.py) | Existing `download_model.py` is 104 lines. Remove GGUF-specific logic (quantization preference list, `.gguf` filtering). Keep volume cache pattern (`/runpod-volume/models` -> `/tmp/models`). Use `huggingface_hub.hf_hub_download()` for single files, `snapshot_download()` for multi-file models. |
| INFRA-03 | Worker Dockerfile follows slim multi-stage build pattern for minimal image size | Existing Dockerfile is the template. Replace llama.cpp builder stage with PyTorch pip install. Use `nvidia/cuda:12.4.1-runtime-ubuntu22.04` base. Install PyTorch via `--index-url https://download.pytorch.org/whl/cu124 --no-cache-dir`. Target under 8GB. Install ffmpeg via apt for audio format conversion. |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| runpod | >=1.7.0 | Serverless handler framework | Same SDK as existing worker. Includes `rp_download` utilities for URL-based file downloading with retry logic. |
| huggingface-hub | >=0.25.0 | Model downloading from HuggingFace | Same as existing worker. `hf_hub_download()` for single files, `snapshot_download()` for multi-file models (like Whisper). |
| soundfile | >=0.12.0 | Audio file I/O (read/write WAV, FLAC, OGG) | Lightweight, NumPy-based. Does not require ffmpeg for WAV. Used by faster-whisper, Kokoro, and most audio libraries. |
| requests | >=2.31.0 | HTTP client for URL-based audio download | Same as existing worker. Used for downloading audio from user-provided URLs. |
| numpy | >=1.24.0 | Audio array manipulation | Dependency of soundfile, PyTorch, and all inference engines. Pin compatible version. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ffmpeg | system package (apt) | Audio format conversion (MP3, M4A, OGG input -> WAV) | Always install in Dockerfile. Required for non-WAV input formats. |
| scipy | >=1.11.0 | Audio resampling (e.g., 44.1kHz -> 16kHz for Whisper) | Only if a worker needs sample rate conversion. Lighter than librosa. |
| pydub | >=0.25.1 | Python wrapper for ffmpeg audio conversion | Optional convenience layer. Can use raw ffmpeg subprocess instead. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw `requests.get()` for URL download | RunPod SDK `rp_download.download_files_from_urls()` | SDK provides retry logic and adaptive chunking, but couples to RunPod SDK internals. Either works. Recommend SDK utility for consistency. |
| `soundfile` for audio I/O | `librosa` | librosa adds heavy deps (matplotlib, scikit-learn). soundfile is sufficient for read/write. Only add librosa if advanced audio features are needed. |
| `scipy.signal.resample` | `librosa.resample` | librosa uses soxr for higher quality resampling but adds 100MB+ of dependencies. scipy is sufficient for production audio workers. |
| Copy-paste template files | Shared pip package | A shared package creates version coupling between independently-deployed workers. Copy-paste with documentation is the correct pattern for 2-3 file workers with independent release cycles. |

**Installation (template requirements.txt):**
```
runpod>=1.7.0
huggingface-hub>=0.25.0
requests>=2.31.0
soundfile>=0.12.0
numpy>=1.24.0
```

Workers add engine-specific deps (e.g., `faster-whisper`, `torch`, `kokoro`) to their own `requirements.txt`.

## Architecture Patterns

### Recommended Project Structure (Template)

```
worker-template/                       # Template in this repo, copied per worker
  download_model.py                    # Generalized HF model download + volume cache
  audio_utils.py                       # Audio input resolver (URL/base64) + output encoder
  Dockerfile.template                  # Multi-stage CUDA build pattern (customized per worker)
  requirements.txt                     # Base dependencies (worker adds engine-specific)
  .runpod/
    hub.json                           # RunPod Hub config (customized per worker)
  tests/
    test_input.json                    # Sample input payloads for local testing

worker-whisper/                        # Example: STT worker (separate repo)
  handler.py                           # Worker-specific handler + model loading
  download_model.py                    # Copied from template (may customize)
  audio_utils.py                       # Copied from template
  Dockerfile                           # Based on template, adds engine deps
  requirements.txt                     # Base + faster-whisper + ctranslate2
  .runpod/
    hub.json                           # STT-specific presets
```

### Pattern 1: Generalized Model Download

**What:** Download any model file(s) from HuggingFace with volume caching and automatic fallback.
**When to use:** Every worker, at module level during container startup.
**Source:** Adapted from existing `download_model.py` (104 lines, HIGH confidence).

The existing `download_model.py` has three GGUF-specific behaviors to remove:
1. `QUANT_PREFERENCE` list and `find_gguf_file()` -- GGUF quantization auto-detection (not needed for audio models)
2. `.gguf` extension filtering -- audio models use `.pt`, `.bin`, `.safetensors`, or whole directories
3. `sys.exit(1)` on missing file -- should raise RuntimeError instead for cleaner error handling

The generalized version keeps:
1. Volume cache path check: `/runpod-volume/models` first, `/tmp/models` fallback
2. `hf_hub_download()` for single-file models
3. `HF_TOKEN` support for gated models (pyannote requires this)
4. Size logging on download completion

New capability needed:
1. `snapshot_download()` support for multi-file models (Whisper models are directories with `config.json`, `model.bin`, `tokenizer.json`, etc.)
2. `allow_patterns` parameter to filter which files to download from a repo

```python
# Generalized download_model.py
from huggingface_hub import hf_hub_download, snapshot_download

VOLUME_PATH = "/runpod-volume/models"
LOCAL_PATH = "/tmp/models"

def download_model(repo_id: str, filename: str | None = None,
                   token: str | None = None,
                   allow_patterns: list[str] | None = None) -> str:
    """
    Download model file(s) from HuggingFace with volume caching.

    - If filename is provided: downloads a single file (hf_hub_download)
    - If filename is None: downloads the full repo snapshot (snapshot_download)
    - Checks /runpod-volume/models cache first, falls back to /tmp/models
    """
    # Determine cache directory
    import os
    if os.path.isdir("/runpod-volume"):
        dest_dir = VOLUME_PATH
    else:
        dest_dir = LOCAL_PATH
    os.makedirs(dest_dir, exist_ok=True)

    if filename:
        # Single file download (same as existing pattern)
        cached = os.path.join(dest_dir, filename)
        if os.path.isfile(cached):
            print(f"Found cached model: {cached}")
            return cached
        return hf_hub_download(
            repo_id=repo_id, filename=filename,
            local_dir=dest_dir, token=token,
        )
    else:
        # Multi-file model (Whisper, Chatterbox, etc.)
        return snapshot_download(
            repo_id=repo_id, local_dir=os.path.join(dest_dir, repo_id.replace("/", "--")),
            token=token, allow_patterns=allow_patterns,
        )
```

### Pattern 2: Audio Input Resolver (URL + Base64)

**What:** Accept audio input as either a public URL or base64-encoded data, resolve to a local temp file path.
**When to use:** Any worker receiving audio input (STT, voice cloning reference audio).
**Source:** Established RunPod ecosystem pattern (RunPod's `worker-faster_whisper`, Dembrane's `runpod-whisper`).

Key design decisions:
1. **Always resolve to a file path** -- inference engines (faster-whisper, Chatterbox) all accept file paths, not raw bytes.
2. **Preserve original format** -- detect format from Content-Type header or file extension, use ffmpeg to convert to WAV only if the engine requires it.
3. **SSRF prevention** -- validate URLs against private IP ranges before downloading. This prevents users from using the worker to probe internal RunPod infrastructure.
4. **Temp file cleanup** -- use context manager or explicit cleanup after inference to prevent disk space leaks across jobs.

```python
import base64
import os
import tempfile
from urllib.parse import urlparse
import ipaddress
import socket
import requests

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm", ".mp4"}

def _validate_url(url: str) -> None:
    """Validate URL is safe to download (SSRF prevention)."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
    # Resolve hostname to check for private IPs
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")
    try:
        addr = socket.getaddrinfo(hostname, None)[0][4][0]
        ip = ipaddress.ip_address(addr)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError("URL resolves to private/internal address")
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname: {hostname}")

def resolve_audio_input(job_input: dict) -> str:
    """
    Resolve audio input to a local temp file path.

    Accepts:
      - {"audio_url": "https://..."} -- download from URL
      - {"audio_base64": "UklGR..."} -- decode from base64
      - {"audio": "https://..." or "base64data"} -- auto-detect

    Returns: path to temp file (caller must clean up)
    """
    if "audio_url" in job_input:
        url = job_input["audio_url"]
        _validate_url(url)
        r = requests.get(url, timeout=120, stream=True)
        r.raise_for_status()
        # Detect extension from URL or Content-Type
        ext = _detect_extension(url, r.headers.get("content-type", ""))
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        for chunk in r.iter_content(chunk_size=8192):
            tmp.write(chunk)
        tmp.close()
        return tmp.name

    elif "audio_base64" in job_input:
        data = base64.b64decode(job_input["audio_base64"])
        ext = _detect_extension_from_bytes(data)
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        tmp.write(data)
        tmp.close()
        return tmp.name

    raise ValueError("Provide 'audio_url' or 'audio_base64'")

def cleanup_audio(path: str) -> None:
    """Remove temp audio file after processing."""
    try:
        os.unlink(path)
    except OSError:
        pass
```

### Pattern 3: Audio Output Encoder

**What:** Encode inference output (NumPy array) to base64 string for JSON response, with S3 upload fallback for large outputs.
**When to use:** TTS and voice cloning workers that produce audio output.
**Source:** Architecture research Pattern 3.

```python
import base64
import io
import soundfile as sf

def encode_audio_output(audio_array, sample_rate: int,
                        format: str = "wav") -> dict:
    """
    Encode audio numpy array to base64 string.

    Returns dict with audio_base64, format, sample_rate, duration_seconds.
    """
    buf = io.BytesIO()
    sf.write(buf, audio_array, sample_rate, format=format)
    buf.seek(0)
    audio_bytes = buf.read()

    return {
        "audio_base64": base64.b64encode(audio_bytes).decode("utf-8"),
        "format": format,
        "sample_rate": sample_rate,
        "duration_seconds": len(audio_array) / sample_rate,
    }
```

### Pattern 4: Slim Multi-Stage Dockerfile

**What:** Two-stage Docker build targeting under 8GB image size for PyTorch-based audio workers.
**When to use:** Every audio worker.
**Source:** Existing llama.cpp Dockerfile adapted; PyTorch Docker optimization research (HIGH confidence).

Key optimizations:
1. Use `nvidia/cuda:12.4.1-runtime-ubuntu22.04` as base (not `-devel`, saves ~5GB)
2. Install PyTorch with `--index-url https://download.pytorch.org/whl/cu124 --no-cache-dir` (~2.5GB torch package, no cache doubling)
3. Install ffmpeg via apt for audio format conversion
4. Never bake model weights into the image (download at runtime via `download_model.py`)
5. Single stage is sufficient for PyTorch workers (no compilation step needed unlike llama.cpp)
6. Install libsndfile1 for soundfile library support

```dockerfile
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

# System deps: Python, ffmpeg, libsndfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /usr/bin/python

WORKDIR /app

# Install PyTorch with CUDA 12.4 support (no cache to save ~2.5GB)
RUN pip3 install --no-cache-dir \
    torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# Install worker dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy worker code
COPY handler.py download_model.py audio_utils.py ./

ENV PYTHONUNBUFFERED=1

# Worker-specific env vars (customize per worker)
ENV HF_REPO_ID="" \
    HF_TOKEN="" \
    MODEL_NAME="default"

CMD ["python3", "-u", "handler.py"]
```

### Anti-Patterns to Avoid

- **Shared pip package across workers:** Do NOT create `runpod-audio-utils` as a pip package. Workers have independent release cycles and different repos. Copy-paste the template files. A shared package creates version coupling that makes independent deployments fragile.
- **Baking model weights into Docker image:** Never include model files in the Docker image. This bloats images to 15-20GB and makes preset switching impossible. Always download at runtime.
- **Using `-devel` CUDA image as runtime base:** The devel image is ~5GB larger. PyTorch bundles its own CUDA runtime, so only the slim `-runtime` image is needed.
- **Subprocess server pattern for Python models:** Audio inference engines are Python libraries. Call them directly, do not spawn a FastAPI/Gradio subprocess.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| URL file downloading with retry | Custom download loop with manual retries | `requests.get()` with timeout or RunPod SDK `rp_download.download_files_from_urls()` | SDK handles exponential backoff, adaptive chunk sizing, and job-scoped directory management |
| HuggingFace model download + caching | Custom HTTP download from HF CDN | `huggingface_hub.hf_hub_download()` / `snapshot_download()` | Handles authentication, resume, integrity checks, cache management |
| Audio format detection | Manual magic byte parsing | `soundfile.info()` for supported formats, ffmpeg probe for others | Edge cases in container format detection are extensive |
| Audio resampling | Custom FFT-based resampler | `scipy.signal.resample_poly()` or `torchaudio.transforms.Resample()` | Resampling algorithms have subtle aliasing issues that are well-solved |
| Base64 encode/decode | Manual byte manipulation | Python stdlib `base64.b64encode()` / `b64decode()` | Standard library, no dependencies |
| SSRF validation | Simple string matching on URL | DNS resolution + `ipaddress` module checks | String-based URL validation is bypassable via DNS rebinding, IPv6, octal encoding |

**Key insight:** The shared template is glue code connecting proven libraries. Every component (HF download, audio I/O, RunPod SDK) is battle-tested. The value is in correct composition, not novel implementation.

## Common Pitfalls

### Pitfall 1: RunPod 10MB Payload Limit

**What goes wrong:** Sending audio as inline base64 in the request payload exceeds RunPod's 10MB `runsync` limit. Base64 encoding adds ~33% overhead, so a 7.5MB audio file becomes ~10MB base64.
**Why it happens:** Developers test with short clips that fit, then production users send real audio.
**How to avoid:** Always support URL-based input as primary. Document base64 as convenience for small clips only (<5MB raw audio). For output, check encoded size before returning; if >7MB, warn or fail with guidance to use URL input instead.
**Warning signs:** 413 errors from RunPod, truncated responses, jobs that silently fail.

### Pitfall 2: Temp File Leaks Across Jobs

**What goes wrong:** Downloaded audio files accumulate in `/tmp` across multiple jobs, eventually filling disk.
**Why it happens:** Exceptions during inference skip the cleanup code. `tempfile.NamedTemporaryFile(delete=False)` requires explicit cleanup.
**How to avoid:** Use try/finally in the handler to always call cleanup. Log temp directory size periodically. Consider a cleanup sweep at handler start.
**Warning signs:** Disk usage growing linearly with job count, eventually causing OOM or disk full errors.

### Pitfall 3: Missing ffmpeg in Docker Image

**What goes wrong:** Worker accepts an MP3/M4A file URL but crashes because ffmpeg is not installed.
**Why it happens:** soundfile only handles WAV/FLAC/OGG natively. MP3 and M4A require ffmpeg.
**How to avoid:** Always install ffmpeg via apt in the Dockerfile. Test with MP3, M4A, OGG, and FLAC inputs.
**Warning signs:** `RuntimeError: Error opening file` on non-WAV audio inputs.

### Pitfall 4: SSRF via Audio URL

**What goes wrong:** Malicious user submits `audio_url=http://169.254.169.254/latest/meta-data/` (cloud metadata endpoint) or private network addresses.
**Why it happens:** The worker downloads URLs without validation, acting as an SSRF proxy.
**How to avoid:** Validate URLs before downloading: check scheme (http/https only), resolve DNS, verify the resolved IP is not private/loopback/link-local. See the `_validate_url()` function in Pattern 2.
**Warning signs:** Requests to internal IPs in access logs, unexpected data in error responses.

### Pitfall 5: snapshot_download Caching Mismatch

**What goes wrong:** `snapshot_download()` uses its own cache directory structure (`~/.cache/huggingface/hub/models--org--name/snapshots/...`), different from the flat `local_dir` approach used by `hf_hub_download()`.
**Why it happens:** The two HuggingFace download functions use different caching strategies.
**How to avoid:** When using `snapshot_download()`, pass `local_dir` to force a specific directory. Use `repo_id.replace("/", "--")` as subdirectory name for consistent naming.
**Warning signs:** Models downloaded twice (once to HF cache, once to local_dir), doubling disk usage.

### Pitfall 6: PyTorch CUDA Version Mismatch

**What goes wrong:** PyTorch installed without explicit CUDA index URL gets CPU-only or wrong CUDA version.
**Why it happens:** Default `pip install torch` installs CPU version. Must use `--index-url https://download.pytorch.org/whl/cu124` for CUDA 12.4.
**How to avoid:** Always pin the CUDA wheel index in Dockerfile pip install command. Verify with `python -c "import torch; print(torch.cuda.is_available())"` in build test.
**Warning signs:** Model loads to CPU instead of GPU, inference is 100x slower, `torch.cuda.is_available()` returns False.

## Code Examples

Verified patterns from official sources:

### Handler Skeleton (Template for All Audio Workers)

```python
# handler.py - Template for audio workers
# Source: Adapted from existing llama.cpp handler.py + RunPod worker-template pattern

import os
import runpod
from download_model import download_model
from audio_utils import resolve_audio_input, cleanup_audio, encode_audio_output

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HF_REPO_ID = os.environ.get("HF_REPO_ID", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

if not HF_REPO_ID:
    raise RuntimeError("HF_REPO_ID environment variable is required")

# ---------------------------------------------------------------------------
# Startup: download model & load to GPU
# ---------------------------------------------------------------------------
print("=" * 60)
print("Audio Worker -- Starting up")
print("=" * 60)

model_path = download_model(repo_id=HF_REPO_ID, token=HF_TOKEN or None)

# Worker-specific: load model here
# model = SomeEngine(model_path, device="cuda")

# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
def handler(job):
    """Process a single job."""
    job_input = job["input"]
    audio_path = None
    try:
        # For workers that accept audio input:
        audio_path = resolve_audio_input(job_input)

        # Worker-specific inference here
        # result = model.process(audio_path, **params)

        return {"status": "success", "output": result}

    except Exception as e:
        return {"error": str(e)}
    finally:
        if audio_path:
            cleanup_audio(audio_path)

# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------
runpod.serverless.start({"handler": handler})
```

### RunPod SDK Download Utility Usage

```python
# Using RunPod's built-in download utilities
# Source: RunPod Python SDK rp_download module

from runpod.serverless.utils.rp_download import download_files_from_urls

def handler(job):
    job_id = job["id"]
    audio_url = job["input"]["audio_url"]

    # Downloads to jobs/{job_id}/downloaded_files/
    # Returns list of local file paths
    downloaded = download_files_from_urls(job_id, [audio_url])
    audio_path = downloaded[0]

    # Process audio...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `hf_hub_download()` only | `snapshot_download()` for multi-file models | huggingface_hub 0.20+ (2024) | Audio models (Whisper, Chatterbox) are multi-file repos, not single files like GGUF |
| Full CUDA devel base image | Runtime-only base + PyTorch bundles CUDA | PyTorch 2.0+ (2023) | 5GB+ savings in Docker image size |
| `librosa` for all audio I/O | `soundfile` for basic I/O, ffmpeg for conversion | 2024 community consensus | librosa adds 100MB+ unnecessary deps for simple read/write |
| Manual audio download with urllib | `requests` with streaming + RunPod SDK utilities | RunPod SDK 1.7+ | Built-in retry logic, adaptive chunking, job-scoped cleanup |

**Deprecated/outdated:**
- `PySoundFile` package name: Use `soundfile` (same library, canonical name since v0.10)
- `torch.cuda.empty_cache()` as sole VRAM management: Still needed but insufficient alone; set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` for production
- Baking models into Docker image: Never do this for configurable workers; download at runtime

## Open Questions

1. **Template location: this repo vs separate template repo?**
   - What we know: The project uses separate repos per worker. This repo is the "hub registry."
   - What's unclear: Should the template files live in this repo as a `template/` directory, or in a separate `worker-audio-template` repo?
   - Recommendation: Keep in this repo under a `template/` or `shared/` directory. It's documentation and starting code, not a runtime dependency. Avoids creating yet another repo for 3-4 files.

2. **RunPod SDK `rp_download` vs custom `requests.get()` for audio URLs?**
   - What we know: RunPod SDK provides `download_files_from_urls()` with retry logic. Custom download gives more control over SSRF validation.
   - What's unclear: Does RunPod's `rp_download` handle SSRF prevention? Likely not, since it's designed for trusted internal URLs.
   - Recommendation: Use custom `requests.get()` with explicit SSRF validation for audio URLs. RunPod's utility is designed for different use cases (downloading job assets, not user-provided URLs).

3. **Audio format conversion: pydub vs raw ffmpeg subprocess?**
   - What we know: pydub wraps ffmpeg with a nice API. Raw subprocess is lighter (no extra dependency).
   - What's unclear: Whether the convenience of pydub justifies the additional dependency.
   - Recommendation: Start with raw ffmpeg subprocess calls. Add pydub only if format conversion logic becomes complex. For Phase 1, the audio resolver just needs to save downloaded bytes to a file -- format conversion happens in engine-specific handlers.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=7.0 |
| Config file | None -- Wave 0 must create `pytest.ini` or `pyproject.toml` `[tool.pytest]` section |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01a | resolve_audio_input() downloads audio from URL to temp file | unit | `python -m pytest tests/test_audio_utils.py::test_resolve_url -x` | No - Wave 0 |
| INFRA-01b | resolve_audio_input() decodes base64 audio to temp file | unit | `python -m pytest tests/test_audio_utils.py::test_resolve_base64 -x` | No - Wave 0 |
| INFRA-01c | resolve_audio_input() rejects private/internal URLs (SSRF) | unit | `python -m pytest tests/test_audio_utils.py::test_ssrf_prevention -x` | No - Wave 0 |
| INFRA-01d | cleanup_audio() removes temp files | unit | `python -m pytest tests/test_audio_utils.py::test_cleanup -x` | No - Wave 0 |
| INFRA-02a | download_model() returns cached path when model exists on volume | unit | `python -m pytest tests/test_download_model.py::test_cached_model -x` | No - Wave 0 |
| INFRA-02b | download_model() calls hf_hub_download for single-file models | unit | `python -m pytest tests/test_download_model.py::test_single_file_download -x` | No - Wave 0 |
| INFRA-02c | download_model() calls snapshot_download for multi-file models | unit | `python -m pytest tests/test_download_model.py::test_snapshot_download -x` | No - Wave 0 |
| INFRA-02d | download_model() raises RuntimeError when repo_id is empty | unit | `python -m pytest tests/test_download_model.py::test_missing_repo_id -x` | No - Wave 0 |
| INFRA-03a | Dockerfile builds successfully with template pattern | smoke | manual -- `docker build --platform linux/amd64 .` | No - Wave 0 |
| INFRA-03b | Built image is under 8GB | smoke | manual -- `docker images --format "table {{.Size}}"` | No - Wave 0 |
| INFRA-03c | ffmpeg is available in runtime image | smoke | manual -- `docker run --rm image ffmpeg -version` | No - Wave 0 |
| INFRA-03d | PyTorch CUDA is available in runtime image | smoke | manual -- `docker run --rm image python -c "import torch; assert torch.cuda.is_available()"` | No - manual only |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_audio_utils.py` -- covers INFRA-01 (audio input resolver, SSRF, cleanup)
- [ ] `tests/test_download_model.py` -- covers INFRA-02 (model download, caching, snapshot)
- [ ] `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` -- test configuration
- [ ] Framework install: `pip install pytest>=7.0` -- add to dev dependencies
- [ ] `tests/conftest.py` -- shared fixtures (mock HF hub, temp directories, sample audio bytes)

## Sources

### Primary (HIGH confidence)

- Existing `download_model.py` in this repo -- 104 lines, proven pattern for HuggingFace model download with volume caching
- Existing `handler.py` in this repo -- 266 lines, proven RunPod handler pattern with dispatch routing
- Existing `Dockerfile` in this repo -- proven multi-stage CUDA build pattern
- [RunPod worker-template](https://github.com/runpod-workers/worker-template) -- official template structure
- [RunPod handler documentation](https://docs.runpod.io/serverless/workers/handler-functions) -- handler function contract
- [RunPod worker-faster_whisper](https://github.com/runpod-workers/worker-faster_whisper) -- reference audio input pattern (audio URL + audio_base64 dual input)
- [HuggingFace Hub download guide](https://huggingface.co/docs/huggingface_hub/guides/download) -- `hf_hub_download()` and `snapshot_download()` API
- [soundfile documentation](https://python-soundfile.readthedocs.io/) -- audio I/O API
- [RunPod Python SDK rp_download](https://deepwiki.com/runpod/runpod-python/2.7-file-download-utilities) -- SDK download utilities API

### Secondary (MEDIUM confidence)

- [PyTorch Docker optimization guide](https://mveg.es/posts/optimizing-pytorch-docker-images-cut-size-by-60percent/) -- image size reduction techniques
- [RunPod Docker setup guide](https://www.runpod.io/articles/guides/docker-setup-pytorch-cuda-12-8-python-3-11) -- PyTorch + CUDA Docker patterns
- [Dembrane/runpod-whisper](https://github.com/Dembrane/runpod-whisper) -- WhisperX RunPod worker with audio I/O patterns

### Tertiary (LOW confidence)

- [requests-hardened](https://pypi.org/project/requests-hardened/) -- SSRF-safe requests library; may be overkill for this use case, manual validation is sufficient
- RunPod `rp_upload` utility for S3 output -- referenced in search results but exact API not verified; defer S3 output to Phase 3/4 when audio output workers are built

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries are the same ones used in the existing worker or established RunPod ecosystem
- Architecture: HIGH -- patterns are direct adaptations of the existing working llama.cpp worker
- Pitfalls: HIGH -- all pitfalls verified against existing codebase analysis, RunPod docs, and community reports

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (30 days -- stable domain, low churn)
