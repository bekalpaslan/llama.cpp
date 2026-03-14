# Codebase Structure

**Analysis Date:** 2026-03-14

## Directory Layout

```
runpod/
├── handler.py              # Main serverless handler (startup + request routing)
├── download_model.py       # HuggingFace model fetching with auto-detection
├── requirements.txt        # Python dependencies (runpod, huggingface-hub, requests)
├── Dockerfile              # Two-stage build (llama.cpp + Python runtime)
├── CLAUDE.md               # Project documentation for Claude Code
├── README.md               # User-facing documentation
├── .runpod/
│   ├── hub.json            # RunPod Hub preset definitions (36 models)
│   └── tests.json          # RunPod Hub test suite definitions
├── .env                    # Local development environment config
└── .dockerignore           # Files excluded from Docker image
```

## Directory Purposes

**Repository Root:**
- Purpose: Application source and configuration for RunPod serverless worker
- Contains: Python handler scripts, Docker configuration, model presets
- Key files: `handler.py` (main), `download_model.py` (model management), `Dockerfile` (build), `.runpod/hub.json` (presets)

**.runpod/:**
- Purpose: RunPod Hub integration and configuration
- Contains: Preset definitions for one-click deployment, test specifications
- Generated: No
- Committed: Yes

## Key File Locations

**Entry Points:**
- `handler.py` (module-level startup + serverless handler dispatch): Startup happens at container initialization; serverless requests dispatched via `dispatch()` function
- `Dockerfile`: Build and launch configuration for container

**Configuration:**
- `.runpod/hub.json`: Preset definitions for 36 models with environment variables
- `.env`: Local development configuration (HF_REPO_ID, etc.)
- `Dockerfile` (lines 55-66): Default environment variables

**Core Logic:**
- `handler.py` (lines 19-100): Startup flow (download model, launch llama-server, health polling)
- `handler.py` (lines 106-192): Sync request handler (input routing, HTTP proxying)
- `handler.py` (lines 198-252): Streaming request handler (SSE chunk yielding)
- `download_model.py` (lines 29-58): Quantization auto-detection (`find_gguf_file()`)
- `download_model.py` (lines 61-104): Model download with caching (`download_model()`)

**Testing:**
- `.runpod/tests.json`: Test suite definitions (used by RunPod Hub)

## Naming Conventions

**Files:**
- Python modules: lowercase with underscores (`handler.py`, `download_model.py`)
- Configuration: JSON format (`.runpod/hub.json`, `.runpod/tests.json`)
- Environment: `.env` and `.env*` files

**Directories:**
- Hidden/configuration: Dot prefix (`.runpod/`, `.env`, `.dockerignore`)

**Functions:**
- Lowercase with underscores: `download_model()`, `find_gguf_file()`, `stream_handler()`, `dispatch()`

**Variables:**
- Environment variables: UPPERCASE with underscores (`HF_REPO_ID`, `HF_FILENAME`, `CTX_SIZE`, `N_GPU_LAYERS`)
- Module-level config: UPPERCASE (`SERVER_PORT`, `BASE_URL`, `STARTUP_TIMEOUT`)
- Local variables: lowercase with underscores (`model_path`, `payload`, `cached`)

**Constants:**
- Quantization preferences: Uppercase with underscores in list (`QUANT_PREFERENCE` in `download_model.py`)
- Cache paths: Uppercase (`VOLUME_PATH`, `LOCAL_PATH`)

## Where to Add New Code

**New Feature (Example: Add a new API endpoint):**
- Primary code: Modify `handler.py` request handler sections (lines 119-192 for sync, 204-225 for streaming)
- Configuration: Add env var schema to `.runpod/hub.json` if needed
- Testing: Add test case to `.runpod/tests.json`

**New Utility Function (Example: Custom model selection logic):**
- Implementation: Add function to `download_model.py` (alongside `find_gguf_file()`)
- Import: Add import to `handler.py` (line 17: `from download_model import ...`)

**New Model Preset:**
- Location: `.runpod/hub.json`, `presets` array (lines 83+)
- Structure: Add object with `name`, `description`, `env`, `gpu`, `volume_size` fields
- Example: See lines 84-94 (Qwen 3.5 35B-A3B preset)

**Startup Behavior Change (Example: Add model validation):**
- Location: `handler.py` module-level startup section (lines 19-100)
- Pattern: Add logic after line 52 (after `download_model()` call) and before line 54 (before `cmd` construction)

## Special Directories

**Docker Build Context:**
- Files included: `handler.py`, `download_model.py`, `requirements.txt`, `Dockerfile`
- Files excluded: Everything in `.dockerignore` (typically git/CI artifacts)

**.runpod/ (Hub Integration):**
- Purpose: RunPod Hub metadata and configurations
- Generated: No (maintained manually)
- Committed: Yes (required for one-click deployment)
- Key usage: `hub.json` defines preset buttons shown in RunPod Hub UI

## File Responsibilities

**handler.py:**
- Startup (lines 19-100):
  - Load env vars
  - Download model via `download_model()`
  - Build and launch llama-server subprocess
  - Poll health and verify readiness
  - Register serverless handler
- Sync Request Handler (lines 106-192):
  - Parse job input
  - Route based on input format (OpenAI passthrough, chat, prompt)
  - Proxy HTTP to llama-server
  - Return parsed JSON response
- Streaming Handler (lines 198-252):
  - Parse job input
  - Proxy streaming HTTP with `stream=True`
  - Parse Server-Sent Events format
  - Yield JSON chunks
  - Exit on `[DONE]` sentinel
- Dispatch (lines 257-266):
  - Route to sync or streaming handler based on `stream` flag
  - Register with RunPod serverless runtime

**download_model.py:**
- Auto-detection (lines 29-58):
  - List files in HuggingFace repo
  - Filter for .gguf files
  - Prefer single files over shards
  - Prioritize Q4_K_M quantization
  - Fall back to other quantizations in preference order
- Download & Caching (lines 61-104):
  - Check `/runpod-volume/models` (persistent network volume)
  - Check `/tmp/models` (ephemeral)
  - Download to appropriate location if not cached
  - Return path to model file

**Dockerfile:**
- Stage 1 - Builder (lines 1-24):
  - Use nvidia/cuda devel image
  - Clone llama.cpp repo
  - Compile with CUDA for architectures 75/80/86/89/90 (T4 through H100)
  - Build only `llama-server` binary with static linking
- Stage 2 - Runtime (lines 27-68):
  - Use nvidia/cuda runtime image (smaller)
  - Copy cuBLAS libraries from builder
  - Install Python 3
  - Copy handler scripts
  - Set default environment variables
  - CMD executes handler.py

**.runpod/hub.json:**
- Structure: Top-level object with `title`, `description`, `category`, `env`, `presets`
- `env` array: Defines all configurable environment variables (input schema)
- `presets` array: 36 model configurations with repo, filename, context size, GPU requirements

**requirements.txt:**
- Dependencies:
  - `runpod>=1.7.0`: RunPod serverless SDK
  - `huggingface-hub>=0.25.0`: HuggingFace model fetching
  - `requests>=2.31.0`: HTTP client for llama-server proxying

**README.md:**
- User documentation: Features, quick start, input formats, environment variables, model presets

**CLAUDE.md:**
- Developer documentation: Architecture explanation, build/deploy commands, design decisions, preset addition guide

## Code Organization Patterns

**Configuration Pattern:**
- All tuneable values are environment variables (no hardcoded settings)
- Defaults provided in code (lines 22-36 in handler.py)
- Override via Docker ENV or RunPod preset env

**Proxy Pattern:**
- Handler receives RunPod job → parses input → builds llama-server payload → proxies HTTP → returns response
- Three input formats normalized to single llama-server API

**Streaming Pattern:**
- Generator function yields chunks (not list of all chunks)
- Server-Sent Events format: "data: {json}\n\n"
- [DONE] sentinel signals completion

**Subprocess Management Pattern:**
- Launch subprocess at module-level startup (once per container)
- Keep reference for health checks only
- No restart logic; if process exits, container exits

**Caching Pattern:**
- Check persistent volume first (survives cold starts)
- Fall back to ephemeral temp storage
- Create directories if needed with `os.makedirs(..., exist_ok=True)`

---

*Structure analysis: 2026-03-14*
