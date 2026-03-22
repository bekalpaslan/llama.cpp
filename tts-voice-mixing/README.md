# Voice Blending Module for Kokoro TTS

Weighted voice mixing for the RunPod TTS worker's Kokoro engine. Blend 2-5 Kokoro voices with arbitrary weights to create custom voice combinations -- for example, 70% `af_heart` + 30% `af_bella` produces a voice audibly distinct from either input. Works by computing a weighted sum of Kokoro voice tensors and passing the blended tensor directly to the synthesis pipeline.

## Voice Blend Syntax

| Syntax | Effect |
|--------|--------|
| `af_heart` | Single voice (no blending) |
| `af_heart,af_bella` | Equal-weight blend (50/50) |
| `af_heart:70,af_bella:30` | Weighted blend (70/30) |
| `af_heart:2,af_bella:1,af_sarah:1` | Ratio-based (50/25/25 after normalization) |

Weights are automatically normalized to sum to 1.0. You can use percentages, ratios, or any positive numbers.

## Validation Rules

- **Same language only:** All voices in a blend must share the same language prefix (e.g., `af_` and `am_` are both American English `a`). Cross-language blends like `af_heart` + `jf_alpha` are rejected.
- **2-5 voices:** Blends with more than 5 voices are rejected.
- **Positive weights:** Zero, negative, and non-numeric weights are rejected.
- **Known voices only:** All voice names must exist in KOKORO_VOICES.
- **Kokoro engine only:** Voice blending is only supported when `TTS_ENGINE=kokoro`.

## Integration Steps

Copy these files into your `tts-worker/` deployment:

### 1. Copy the blend module

```bash
cp tts-voice-mixing/voice_blend.py tts-worker/voice_blend.py
```

### 2. Replace the Kokoro engine

```bash
cp tts-voice-mixing/patches/kokoro_engine.py tts-worker/engines/kokoro_engine.py
```

### 3. Replace the handler

```bash
cp tts-voice-mixing/patches/handler.py tts-worker/handler.py
```

### 4. Update test inputs

```bash
cp tts-voice-mixing/patches/tests.json tts-worker/.runpod/tests.json
```

### 5. Rebuild and redeploy

```bash
cd tts-worker
docker build --platform linux/amd64 -t your-registry/tts-worker:latest .
docker push your-registry/tts-worker:latest
```

## API Examples

### Single voice (unchanged)

```bash
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "text": "Hello world",
      "voice": "af_heart",
      "speed": 1.0,
      "response_format": "wav"
    }
  }'
```

### Weighted voice blend

```bash
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "text": "This is a blended voice.",
      "voice": "af_heart:70,af_bella:30",
      "speed": 1.0,
      "response_format": "wav"
    }
  }'
```

### Equal-weight blend

```bash
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "text": "Equal mix of three voices.",
      "voice": "af_heart,af_bella,af_sarah",
      "speed": 1.0,
      "response_format": "wav"
    }
  }'
```

## Module API

```python
from voice_blend import parse_voice_spec, validate_blend_request, blend_voices, MAX_BLEND_VOICES

# Parse a voice spec into (name, weight) tuples
parts = parse_voice_spec("af_heart:70,af_bella:30")
# [("af_heart", 0.7), ("af_bella", 0.3)]

# Validate before processing (returns None or error string)
error = validate_blend_request("af_heart:70,af_bella:30", KOKORO_VOICES, "kokoro")

# Blend voice tensors (requires a KPipeline instance)
blended_tensor = blend_voices(pipeline, parts)
```

## File Structure

```
tts-voice-mixing/
  voice_blend.py          # Core blend module (copy to tts-worker/)
  test_voice_blend.py     # Pytest test suite (20 tests)
  README.md               # This file
  patches/
    kokoro_engine.py       # Drop-in replacement for engines/kokoro_engine.py
    handler.py             # Drop-in replacement for handler.py
    tests.json             # Drop-in replacement for .runpod/tests.json
```

## Running Tests

```bash
cd tts-voice-mixing
python -m pytest test_voice_blend.py -v
```

No GPU or Kokoro installation required for unit tests -- torch tensors and mocked pipelines are used.
