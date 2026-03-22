# Coding Conventions

**Analysis Date:** 2026-03-14

## Naming Patterns

**Files:**
- Module files use snake_case: `handler.py`, `download_model.py`
- Files contain single responsibility domains (model downloading separate from request handling)

**Functions:**
- snake_case for all function names: `find_gguf_file()`, `download_model()`, `stream_handler()`
- Private/internal functions not explicitly marked (no leading underscore convention observed)
- Handler functions use explicit names: `handler()`, `stream_handler()`, `dispatch()`

**Variables:**
- snake_case for local and module variables
- Environment variable references use UPPER_SNAKE_CASE: `HF_REPO_ID`, `HF_TOKEN`, `MODEL_NAME`, `CTX_SIZE`, etc.
- Configuration constants at module level in UPPER_SNAKE_CASE: `VOLUME_PATH`, `LOCAL_PATH`, `QUANT_PREFERENCE`, `SERVER_PORT`, `BASE_URL`, `STARTUP_TIMEOUT`
- Loop counters and temporary variables: `i`, `r` (for requests), `f` (for files)

**Types:**
- Python type hints used with union syntax: `str | None` (Python 3.10+)
- Type hints on function signatures: `def find_gguf_file(repo_id: str, preferred_quant: str = "Q4_K_M", token: str | None = None) -> str | None:`
- Dictionary access keys use double quotes: `job["input"]`, `r.json()`, `health.get("status")`

## Code Style

**Formatting:**
- No explicit formatter config (no `.flake8`, `.pylintrc`, or `pyproject.toml` found)
- Follows PEP 8 implicitly with:
  - 4-space indentation
  - Line length appears ~80-100 characters (longer for command arrays and payloads)
  - Blank lines between logical sections

**Linting:**
- No linting tools configured (no eslint, pylint, or flake8 config files)
- Code passes implicit Python 3.10+ requirements (uses `|` union syntax)

## Import Organization

**Order:**
1. Standard library imports: `json`, `os`, `subprocess`, `sys`, `time`
2. Third-party imports: `requests`, `runpod`, `huggingface_hub`
3. Local imports: `from download_model import download_model`

**Path Aliases:**
- No path aliases or absolute imports used; project is small (2 files)
- Relative imports only at root level

## Error Handling

**Patterns:**
- Use `raise RuntimeError()` for startup-critical errors: `raise RuntimeError("HF_REPO_ID environment variable is required")`, `raise RuntimeError("llama-server exited with code...")`
- Catch specific exceptions where possible: `except requests.RequestException as e:`, `except requests.ConnectionError:`, `except json.JSONDecodeError:`
- Return error responses in handlers instead of raising: `return {"error": str(e)}`
- Yield error responses in generators: `yield {"error": "..."}`
- Use `except Exception as e:` for broad fallback in `find_gguf_file()` when listing HuggingFace repo files fails
- Print warnings to stdout for non-fatal issues: `print(f"Warning: could not list files in {repo_id}: {e}")`
- Exit with `sys.exit(1)` for unrecoverable errors: when no GGUF files found in repo

**Startup validation:**
- Check required env vars at module load time before subprocess launch
- Poll with timeout loop to verify external service health before proceeding
- Exit entire process if startup fails; don't defer error to first request

## Logging

**Framework:** Standard `print()` statements

**Patterns:**
- Use `print()` for informational messages
- Print separator lines for major milestones: `print("=" * 60)`
- Include context in status messages: `print(f"llama-server ready after {i + 1}s")`
- Print error details with stderr output flag for critical issues: `print(f"ERROR: ...", file=sys.stderr)`
- Use print for diagnostics during startup flow (no logging framework)
- No debug or trace-level logging; everything at info/error level

**Output:**
- Startup diagnostics go to stdout (captured by container logs)
- Error messages go to stderr where appropriate
- Return error dicts in responses rather than logging in handlers

## Comments

**When to Comment:**
- Module-level docstrings explain purpose and high-level behavior: `"""RunPod Serverless Handler for llama.cpp GGUF models..."""`
- Section markers with equals signs divide logical blocks: `# ---------------------------------------------------------------------------`
- Inline comments explain non-obvious logic or alternatives: `# Prefer single-file models (skip split shards like *-00001-of-00003.gguf)`
- Comments explain why choices were made over what code does: `# Fall back to first available`

**Docstrings:**
- Google/NumPy style multi-line docstrings on public functions
- Include parameter descriptions and return type:
```python
def find_gguf_file(repo_id: str, preferred_quant: str = "Q4_K_M",
                   token: str | None = None) -> str | None:
    """Find the best GGUF file in a HuggingFace repo."""
```
- Handler docstrings list all accepted input formats with examples
- One-liner docstrings for simple utilities like `download_model()`

## Function Design

**Size:** Functions range 6-30 lines; handlers are longer due to multiple format branches

**Parameters:**
- Use keyword arguments for optional parameters: `find_gguf_file(repo_id, preferred_quant="Q4_K_M", token=None)`
- Accept dicts as job input rather than many parameters: `job["input"]` unpacking
- Pass environment through module-level constants rather than parameter threading

**Return Values:**
- Return early on errors before processing: `if not filename: ... sys.exit(1)`
- Return full response dicts from handlers (not status codes): `{"error": str(e)}`, `return r.json()`
- Generator handlers yield individual chunks: `yield json.loads(data)` in streaming
- Functions return None on failure in some cases: `find_gguf_file()` returns None if files not listed
- Use tuple unpacking for configuration loading is not used; use direct access

## Module Design

**Exports:**
- `handler.py`: Exports `dispatch()` as main entry point (called by `runpod.serverless.start()`)
  - Module-level code runs at import time (downloads model, starts server)
  - Handler functions are internal but referenced by `dispatch()`
- `download_model.py`: Exports `download_model()` as main function
  - Helper `find_gguf_file()` is internal but not marked private
  - Constants `VOLUME_PATH`, `LOCAL_PATH`, `QUANT_PREFERENCE` are module-level

**Initialization:**
- Startup logic at module level in `handler.py` (runs on import)
- No separate initialization functions; configuration via environment variables only
- Model download and server start are coupled—both happen at import time

**Error boundaries:**
- Startup errors (missing env vars, server won't start) abort immediately via `raise RuntimeError()` or `sys.exit(1)`
- Request errors caught in try-except and returned as response dicts
- Streaming errors yielded rather than logged

---

*Convention analysis: 2026-03-14*
