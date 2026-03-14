# Technology Stack

**Analysis Date:** 2026-03-14

## Languages

**Primary:**
- Python 3 - Main handler logic and model download orchestration (`handler.py`, `download_model.py`)
- C/C++ - llama.cpp inference engine compiled with CUDA support (linked from builder stage)

**Build:**
- Bash - Docker build scripts and entrypoint

## Runtime

**Environment:**
- Docker container-based (RunPod Serverless)
- Base image: `nvidia/cuda:12.4.1-runtime-ubuntu22.04`
- Builder image: `nvidia/cuda:12.4.1-devel-ubuntu22.04`
- Python 3 runtime available in runtime image

**Package Manager:**
- pip3 - Python dependency management
- Lockfile: `requirements.txt` (pinned versions)

## Frameworks

**Core:**
- llama.cpp - GGUF model inference engine with OpenAI-compatible API server
  - Version: Pinnable via `LLAMA_CPP_VERSION` build arg (defaults to `master`)
  - Binary: `llama-server` compiled with CUDA support
  - Location: `/usr/local/bin/llama-server`

**Serverless:**
- RunPod Serverless SDK - Job queue integration and request handling
  - Package: `runpod>=1.7.0`
  - Entry point: `handler.py`, line 263-266

**HTTP Client:**
- requests - HTTP library for proxying to llama-server
  - Package: `requests>=2.31.0`
  - Used for all communication with localhost:8080 llama-server API

## Key Dependencies

**Critical:**
- `runpod>=1.7.0` - RunPod Serverless handler registration and job dispatch
  - Why it matters: Enables async job processing on RunPod infrastructure
  - Location: `handler.py` imports and `runpod.serverless.start()`

- `huggingface-hub>=0.25.0` - Model file download and repository browsing
  - Why it matters: Downloads GGUF models from HuggingFace and auto-detects best quantization
  - Location: `download_model.py`, functions `hf_hub_download()` and `list_repo_files()`

- `requests>=2.31.0` - HTTP client for llama-server proxy
  - Why it matters: All LLM API communication routes through this
  - Location: `handler.py`, all POST/GET requests to `http://127.0.0.1:8080`

**Infrastructure:**
- CUDA runtime libraries (copied from builder)
  - `libcublas.so*` and `libcublasLt.so*` - GPU acceleration
  - Location: `/usr/local/cuda/lib64/` in runtime image

## Configuration

**Environment:**
- Environment variables only (no config files)
- Critical required: `HF_REPO_ID` (HuggingFace repository ID)
- Optional tuning: `HF_FILENAME`, `HF_TOKEN`, `MODEL_NAME`, `N_GPU_LAYERS`, `CTX_SIZE`, `N_PARALLEL`, `FLASH_ATTN`, `KV_CACHE_TYPE`, `EXTRA_ARGS`, `STARTUP_TIMEOUT`
- All variables defined in Dockerfile with defaults and in `.runpod/hub.json` for presets

**Build:**
- `Dockerfile` - Two-stage multi-architecture build (llama.cpp compilation + Python runtime)
- `.dockerignore` - Excludes unnecessary files from build context

## Platform Requirements

**Development:**
- Docker Desktop with buildx (for multi-arch builds: `--platform linux/amd64`)
- CUDA 12.4 compatible GPU (for local testing with `python handler.py --rp_serve_api`)
- Python 3.9+ with pip

**Production:**
- RunPod Serverless Endpoint configured with:
  - Container image: `alpaslanbek/llamacpp-worker:latest` (published to Docker Hub)
  - NVIDIA GPU: T4, A100, RTX 3090, A6000, A40, RTX 4090, L4, L40, H100 (CUDA SM 75/80/86/89/90)
  - RAM: Variable by model size (cached in `/runpod-volume/models` network volume)
  - Storage: Model size + overhead (preset volume_size recommendations in `.runpod/hub.json`)

## CUDA Architecture Support

Compiled with support for GPU compute capabilities:
- `75` - T4, RTX 2060/2070/2080
- `80` - A100, A30
- `86` - RTX 3090, A6000, A40, L40
- `89` - RTX 4090, L4, L40S
- `90` - H100, H200

Configuration: `Dockerfile` line 22, CMake flag `-DCMAKE_CUDA_ARCHITECTURES="75;80;86;89;90"`

## Inference Server Details

**llama-server Configuration:**
- Runs on `localhost:8080` (defined in `handler.py` line 34-35)
- Exposes OpenAI-compatible REST API: `/v1/chat/completions`, `/v1/completions`, `/health`
- Built with `BUILD_SHARED_LIBS=OFF` (static linking, only cuBLAS runtime required)
- Launched as subprocess via `subprocess.Popen()` in `handler.py` lines 74-78

---

*Stack analysis: 2026-03-14*
