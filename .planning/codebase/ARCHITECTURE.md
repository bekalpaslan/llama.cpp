# Architecture

**Analysis Date:** 2026-03-14

## Pattern Overview

**Overall:** Serverless proxy architecture with external process delegation

**Key Characteristics:**
- Single responsibility: proxy HTTP requests from RunPod serverless API to a subprocess llama-server
- Configuration-driven model selection via environment variables
- Two-stage Docker build: compile llama.cpp with CUDA, then package with Python handler
- Module-level startup (runs once at container initialization) for model download and server launch
- Request-level handler dispatch for both sync and streaming workloads

## Layers

**Entry Point / Serverless Interface:**
- Purpose: Accept job payloads from RunPod serverless API and dispatch to appropriate handler
- Location: `handler.py` (lines 257-266)
- Contains: `dispatch()` function that routes based on `stream` flag
- Depends on: `runpod.serverless` SDK, request handlers
- Used by: RunPod runtime (called automatically via `runpod.serverless.start()`)

**Initialization/Startup Layer:**
- Purpose: Download model from HuggingFace and launch llama-server subprocess
- Location: `handler.py` (module-level, lines 19-100)
- Contains: Configuration loading, model download, server health polling
- Depends on: `download_model()` function, `requests` library for health checks
- Used by: Python runtime (executes on container startup before handler registration)
- Key flow:
  1. Load env vars for model repo, filename, and llama-server configuration
  2. Call `download_model()` to fetch GGUF from HuggingFace or cache
  3. Build llama-server command with GPU and performance parameters
  4. Poll `/health` endpoint until server reports `{"status": "ok"}`
  5. Register `dispatch()` handler with RunPod serverless runtime

**Model Download Layer:**
- Purpose: Fetch GGUF models from HuggingFace with smart caching and quantization auto-detection
- Location: `download_model.py`
- Contains: Two functions: `find_gguf_file()` (auto-detect best quantization), `download_model()` (manage cache)
- Depends on: `huggingface_hub` SDK
- Used by: Startup layer during container initialization

**Request Handler Layer:**
- Purpose: Translate RunPod job inputs into llama-server HTTP requests and proxy responses
- Location: `handler.py` (lines 106-192, 198-252)
- Contains: Three handlers—sync `handler()`, streaming `stream_handler()`, and dispatch function
- Depends on: `requests` library for HTTP proxying, response parsing
- Used by: Serverless entry point via `dispatch()`

## Data Flow

**Startup Flow:**
1. Container starts, Python interpreter executes `handler.py`
2. Module-level code (lines 19-100) runs first:
   - Environment variables are read (HF_REPO_ID, CTX_SIZE, N_GPU_LAYERS, etc.)
   - `download_model()` is called to fetch GGUF from HuggingFace
   - llama-server subprocess is spawned with full command line args
   - Loop polls `/health` endpoint until server is ready
3. Once server is healthy, `runpod.serverless.start()` is called to register `dispatch()` handler
4. Container enters RunPod serverless runtime and waits for jobs

**Request Flow (Sync):**
1. RunPod delivers job to `dispatch(job)` with `stream=False`
2. `dispatch()` calls `handler(job)`
3. `handler()` inspects `job["input"]` to determine input format:
   - **OpenAI passthrough:** Uses exact route and payload from input
   - **Chat messages:** Maps `{"messages": [...]}` to `/v1/chat/completions` payload
   - **Simple prompt:** Maps `{"prompt": "..."}` to `/completion` payload
4. Optional parameters are passed through (temperature, top_p, top_k, etc.)
5. HTTP POST is made to `http://127.0.0.1:8080{route}` with `stream=False`
6. Response is parsed as JSON and returned to RunPod
7. RunPod delivers response to job caller

**Request Flow (Streaming):**
1. RunPod delivers job to `dispatch(job)` with `stream=True`
2. `dispatch()` calls `stream_handler(job)` which returns a generator
3. Same input format determination as sync, but payload includes `stream=True`
4. HTTP POST is made with `stream=True` to enable Server-Sent Events
5. Response iterator loops over lines, skipping empty lines and parsing JSON chunks
6. Each parsed chunk is yielded to RunPod's streaming infrastructure
7. When `[DONE]` sentinel is received, generator exits
8. RunPod aggregates chunks and delivers stream to job caller

**State Management:**
- Model state: Persistent llama-server process (singleton per container)
- Request state: No cross-request state; each job is independent
- Cache state: Model files persisted in `/runpod-volume/models` (network volume) or `/tmp/models` (ephemeral)

## Key Abstractions

**Model Selection:**
- Purpose: Enable one Docker image to serve any GGUF model via configuration
- Files: `download_model.py` (lines 29-58), `handler.py` (lines 22-25)
- Pattern: Environment variable configuration (`HF_REPO_ID`, `HF_FILENAME`, `CTX_SIZE`) mapped to llama-server args; auto-detection of quantization if filename not provided

**Input Format Abstraction:**
- Purpose: Normalize three different input formats (chat, prompt, OpenAI passthrough) into llama-server payloads
- Files: `handler.py` (lines 119-191)
- Pattern: Conditional branching based on keys in `job["input"]` dictionary; each format maps to a different llama-server endpoint

**Streaming Abstraction:**
- Purpose: Handle both sync and async request patterns via single request handler
- Files: `handler.py` (lines 257-260)
- Pattern: `dispatch()` function acts as router; checks `stream` flag to select `handler()` or `stream_handler()`

## Entry Points

**Container Startup:**
- Location: `handler.py` (module-level, lines 19-100)
- Triggers: Docker CMD executes `python3 -u handler.py` (from Dockerfile line 68)
- Responsibilities:
  - Load configuration from environment
  - Download model from HuggingFace
  - Launch llama-server subprocess
  - Health check and wait for server readiness
  - Register serverless handler

**Serverless Request Handler:**
- Location: `handler.py`, `dispatch()` function (lines 257-260)
- Triggers: RunPod serverless runtime invokes handler when job arrives
- Responsibilities: Route request to sync or streaming handler based on input

**Sync Handler:**
- Location: `handler.py`, `handler()` function (lines 106-192)
- Triggers: Called by `dispatch()` when `stream=False`
- Responsibilities: Proxy single HTTP request to llama-server and return response

**Streaming Handler:**
- Location: `handler.py`, `stream_handler()` function (lines 198-252)
- Triggers: Called by `dispatch()` when `stream=True`
- Responsibilities: Proxy streaming HTTP request and yield SSE chunks

## Error Handling

**Strategy:** Fail-fast with error responses, no retry logic

**Patterns:**
- **Startup errors:** RuntimeError raised immediately (e.g., missing HF_REPO_ID, model download failure, server health timeout)
- **Request errors:** HTTP errors and exceptions caught and returned as `{"error": str(e)}` in response (lines 135-136, 163-164, 190-191, 251)
- **Connection errors:** Requests library ConnectionError is caught during health polling; loop continues until timeout (lines 94-95)
- **JSON parsing:** JSONDecodeError in stream handler is caught and skipped (lines 248-249)

## Cross-Cutting Concerns

**Logging:**
- Approach: `print()` statements to stdout; RunPod captures and logs container output
- Locations: Startup phase logs model download, llama-server launch, health check progression (lines 41-43, 48-52, 73, 81-82, 92-93, 102-103)

**Configuration:**
- Approach: All tuneable parameters are environment variables with sensible defaults
- Critical vars: `HF_REPO_ID` (required), `CTX_SIZE`, `N_GPU_LAYERS`, `N_PARALLEL`
- Optional vars: `HF_FILENAME` (auto-detected), `HF_TOKEN`, `MODEL_NAME`, `FLASH_ATTN`, `KV_CACHE_TYPE`, `EXTRA_ARGS`, `STARTUP_TIMEOUT`

**Performance Tuning:**
- GPU offloading: `N_GPU_LAYERS` (default 99 = all layers)
- Context window: `CTX_SIZE` (adjusted per model to fit VRAM)
- Parallelism: `N_PARALLEL` (concurrent inference slots)
- KV cache quantization: `KV_CACHE_TYPE` (f16 default, can reduce to q4_0 for memory savings)
- Flash attention: `FLASH_ATTN` (on/off/auto; defaults to on)

**Caching:**
- Model files: Checked in `/runpod-volume/models` first (persistent network volume), falls back to `/tmp/models` (ephemeral)
- Quantization preference: Auto-detection tries Q4_K_M first, then falls back to other quantizations in order (lines 17-26)

---

*Architecture analysis: 2026-03-14*
