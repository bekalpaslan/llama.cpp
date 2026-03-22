# Testing Patterns

**Analysis Date:** 2026-03-14

## Test Framework

**Runner:**
- No automated test framework configured (pytest, unittest, etc.)
- Manual testing via RunPod Console or local invocation

**Testing Infrastructure:**
- `.runpod/tests.json` provides RunPod Hub integration test specifications
- Tests are defined declaratively as JSON, not programmatic test code
- RunPod Hub runner executes these tests when deployment is initiated

**Run Commands:**
```bash
# Local testing with RunPod's dev server
export HF_REPO_ID="bartowski/Qwen_Qwen3.5-9B-GGUF"
python handler.py --rp_serve_api

# Via RunPod Hub (automatic execution on deployment)
# Tests defined in .runpod/tests.json are executed by the platform
```

## Test File Organization

**Location:**
- Tests defined in `.runpod/tests.json` (platform-agnostic JSON format)
- No co-located test files (e.g., `handler_test.py`, `test_handler.py`)
- No separate `tests/` directory

**Naming:**
- Test cases use descriptive names in `.runpod/tests.json`: `"Chat completion - basic"`, `"OpenAI passthrough - models"`

**Structure:**
```
.runpod/
└── tests.json          # RunPod test specifications
```

## Test Structure

**Suite Organization:**
```json
{
  "tests": [
    {
      "name": "Chat completion - basic",
      "input": {
        "messages": [...],
        "max_tokens": 32,
        "temperature": 0.1
      },
      "expected_status": 200,
      "timeout": 60
    }
  ]
}
```

**Test Case Components:**
- `name`: Human-readable test description
- `input`: The job input payload sent to the handler
- `expected_status`: HTTP status code expected (200 for success)
- `timeout`: Timeout in seconds before test fails

**Patterns:**
- Each test is independent; no setup/teardown fixtures
- Tests validate success path primarily (no negative test cases observed)
- Tests use representative but minimal inputs (e.g., 32 tokens max to keep runtime short)

## Test Coverage

**Current test scenarios (from `.runpod/tests.json`):**

**Chat Completions:**
- Basic: Simple user message without system prompt
- With System Prompt: Verify system role integration
- Both use low temperature (0.1, 0.0) to reduce variance

**Simple Prompt:**
- Direct text-in/text-out completion format
- Validates `/completion` endpoint

**OpenAI Passthrough:**
- Chat endpoint: Verify `/v1/chat/completions` proxy works
- Models endpoint: Verify `/v1/models` list endpoint

**Test Execution:**
```bash
# RunPod Hub automatically runs all tests in .runpod/tests.json
# when deployment occurs. Individual tests timeout after specified
# duration (e.g., 60 seconds for chat, 10 seconds for models list).
```

## Input Validation Patterns

**Handler Validation:**
- Check for presence of required keys: `if "openai_route" in job_input:`, `if messages:`, `if prompt:`
- No explicit schema validation; rely on JSON structure checks
- Return error dict if no recognized format found: `return {"error": "Provide 'messages', 'prompt', or 'openai_route' + 'openai_input'"}`

**Environment Validation:**
- Required env var checked at startup: `if not HF_REPO_ID: raise RuntimeError(...)`
- Optional env vars have defaults: `N_GPU_LAYERS = int(os.environ.get("N_GPU_LAYERS", "99"))`
- Type conversions happen at module load time: `int()`, `str`

## Error Scenarios

**Startup Errors:**
- Missing `HF_REPO_ID`: Raise `RuntimeError` immediately
- llama-server exits prematurely: Detect via `poll()`, raise `RuntimeError` with exit code
- Server fails to start within timeout: Raise `RuntimeError` with timeout duration
- No GGUF files in HuggingFace repo: Print error and `sys.exit(1)`

**Request Errors:**
- Network failures: Catch `requests.ConnectionError`, return `{"error": str(e)}`
- HTTP errors (non-200): `r.raise_for_status()` will raise, caught and returned as error dict
- JSON decode errors in streaming: Catch `json.JSONDecodeError`, continue to next line
- Malformed streaming format: Check `line.startswith("data: ")` before parsing

**Runtime Behavior:**
- Errors in handlers return error responses, not exceptions
- Errors in streaming generators yield error responses
- No retry logic; errors propagate to client as-is

## Mocking & External Dependencies

**Not Applicable:**
- No unit test framework (pytest, unittest)
- No mocking library (unittest.mock, pytest-mock)
- Tests run against real llama-server instance
- All external calls (HuggingFace, llama-server) are live

**External Services in Use:**
- `huggingface_hub` (real HF API): Used by `download_model()` - no mocking
- `requests` library: Makes real HTTP calls to llama-server on localhost:8080
- `runpod` client: Real RunPod serverless integration (mocked only in local `--rp_serve_api` mode)

## Test Data & Fixtures

**Test Inputs:**
All test data defined in `.runpod/tests.json`:

```json
{
  "name": "Chat completion - basic",
  "input": {
    "messages": [
      {"role": "user", "content": "Say hello in exactly 3 words."}
    ],
    "max_tokens": 32,
    "temperature": 0.1
  }
}
```

**Characteristics:**
- Minimal: Use small `max_tokens` (8-32) to keep test runtime short
- Deterministic: Use low temperature (0.0-0.1) to reduce output variance
- Representative: Cover core input formats (messages, prompt, OpenAI passthrough)

**No Fixture Framework:**
- No factory functions or shared setup
- Each test is self-contained
- Test data hardcoded inline in test definition

## Coverage Targets

**Requirements:** No explicit coverage requirements enforced

**What IS tested:**
- All three input formats (chat messages, simple prompt, OpenAI passthrough)
- Both sync and async paths (via streaming tests)
- System prompt handling in chat format
- Parameter passthrough (max_tokens, temperature)

**What IS NOT tested:**
- Error cases (malformed input, missing required fields)
- Concurrent requests (N_PARALLEL parameter not exercised)
- GPU layer offloading (no CUDA validation in tests)
- Model auto-detection (all tests specify HF_REPO_ID, not testing find_gguf_file)
- Cache behavior (tests don't verify network volume caching)
- Edge cases (very large context sizes, invalid quantization specs)

## Local Development Testing

**Prerequisites:**
- CUDA-capable GPU (or CPU mode with `--rp_serve_api`)
- Python 3.10+ with `requests`, `runpod`, `huggingface-hub` installed
- Valid HuggingFace model repo specified in `HF_REPO_ID`

**Manual Testing Workflow:**
```bash
# 1. Set environment for desired model
export HF_REPO_ID="bartowski/Qwen_Qwen3.5-9B-GGUF"
export HF_FILENAME="Qwen_Qwen3.5-9B-Q4_K_M.gguf"
export CTX_SIZE="8192"

# 2. Start handler (downloads model, launches llama-server, starts RunPod API)
python handler.py --rp_serve_api

# 3. In another terminal, send test requests
# The handler will be available at http://localhost:8000 for RunPod requests
```

**What Happens:**
1. `handler.py` runs module-level startup code
2. Downloads model from HuggingFace (or uses cache)
3. Launches `llama-server` subprocess
4. Polls `/health` until server responds with `"status": "ok"`
5. Starts RunPod serverless listener on port 8000
6. Accepts job payloads and routes to `dispatch()`

## Continuous Integration

**Platform:** RunPod Hub

**Trigger:** Deployment of new image version

**Execution:** Automatic test run via `.runpod/tests.json`

**Pass Criteria:**
- All tests return expected HTTP status code (200)
- All tests complete within specified timeout
- No crashes or exceptions during execution

## Testing Best Practices Observed

**Strengths:**
- Tests validate real end-to-end behavior (no mocks hide integration issues)
- Multiple input format coverage ensures API compatibility
- Timeouts prevent hanging on startup failures

**Gaps:**
- No error case testing
- No concurrent request testing
- No coverage metrics
- No regression test suite for deployment checklist
- Auto-detection logic (`find_gguf_file()`) never directly tested

---

*Testing analysis: 2026-03-14*
