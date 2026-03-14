# LlamaCpp RunPod Worker

RunPod Serverless worker that serves any GGUF model from HuggingFace via llama.cpp with an OpenAI-compatible API.

## Features

- **Any GGUF model** — just set `HF_REPO_ID` and optionally `HF_FILENAME`
- **Auto-detection** — leave `HF_FILENAME` blank and the worker finds the best Q4_K_M GGUF automatically
- **OpenAI-compatible API** — drop-in replacement for OpenAI SDK
- **Streaming** — SSE streaming via RunPod's `/stream` endpoint
- **GPU acceleration** — CUDA with flash attention, quantized KV cache
- **Network volume caching** — download once, reuse across cold starts
- **19 pre-configured model presets** — Qwen 3.5, DeepSeek R1, Llama 3, Mistral, Phi-4, Gemma 3, and more

## Quick Start

### Deploy on RunPod

1. Build and push the Docker image:
   ```bash
   docker build --platform linux/amd64 -t yourusername/llamacpp-worker:latest .
   docker push yourusername/llamacpp-worker:latest
   ```

2. Create a Serverless Endpoint in RunPod console pointing to your image.

3. Set environment variables:
   - `HF_REPO_ID` — e.g. `bartowski/Qwen_Qwen3.5-9B-GGUF`
   - `HF_FILENAME` — e.g. `Qwen_Qwen3.5-9B-Q4_K_M.gguf` (optional, auto-detects)

### Deploy via RunPod Hub

Submit this repo to RunPod Hub for one-click deploy with model presets. See `.runpod/hub.json` for the full preset list.

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
| `CTX_SIZE` | `8192` | Context window size |
| `N_PARALLEL` | `1` | Concurrent inference slots |
| `FLASH_ATTN` | `on` | Flash attention (on/off/auto) |
| `KV_CACHE_TYPE` | `f16` | KV cache type: f16, q8_0, q4_0 |
| `EXTRA_ARGS` | | Additional llama-server flags |

## Model Presets

| Model | Active Params | VRAM (Q4_K_M) | Recommended GPU |
|-------|--------------|---------------|-----------------|
| Qwen 3.5 35B-A3B | 3B | ~23 GB | RTX A5000 24GB |
| Qwen 3.5 9B | 9B | ~7 GB | RTX A4000 16GB |
| Qwen 3.5 27B | 27B | ~19 GB | RTX A5000 24GB |
| Qwen 3.5 4B | 4B | ~4 GB | RTX A4000 16GB |
| Qwen 3.5 122B-A10B | 10B | ~76 GB | A100 80GB |
| DeepSeek R1 Distill 7B | 7B | ~5 GB | RTX A4000 16GB |
| DeepSeek R1 Distill 14B | 14B | ~9 GB | RTX A4000 16GB |
| DeepSeek R1 Distill 32B | 32B | ~20 GB | RTX A5000 24GB |
| Llama 3.3 70B | 70B | ~42 GB | A6000 48GB |
| Mistral Small 3.2 24B | 24B | ~14 GB | RTX A5000 24GB |
| Devstral Small 2 24B | 24B | ~14 GB | RTX A5000 24GB |
| Phi-4 14B | 14B | ~9 GB | RTX A4000 16GB |
| Gemma 3 12B | 12B | ~7 GB | RTX A4000 16GB |
| GLM-4 9B | 9B | ~6 GB | RTX A4000 16GB |

## Local Testing

```bash
# Test with a local GGUF
export HF_REPO_ID="bartowski/Qwen_Qwen3.5-9B-GGUF"
python handler.py --rp_serve_api
```

## License

MIT
