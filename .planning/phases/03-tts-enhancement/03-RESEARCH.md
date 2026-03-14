# Phase 3: TTS Enhancement - Research

**Researched:** 2026-03-14
**Domain:** Kokoro TTS voice mixing/blending in RunPod serverless handler
**Confidence:** HIGH

## Summary

Phase 3 adds voice mixing (weighted blending of multiple Kokoro voices) to the existing shipped TTS worker at `runpod-workers-hub/tts-worker`. The worker already supports three engines (Kokoro, Dia, F5-TTS) with an OpenAI-compatible API, 42+ voices, and WAV/FLAC/PCM output. The change is narrowly scoped: modify the Kokoro engine to accept voice blend specifications and expose this through the existing API.

Kokoro's voice system represents each voice as a PyTorch tensor (shape roughly `[511, 1, 256]`). The official `kokoro` Python library (v0.9.4+) natively supports equal-weight voice blending by passing comma-separated voice names to `KPipeline.__call__()` -- it calls `torch.mean(torch.stack(packs), dim=0)` internally. However, **weighted blending is NOT natively supported** by the library. To implement TTS-01 ("weighted mixing"), we need to manually load voice tensors and compute `sum(voice_i * weight_i)` before passing the resulting tensor to the pipeline. The Kokoro-FastAPI project demonstrates a proven pattern for this using parenthesized weights: `"af_bella(2)+af_sky(1)"`.

**Primary recommendation:** Implement weighted voice blending in `kokoro_engine.py` by intercepting the `voice` parameter before it reaches `KPipeline`, parsing a weight syntax (e.g., `af_bella:70,af_sarah:30`), manually loading and blending the voice tensors, then passing the blended tensor directly to the pipeline. This is a single-file change plus handler input validation. No Dockerfile, requirements, or engine architecture changes needed.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TTS-01 | User can blend multiple voices with weighted mixing (Kokoro voice mixing) | Kokoro voice tensors are `.pt` files that can be loaded via `KPipeline.load_voice()` or `torch.load()`. Blending is tensor arithmetic: `voice_a * 0.7 + voice_b * 0.3`. The pipeline accepts raw `torch.FloatTensor` as the `voice` parameter, so blended tensors can be passed directly. Weight normalization ensures weights sum to 1.0. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| kokoro | >=0.9.4 | TTS engine with voice pipeline | Already installed in the TTS worker. Provides `KPipeline` with native voice loading and `.pt` tensor handling |
| torch | 2.6.0 | Tensor operations for voice blending | Already installed. Used for `torch.load()`, `torch.stack()`, tensor arithmetic |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | (existing) | Audio array concatenation | Already used in kokoro_engine.py for `np.concatenate(chunks)` |
| soundfile | (existing) | WAV encoding | Already used for output encoding |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom weight parsing | Kokoro's native comma-separated blending | Native only supports equal-weight averaging. We need weighted mixing per TTS-01 |
| `voice_a:70,voice_b:30` syntax | `voice_a(2)+voice_b(1)` syntax (Kokoro-FastAPI style) | Colon-weight syntax is more intuitive for percentages. Kokoro-FastAPI uses parenthesized ratios which auto-normalize. Either works; colon syntax is more consistent with CLI tools like nazdridoy/kokoro-tts |

**Installation:** No new packages required. All dependencies already exist in the TTS worker.

## Architecture Patterns

### Existing TTS Worker Structure (NO CHANGES needed to structure)
```
tts-worker/
├── Dockerfile           # NO CHANGE
├── handler.py           # MINOR: accept blend syntax in voice param, validate
├── engines/
│   ├── base.py          # NO CHANGE
│   ├── kokoro_engine.py # PRIMARY: add voice blending logic
│   ├── dia_engine.py    # NO CHANGE
│   └── f5_engine.py     # NO CHANGE
├── requirements.txt     # NO CHANGE
├── .runpod/
│   ├── hub.json         # NO CHANGE
│   └── tests.json       # ADD: voice blending test case
└── README.md            # UPDATE: document voice blending feature
```

### Pattern 1: Voice Blending via Tensor Arithmetic
**What:** Parse weighted voice specification, load individual voice tensors, compute weighted sum, pass blended tensor to KPipeline.
**When to use:** Any time the `voice` parameter contains a blend specification (detected by presence of `,` or `+` delimiter).
**Example:**
```python
# Source: Kokoro pipeline.py voice loading + Kokoro-FastAPI voice combination pattern
import torch
from kokoro import KPipeline

def blend_voices(pipeline: KPipeline, voice_spec: str) -> torch.FloatTensor:
    """
    Parse voice specification and return blended tensor.

    Supported formats:
      - "af_heart"              -> single voice (no blending)
      - "af_heart,af_bella"     -> equal-weight blend (50/50)
      - "af_heart:70,af_bella:30" -> weighted blend (70/30)

    Weights are normalized to sum to 1.0.
    """
    parts = voice_spec.split(",")
    if len(parts) == 1 and ":" not in parts[0]:
        return voice_spec  # single voice, let pipeline handle it

    voices = []
    weights = []
    for part in parts:
        part = part.strip()
        if ":" in part:
            name, weight = part.rsplit(":", 1)
            voices.append(name.strip())
            weights.append(float(weight))
        else:
            voices.append(part)
            weights.append(1.0)

    # Normalize weights to sum to 1.0
    total = sum(weights)
    weights = [w / total for w in weights]

    # Load voice tensors and compute weighted sum
    tensors = [pipeline.load_voice(v) for v in voices]
    blended = sum(t * w for t, w in zip(tensors, weights))
    return blended
```

### Pattern 2: Handler Input Validation
**What:** Validate voice blend input in the handler before passing to engine. Ensure all referenced voices exist, weights are positive numbers, and at least 2 voices are specified for blending.
**When to use:** In `handler.py` when `TTS_ENGINE == "kokoro"` and voice param contains blend syntax.
**Example:**
```python
# In handler.py, before engine.generate()
voice = job_input.get("voice", "af_heart")

# Voice blending only supported for Kokoro engine
if TTS_ENGINE == "kokoro" and ("," in voice):
    # Validate: extract voice names and check they exist
    parts = voice.split(",")
    for part in parts:
        name = part.split(":")[0].strip()
        if name not in KOKORO_VOICES:
            return {"error": f"Unknown voice: '{name}'. Use list_voices to see available voices."}
```

### Anti-Patterns to Avoid
- **Pre-generating all possible blends at startup:** There are 42+ voices, so the combinatorial space is enormous. Blend on-demand per request.
- **Saving blended voices to disk:** For a serverless worker, blended tensors should be computed per-request. Caching to disk adds I/O without benefit since each request may have different weights.
- **Modifying KPipeline internals:** Use the public API (`load_voice()` for tensor loading, pass tensor as `voice` parameter). Do not monkey-patch or subclass KPipeline.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Voice tensor loading | Custom file loading from HuggingFace | `pipeline.load_voice(voice_name)` | KPipeline already handles HF download, caching, and tensor loading. It returns a `torch.FloatTensor` ready for arithmetic. |
| Weight normalization | Manual percentage validation | `weights = [w / sum(weights) for w in weights]` | Simple list comprehension. Auto-normalizes any positive numbers to sum to 1.0. No need for requiring they sum to 100. |
| Audio chunking + concatenation | Custom audio stitching | Existing `KokoroEngine.generate()` loop | The existing engine already handles text chunking via `pipeline()` generator and `np.concatenate()`. Voice blending happens before this loop, not during it. |

**Key insight:** Voice blending is a pre-processing step on the voice parameter. The entire synthesis pipeline (text splitting, phoneme conversion, audio generation, chunk concatenation) remains unchanged. The only new code is parsing the voice spec and computing a weighted tensor sum.

## Common Pitfalls

### Pitfall 1: Language Mismatch in Blended Voices
**What goes wrong:** User blends an American English voice (`af_heart`) with a Japanese voice (`jf_alpha`). The result uses the wrong phoneme pipeline.
**Why it happens:** `KPipeline` is initialized with a `lang_code` and selects the phonemizer accordingly. Mixing voices from different languages produces a tensor that works but sounds wrong because the phonemes don't match one of the voice's training data.
**How to avoid:** Validate that all voices in a blend share the same language prefix (first character). Return an error if they don't match. Example: `af_heart:70,am_adam:30` is valid (both `a` = American English), but `af_heart:70,jf_alpha:30` should be rejected or warned.
**Warning signs:** Garbled or heavily accented output when blending cross-language voices.

### Pitfall 2: Invalid Weight Values
**What goes wrong:** User passes negative weights, zero weights, or non-numeric weight values.
**Why it happens:** No input validation on weight portion of the voice spec.
**How to avoid:** Validate that all weights are positive numbers. Return a clear error for invalid formats.
**Warning signs:** Silent `float()` conversion errors or division-by-zero in normalization.

### Pitfall 3: Single Voice with Weight Syntax
**What goes wrong:** User passes `"af_heart:100"` expecting it to work as a single voice, but the colon triggers blend parsing which fails because there's only one voice.
**How to avoid:** Treat a single voice with weight as valid (just use that voice directly). The blend logic should handle len(parts)==1 gracefully.
**Warning signs:** Unnecessary errors on valid-intent inputs.

### Pitfall 4: Assuming Kokoro's Native Comma Blending Handles Weights
**What goes wrong:** Developer passes `"af_heart:70,af_bella:30"` directly to `KPipeline.load_voice()` expecting it to parse weights.
**Why it happens:** Kokoro's native comma blending only does equal-weight averaging via `torch.mean(torch.stack(packs), dim=0)`. It does not parse weights.
**How to avoid:** Intercept the voice parameter in `kokoro_engine.py` BEFORE passing to the pipeline. Parse weights manually, compute weighted sum, then pass the resulting tensor to the pipeline.
**Warning signs:** Weights being ignored silently, all blends sounding identical regardless of weights.

## Code Examples

Verified patterns from official sources and the existing TTS worker:

### Loading Voice Tensors from KPipeline
```python
# Source: Kokoro pipeline.py / DeepWiki documentation
# KPipeline.load_voice() returns a torch.FloatTensor
# It handles HuggingFace download + caching automatically.

pipeline = KPipeline(lang_code="a", device="cuda")
voice_tensor = pipeline.load_voice("af_heart")  # Returns torch.FloatTensor
# voice_tensor shape: approximately [511, 1, 256]
```

### Weighted Voice Blending (Manual)
```python
# Source: Kokoro HuggingFace README + Kokoro-FastAPI pattern
# Native KPipeline only does equal-weight. For weighted, use tensor math.

voice_a = pipeline.load_voice("af_heart")   # torch.FloatTensor
voice_b = pipeline.load_voice("af_bella")   # torch.FloatTensor
blended = voice_a * 0.7 + voice_b * 0.3     # Weighted sum
# Pass blended tensor directly as voice parameter:
for gs, ps, audio in pipeline(text, voice=blended, speed=1.0):
    chunks.append(audio)
```

### Equal-Weight Blending (Native Kokoro)
```python
# Source: Kokoro pipeline.py load_voice implementation
# Native support via comma-separated names (equal weight only):

for gs, ps, audio in pipeline(text, voice="af_heart,af_bella", speed=1.0):
    chunks.append(audio)
# Internally: torch.mean(torch.stack([af_heart_tensor, af_bella_tensor]), dim=0)
```

### Existing KokoroEngine.generate() (Current Code)
```python
# Source: tts-worker/engines/kokoro_engine.py (existing shipped code)
def generate(self, text, voice="af_heart", speed=1.0, **kwargs):
    lang_code = LANG_MAP.get(voice[0], "a") if voice else "a"
    pipeline = self._get_pipeline(lang_code)
    chunks = []
    for _, _, audio in pipeline(text, voice=voice, speed=speed):
        chunks.append(audio)
    if not chunks:
        return b"", 24000
    full_audio = np.concatenate(chunks)
    buf = io.BytesIO()
    sf.write(buf, full_audio, 24000, format="WAV")
    return buf.getvalue(), 24000
```

### Modified generate() with Voice Blending
```python
# Proposed modification to kokoro_engine.py
def generate(self, text, voice="af_heart", speed=1.0, **kwargs):
    # Detect blend syntax
    if "," in voice:
        voice_tensor, lang_code = self._blend_voices(voice)
    else:
        voice_tensor = voice  # string -> let pipeline resolve
        lang_code = LANG_MAP.get(voice[0], "a") if voice else "a"

    pipeline = self._get_pipeline(lang_code)
    chunks = []
    for _, _, audio in pipeline(text, voice=voice_tensor, speed=speed):
        chunks.append(audio)
    if not chunks:
        return b"", 24000
    full_audio = np.concatenate(chunks)
    buf = io.BytesIO()
    sf.write(buf, full_audio, 24000, format="WAV")
    return buf.getvalue(), 24000
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed single voices only | Voice embedding blending via tensor arithmetic | Kokoro v0.9+ (2025) | Enables creative voice design without training new voice models |
| Manual `.pt` file editing | API-level voice combination syntax | Kokoro-FastAPI (2025) | Users can blend voices via API parameters, no file management |

**Deprecated/outdated:**
- Kokoro versions before 0.9.x had fewer voices and less mature voice loading APIs. Current v0.9.4+ has stable `load_voice()` API.

## Open Questions

1. **Maximum number of voices in a blend**
   - What we know: Tensor arithmetic works with any number of voices. Kokoro-FastAPI and CLI tools typically show 2-voice examples.
   - What's unclear: Whether blending 3+ voices produces useful results or just mud.
   - Recommendation: Support 2-5 voices in a blend. Document that 2-3 voices produce the best results. Reject blends with more than 5 voices.

2. **Voice tensor caching for repeated blend requests**
   - What we know: `KPipeline.load_voice()` caches individual voice tensors in `self.voices` dict. Blended tensors are NOT cached by default.
   - What's unclear: Whether recomputing the blend per-request adds meaningful latency.
   - Recommendation: Don't cache blended tensors initially. The tensor arithmetic (`voice_a * 0.7 + voice_b * 0.3`) is sub-millisecond. Optimize only if profiling shows a need.

3. **Whether `load_voice` is a public stable API**
   - What we know: DeepWiki and multiple third-party implementations use `pipeline.load_voice()`. The method exists in pipeline.py.
   - What's unclear: Whether hexgrad considers this a stable public API or internal.
   - Recommendation: Use it. It's the only way to get voice tensors. If it changes, the fix is a single line.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | RunPod integration tests via `.runpod/tests.json` |
| Config file | `.runpod/tests.json` |
| Quick run command | `python handler.py --rp_serve_api` (local test server) |
| Full suite command | Deploy to RunPod, run tests.json via RunPod API |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TTS-01 | Equal-weight voice blend generates audio | integration | Add to `.runpod/tests.json`: voice "af_heart,af_bella" | No - Wave 0 |
| TTS-01 | Weighted voice blend generates audio | integration | Add to `.runpod/tests.json`: voice "af_heart:70,af_bella:30" | No - Wave 0 |
| TTS-01 | Blended voice is audibly different from singles | manual | Compare audio outputs of blend vs individual voices | manual-only: requires human listening |
| TTS-01 | Invalid blend syntax returns clear error | integration | Add to `.runpod/tests.json`: voice "af_heart:abc,af_bella:30" | No - Wave 0 |
| TTS-01 | Cross-language blend is rejected | integration | Add to `.runpod/tests.json`: voice "af_heart:50,jf_alpha:50" | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `python handler.py --rp_serve_api` + manual curl test
- **Per wave merge:** Full `.runpod/tests.json` suite on RunPod
- **Phase gate:** All tests.json entries pass on deployed endpoint

### Wave 0 Gaps
- [ ] Add voice blending test cases to `.runpod/tests.json`
- [ ] No unit test framework exists in the TTS worker (no pytest, no test directory). Integration testing via RunPod API is the established pattern. Adding unit tests for the blend parsing function would be valuable but is optional given the project's testing pattern.

## Sources

### Primary (HIGH confidence)
- [Kokoro GitHub (hexgrad/kokoro)](https://github.com/hexgrad/kokoro) - KPipeline API, voice loading, README
- [Kokoro pipeline.py source](https://github.com/hexgrad/kokoro/blob/main/kokoro/pipeline.py) - load_voice implementation, comma-separated blending via torch.mean(torch.stack())
- [DeepWiki: Kokoro Languages and Voices](https://deepwiki.com/hexgrad/kokoro/4-languages-and-voices) - Voice tensor structure [256], load_voice caching, blending mechanism
- [Kokoro-FastAPI (remsky/Kokoro-FastAPI)](https://github.com/remsky/Kokoro-FastAPI) - Production voice combination API pattern: `af_bella(2)+af_sky(1)` syntax, weight normalization
- [DeepWiki: Voice Blending (nazdridoy/kokoro-tts)](https://deepwiki.com/nazdridoy/kokoro-tts/3.2-voice-blending) - CLI blending syntax `af_sarah:60,am_adam:40`, weight normalization, binary blending constraint
- Existing TTS worker source code: `C:/Users/alpas/IdeaProjects/tts-worker/` - handler.py, engines/kokoro_engine.py, hub.json, tests.json

### Secondary (MEDIUM confidence)
- [PyKokoro documentation](https://pykokoro.readthedocs.io/en/latest/) - VoiceBlend.parse() API for ONNX backend (different from torch-based KPipeline but confirms the feature concept)
- [HuggingFace Kokoro-82M VOICES.md](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md) - Complete voice list, quality grades, naming convention

### Tertiary (LOW confidence)
- Maximum useful blend count (2-5 voices) - Based on community examples only, not benchmarked
- Voice tensor exact shape `[511, 1, 256]` - From DeepWiki, not verified against current Kokoro version. Shape may vary but arithmetic operations work regardless of exact dimensions.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new packages needed. Kokoro v0.9.4+ is already installed and its voice blending is well-documented.
- Architecture: HIGH - Single-file change to kokoro_engine.py + minor handler validation. Pattern proven by Kokoro-FastAPI.
- Pitfalls: HIGH - Language mismatch and weight validation are well-understood from existing implementations.

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (Kokoro ecosystem is stable; v0.9.4 API unlikely to change significantly)
