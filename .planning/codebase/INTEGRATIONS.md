# External Integrations

**Analysis Date:** 2026-03-14

## APIs & External Services

**HuggingFace Hub:**
- Model file hosting and repository browsing
  - SDK/Client: `huggingface-hub>=0.25.0`
  - Auth: Environment variable `HF_TOKEN` (optional for gated models)
  - Functions: `hf_hub_download()` for model download, `list_repo_files()` for auto-detection
  - Location: `download_model.py`

**llama.cpp Server (Local):**
- In-process inference via HTTP
  - Runs on `localhost:8080`
  - OpenAI-compatible REST endpoints:
    - `POST /v1/chat/completions` - Chat message completion (from `handler.py` line 157)
    - `POST /v1/completions` or `POST /completion` - Raw prompt completion (from `handler.py` line 183)
    - `GET /health` - Server health check (from `handler.py` line 88)
  - Metrics endpoint: `--metrics` flag passed to llama-server (Dockerfile line 67)

**RunPod Serverless API:**
- Job queue and request routing
  - SDK: `runpod>=1.7.0`
  - Handler registration: `runpod.serverless.start()` (from `handler.py` line 263-266)
  - Dispatch function: `dispatch()` routes to sync `handler()` or streaming `stream_handler()` based on `job["input"]["stream"]` flag
  - Streaming: Returns generator for SSE streaming via `/stream/{job_id}` endpoint

## Data Storage

**Model Cache Locations:**
- Primary: `/runpod-volume/models/` (persistent network volume, survives cold starts)
- Fallback: `/tmp/models/` (ephemeral, cleared on container restart)
- Auto-detection: `download_model.py` checks primary first (line 78)

**Model Files:**
- Format: GGUF (Quantized Large Language Model Format)
- Download source: HuggingFace repositories (specified by `HF_REPO_ID`)
- Quantization preference order: Q4_K_M > Q4_K_S > Q5_K_M > Q5_K_S > Q3_K_M > Q6_K > Q8_0 > Q4_0 (from `download_model.py` lines 17-26)

**No Database:** Application is stateless. No persistent database required. Model is the only stateful component.

## File Storage

- HuggingFace Hub - Remote model repository
- RunPod Network Volume - Local persistent cache for models across container restarts
- Local ephemeral storage `/tmp/models/` - Fallback if network volume not available

## Caching

- **Model caching:** Built into `download_model.py` (lines 78-83)
  - Checks local paths before downloading
  - Returns cached model path if file exists
  - Reports cache hit with size in GB

- **Key-value cache quantization:** Configurable via `KV_CACHE_TYPE` environment variable
  - Supported types: `f16` (default), `f32`, `q8_0`, `q4_0`, `q4_1`
  - Passed to llama-server as `-ctk` and `-ctv` flags (from `handler.py` lines 63-64)

## Authentication & Identity

**Auth Provider:**
- HuggingFace token-based authentication
- Implementation: `HF_TOKEN` environment variable
- Usage: Optional for accessing gated model repositories
- Location: Passed to `hf_hub_download()` in `download_model.py` line 95-100

**No user authentication:** RunPod Serverless endpoint authentication is handled by RunPod platform itself. Worker is stateless and does not manage user identity.

## Monitoring & Observability

**Error Tracking:**
- No external error tracking service
- Errors logged to stdout/stderr in container

**Logs:**
- Container stdout/stderr (from Python print statements and llama-server subprocess output)
- llama-server metrics available via `--metrics` flag
- Handler errors returned as JSON: `{"error": str(e)}` (from `handler.py` lines 136, 164, 190)

**Health Checks:**
- llama-server health endpoint: `GET /health` (polled during startup)
- Startup validation: 600-second timeout (configurable via `STARTUP_TIMEOUT`) to ensure server ready before processing jobs

## CI/CD & Deployment

**Hosting:**
- RunPod Serverless (docker container-based)
- Container registry: Docker Hub (`alpaslanbek/llamacpp-worker`)
- Alternative registry: RunPod Hub (`.runpod/hub.json` presets for one-click deploy)

**Build & Push:**
```bash
docker build --platform linux/amd64 -t alpaslanbek/llamacpp-worker:latest .
docker push alpaslanbek/llamacpp-worker:latest
```
(From CLAUDE.md)

**CI Pipeline:**
- Not detected (no GitHub Actions, GitLab CI, or similar)
- Manual build and push process

**Deployment:**
- One-click via `.runpod/hub.json` presets (36 model configurations)
- Manual via RunPod console with custom `HF_REPO_ID` and `HF_FILENAME`

## Environment Configuration

**Required env vars:**
- `HF_REPO_ID` - HuggingFace repository containing GGUF model (e.g., `bartowski/Qwen_Qwen3.5-9B-GGUF`)

**Optional env vars:**
- `HF_FILENAME` - Specific GGUF file (auto-detects best if empty)
- `HF_TOKEN` - Auth for gated models
- `MODEL_NAME` - Display name in `/v1/models` (default: `default`)
- `N_GPU_LAYERS` - GPU layer offload (default: `99`, meaning all)
- `CTX_SIZE` - Context window in tokens (default: `4096`)
- `N_PARALLEL` - Concurrent inference slots (default: `1`)
- `FLASH_ATTN` - Flash attention mode (default: `on`, options: `on/off/auto`)
- `KV_CACHE_TYPE` - KV cache quantization (default: `f16`)
- `EXTRA_ARGS` - Additional llama-server CLI flags (space-separated)
- `STARTUP_TIMEOUT` - Server startup wait time in seconds (default: `600`)

**Secrets location:**
- RunPod console environment variables (configured when creating endpoint)
- `.runpod/hub.json` stores preset configurations (public, non-sensitive)

## Webhooks & Callbacks

**Incoming:**
- None detected

**Outgoing:**
- None detected

**Job Polling:**
- RunPod Serverless polling via `/stream/{job_id}` for streaming responses (built into RunPod SDK)

---

*Integration audit: 2026-03-14*
