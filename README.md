# LlamaCpp RunPod Worker

RunPod Serverless worker that serves any GGUF model from HuggingFace via llama.cpp with an OpenAI-compatible API.

## Features

- **Any GGUF model** — just set `HF_REPO_ID` and optionally `HF_FILENAME`
- **Auto-detection** — leave `HF_FILENAME` blank and the worker finds the best Q4_K_M GGUF automatically
- **OpenAI-compatible API** — drop-in replacement for OpenAI SDK
- **Streaming** — SSE streaming via RunPod's `/stream` endpoint
- **GPU acceleration** — CUDA with flash attention, quantized KV cache
- **Network volume caching** — download once, reuse across cold starts
- **35 pre-configured model presets** — Qwen 3.5, DeepSeek R1, Llama 3/4, Mistral, Phi-4, Gemma 3, and more

## Quick Start

### Deploy on RunPod

1. Create a **Serverless Endpoint** in the RunPod console.
2. Set the container image to `alpaslanbek/llamacpp-worker:latest`.
3. Set environment variables:
   - `HF_REPO_ID` — e.g. `bartowski/Qwen_Qwen3.5-9B-GGUF`
   - `HF_FILENAME` — e.g. `Qwen_Qwen3.5-9B-Q4_K_M.gguf` (optional, auto-detects)

### Deploy via RunPod Hub

Use one of the 35 pre-configured model presets for one-click deploy. See `.runpod/hub.json` for the full preset list.

## Input Formats

### Chat Messages
```json
{
  "input": {
    "messages": [
      {"role": "system", "content": "You are helpful."},
      {"role": "user", "content": "Hello!"}
    ],
    "max_tokens": 512,
    "temperature": 0.7
  }
}
```

### Simple Prompt
```json
{
  "input": {
    "prompt": "The meaning of life is",
    "max_tokens": 256
  }
}
```

### OpenAI Passthrough
```json
{
  "input": {
    "openai_route": "/v1/chat/completions",
    "openai_input": {
      "model": "default",
      "messages": [{"role": "user", "content": "Hi"}],
      "max_tokens": 512
    }
  }
}
```

### Streaming
Add `"stream": true` to any messages or OpenAI passthrough input. Poll the `/stream/{job_id}` endpoint for chunks.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HF_REPO_ID` | required | HuggingFace repo with GGUF model |
| `HF_FILENAME` | auto-detect | Specific GGUF file to download |
| `HF_TOKEN` | | Auth token for gated models |
| `MODEL_NAME` | `default` | Display name in `/v1/models` |
| `N_GPU_LAYERS` | `99` | GPU layers to offload (99 = all) |
| `CTX_SIZE` | `4096` | Context window size |
| `N_PARALLEL` | `1` | Concurrent inference slots |
| `FLASH_ATTN` | `on` | Flash attention (on/off/auto) |
| `KV_CACHE_TYPE` | `f16` | KV cache type: f16, q8_0, q4_0 |
| `EXTRA_ARGS` | | Additional llama-server flags |
| `STARTUP_TIMEOUT` | `600` | Seconds to wait for llama-server to start |

## Model Presets

| Model | Recommended GPU |
|-------|-----------------|
| Qwen 3.5 35B-A3B | RTX A5000 |
| Qwen 3.5 9B | RTX A4000 |
| Qwen 3.5 27B | RTX A5000 |
| Qwen 3.5 4B | RTX A4000 |
| Qwen 3.5 122B-A10B | A100 80GB |
| DeepSeek R1 Distill Qwen 7B | RTX A4000 |
| DeepSeek R1 Distill Qwen 14B | RTX A4000 |
| DeepSeek R1 Distill Qwen 32B | RTX A5000 |
| DeepSeek R1 Distill Llama 8B | RTX A4000 |
| Qwen 3 8B | RTX A4000 |
| Qwen 3 14B | RTX A4000 |
| Qwen 3 32B | RTX A5000 |
| Qwen 3 30B-A3B | RTX A5000 |
| Qwen3 Coder Next 80B-A3B | A6000 |
| Qwen 2.5 Coder 32B | RTX A5000 |
| Qwen 2.5 Coder 14B | RTX A4000 |
| Qwen 2.5 Coder 7B | RTX A4000 |
| QwQ-32B | RTX A5000 |
| Llama 4 Scout 17B-16E | A6000 |
| Llama 3.3 70B Instruct | A6000 |
| Llama 3.1 8B Instruct | RTX A4000 |
| Llama 3.2 3B Instruct | RTX A4000 |
| Mistral Small 3.2 24B | RTX A5000 |
| Mistral Nemo 12B | RTX A4000 |
| Devstral Small 2 24B | RTX A5000 |
| Phi-4 14B | RTX A4000 |
| Phi-4 Reasoning Plus 14B | RTX A4000 |
| Phi-4 Mini Reasoning 3.8B | RTX A4000 |
| Gemma 3 27B | RTX A5000 |
| Gemma 3 12B | RTX A4000 |
| Gemma 3 4B | RTX A4000 |
| GLM-4 9B | RTX A4000 |
| GLM-4.7 Flash 30B-A3B | RTX A4000 |
| Hermes 4 14B | RTX A4000 |
| OpenAI GPT-oss 20B | RTX A5000 |
| SmolLM3 3B | RTX A4000 |

## Development

### Local Testing

```bash
export HF_REPO_ID="bartowski/Qwen_Qwen3.5-9B-GGUF"
python handler.py --rp_serve_api
```

### Building the Image

```bash
docker build --platform linux/amd64 -t alpaslanbek/llamacpp-worker:latest .
docker push alpaslanbek/llamacpp-worker:latest
```

## License

MIT
