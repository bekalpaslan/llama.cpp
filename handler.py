"""
RunPod Serverless Handler for llama.cpp GGUF models.

Starts llama-server as a subprocess and proxies requests to its
OpenAI-compatible API. Supports chat completions, text completions,
and direct OpenAI passthrough.
"""

import json
import os
import subprocess
import time

import requests
import runpod

from download_model import download_model

# ---------------------------------------------------------------------------
# Configuration (all tuneable via environment variables)
# ---------------------------------------------------------------------------
HF_REPO_ID = os.environ.get("HF_REPO_ID", "")
HF_FILENAME = os.environ.get("HF_FILENAME", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "default")

N_GPU_LAYERS = int(os.environ.get("N_GPU_LAYERS", "99"))
CTX_SIZE = int(os.environ.get("CTX_SIZE", "4096"))
N_PARALLEL = int(os.environ.get("N_PARALLEL", "1"))
FLASH_ATTN = os.environ.get("FLASH_ATTN", "on")
KV_CACHE_TYPE = os.environ.get("KV_CACHE_TYPE", "f16")
EXTRA_ARGS = os.environ.get("EXTRA_ARGS", "")

SERVER_PORT = 8080
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"
STARTUP_TIMEOUT = int(os.environ.get("STARTUP_TIMEOUT", "600"))

# ---------------------------------------------------------------------------
# Startup: download model & launch llama-server
# ---------------------------------------------------------------------------
print("=" * 60)
print("LlamaCpp RunPod Worker — Starting up")
print("=" * 60)

if not HF_REPO_ID:
    raise RuntimeError("HF_REPO_ID environment variable is required")

model_path = download_model(
    repo_id=HF_REPO_ID,
    filename=HF_FILENAME or None,
    token=HF_TOKEN or None,
)

cmd = [
    "llama-server",
    "-m", model_path,
    "--host", "0.0.0.0",
    "--port", str(SERVER_PORT),
    "-ngl", str(N_GPU_LAYERS),
    "-c", str(CTX_SIZE),
    "-fa", FLASH_ATTN,
    "-np", str(N_PARALLEL),
    "-ctk", KV_CACHE_TYPE,
    "-ctv", KV_CACHE_TYPE,
    "-a", MODEL_NAME,
    "--no-webui",
    "--metrics",
]

if EXTRA_ARGS:
    cmd.extend(EXTRA_ARGS.split())

print(f"Starting llama-server: {' '.join(cmd)}")
server_process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)

# Wait for the server to be healthy
print("Waiting for llama-server to become ready...")
for i in range(STARTUP_TIMEOUT):
    if server_process.poll() is not None:
        raise RuntimeError(
            f"llama-server exited with code {server_process.returncode}"
        )
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=2)
        if r.status_code == 200:
            health = r.json()
            if health.get("status") == "ok":
                print(f"llama-server ready after {i + 1}s")
                break
    except requests.ConnectionError:
        pass
    time.sleep(1)
else:
    raise RuntimeError(
        f"llama-server did not become ready within {STARTUP_TIMEOUT}s"
    )


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
def handler(job):
    """
    Accepts three input formats:

    1. OpenAI passthrough:
       {"openai_route": "/v1/chat/completions", "openai_input": {...}}

    2. Chat messages:
       {"messages": [...], "max_tokens": 512, "temperature": 0.7, ...}

    3. Simple prompt:
       {"prompt": "Hello", "max_tokens": 512, "temperature": 0.7, ...}
    """
    job_input = job["input"]

    # --- Format 1: OpenAI passthrough ---
    if "openai_route" in job_input:
        route = job_input["openai_route"]
        payload = dict(job_input.get("openai_input", {}))
        payload["stream"] = False

        try:
            r = requests.post(
                f"{BASE_URL}{route}",
                json=payload,
                timeout=600,
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            return {"error": str(e)}

    # --- Format 2: Chat messages ---
    messages = job_input.get("messages")
    if messages:
        payload = {
            "model": MODEL_NAME,
            "messages": messages,
            "max_tokens": job_input.get("max_tokens", 512),
            "temperature": job_input.get("temperature", 0.7),
            "top_p": job_input.get("top_p", 0.9),
            "stream": False,
        }
        # Pass through optional params
        for key in ("stop", "frequency_penalty", "presence_penalty",
                     "top_k", "min_p", "seed"):
            if key in job_input:
                payload[key] = job_input[key]

        try:
            r = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                json=payload,
                timeout=600,
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            return {"error": str(e)}

    # --- Format 3: Simple prompt ---
    prompt = job_input.get("prompt", "")
    if prompt:
        payload = {
            "prompt": prompt,
            "n_predict": job_input.get("max_tokens", 512),
            "temperature": job_input.get("temperature", 0.7),
            "top_p": job_input.get("top_p", 0.9),
            "stream": False,
        }
        for key in ("stop", "top_k", "min_p", "seed",
                     "frequency_penalty", "presence_penalty"):
            if key in job_input:
                payload[key] = job_input[key]

        try:
            r = requests.post(
                f"{BASE_URL}/completion",
                json=payload,
                timeout=600,
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            return {"error": str(e)}

    return {"error": "Provide 'messages', 'prompt', or 'openai_route' + 'openai_input'"}


# ---------------------------------------------------------------------------
# Streaming handler (generator)
# ---------------------------------------------------------------------------
def stream_handler(job):
    """
    Generator handler for streaming responses.
    Use by sending {"stream": true} in the job input along with messages or
    an openai passthrough. Chunks are available via the /stream endpoint.
    """
    job_input = job["input"]

    # Determine route and payload
    if "openai_route" in job_input:
        route = job_input["openai_route"]
        payload = dict(job_input.get("openai_input", {}))
    elif "messages" in job_input:
        route = "/v1/chat/completions"
        payload = {
            "model": MODEL_NAME,
            "messages": job_input["messages"],
            "max_tokens": job_input.get("max_tokens", 512),
            "temperature": job_input.get("temperature", 0.7),
            "top_p": job_input.get("top_p", 0.9),
        }
        for key in ("stop", "frequency_penalty", "presence_penalty",
                     "top_k", "min_p", "seed"):
            if key in job_input:
                payload[key] = job_input[key]
    else:
        yield {"error": "Streaming requires 'messages' or 'openai_route'"}
        return

    payload["stream"] = True

    try:
        r = requests.post(
            f"{BASE_URL}{route}",
            json=payload,
            stream=True,
            timeout=600,
        )
        r.raise_for_status()

        for line in r.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8")
            if line.startswith("data: "):
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    continue
    except requests.RequestException as e:
        yield {"error": str(e)}


# ---------------------------------------------------------------------------
# Route to the right handler
# ---------------------------------------------------------------------------
def dispatch(job):
    if job["input"].get("stream", False):
        return stream_handler(job)
    return handler(job)


runpod.serverless.start({
    "handler": dispatch,
    "return_aggregate_stream": True,
})
