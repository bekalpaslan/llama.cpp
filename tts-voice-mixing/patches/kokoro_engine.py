"""Kokoro TTS engine with voice blending support.

Drop-in replacement for tts-worker/engines/kokoro_engine.py.
Adds weighted voice blending via the voice_blend module.
"""

import io

import numpy as np
import soundfile as sf
from engines.base import TTSEngine
from voice_blend import blend_voices, parse_voice_spec

KOKORO_VOICES = {
    "af_heart": "American Female - Heart",
    "af_alloy": "American Female - Alloy",
    "af_aoede": "American Female - Aoede",
    "af_bella": "American Female - Bella",
    "af_jessica": "American Female - Jessica",
    "af_kore": "American Female - Kore",
    "af_nicole": "American Female - Nicole",
    "af_nova": "American Female - Nova",
    "af_river": "American Female - River",
    "af_sarah": "American Female - Sarah",
    "af_sky": "American Female - Sky",
    "am_adam": "American Male - Adam",
    "am_echo": "American Male - Echo",
    "am_eric": "American Male - Eric",
    "am_fenrir": "American Male - Fenrir",
    "am_liam": "American Male - Liam",
    "am_michael": "American Male - Michael",
    "am_onyx": "American Male - Onyx",
    "am_puck": "American Male - Puck",
    "bf_alice": "British Female - Alice",
    "bf_emma": "British Female - Emma",
    "bf_isabella": "British Female - Isabella",
    "bf_lily": "British Female - Lily",
    "bm_daniel": "British Male - Daniel",
    "bm_fable": "British Male - Fable",
    "bm_george": "British Male - George",
    "bm_lewis": "British Male - Lewis",
    "jf_alpha": "Japanese Female - Alpha",
    "jm_kumo": "Japanese Male - Kumo",
    "zf_xiaobei": "Chinese Female - Xiaobei",
    "zf_xiaoni": "Chinese Female - Xiaoni",
    "zm_yunjian": "Chinese Male - Yunjian",
    "zm_yunxi": "Chinese Male - Yunxi",
    "ef_dora": "Spanish Female - Dora",
    "em_alex": "Spanish Male - Alex",
    "ff_siwis": "French Female - Siwis",
    "hf_alpha": "Hindi Female - Alpha",
    "hm_omega": "Hindi Male - Omega",
    "if_sara": "Italian Female - Sara",
    "im_nicola": "Italian Male - Nicola",
    "pf_dora": "Portuguese Female - Dora",
    "pm_alex": "Portuguese Male - Alex",
}

LANG_MAP = {
    "a": "a",
    "b": "b",
    "j": "j",
    "z": "z",
    "e": "e",
    "f": "f",
    "h": "h",
    "i": "i",
    "p": "p",
}


class KokoroEngine(TTSEngine):
    """Kokoro TTS engine with voice blending support."""

    def __init__(self):
        from kokoro import KPipeline

        print("Loading Kokoro TTS engine...")
        # Pre-load American English pipeline
        self._pipelines = {}
        self._pipelines["a"] = KPipeline(lang_code="a", device="cuda")
        print("Kokoro TTS engine loaded successfully.")

    def _get_pipeline(self, lang_code: str):
        """Lazy-load pipeline for the given language code."""
        if lang_code not in self._pipelines:
            from kokoro import KPipeline

            print(f"Loading Kokoro pipeline for lang_code='{lang_code}'...")
            self._pipelines[lang_code] = KPipeline(
                lang_code=lang_code, device="cuda"
            )
        return self._pipelines[lang_code]

    def _resolve_voice(self, voice: str):
        """Resolve a voice specification to a voice tensor or string and lang code.

        For single voices, returns the voice name string and its lang code
        (lets the pipeline handle native voice loading).

        For blended voices, parses the spec, loads tensors, computes the
        weighted sum, and returns the blended tensor with the shared lang code.

        Args:
            voice: Voice specification string (e.g., "af_heart" or "af_heart:70,af_bella:30").

        Returns:
            Tuple of (voice_or_tensor, lang_code) where voice_or_tensor is either
            a string (single voice) or a torch.FloatTensor (blended voice).
        """
        parts = parse_voice_spec(voice)

        if len(parts) == 1 and "," not in voice:
            # Single voice -- let pipeline handle natively
            name = parts[0][0]
            lang_code = LANG_MAP.get(name[0], "a") if name else "a"
            return name, lang_code

        # Multi-voice blend (or single voice with explicit weight syntax containing comma)
        first_name = parts[0][0]
        lang_code = LANG_MAP.get(first_name[0], "a") if first_name else "a"
        pipeline = self._get_pipeline(lang_code)
        blended_tensor = blend_voices(pipeline, parts)
        return blended_tensor, lang_code

    def generate(
        self, text: str, voice: str = "af_heart", speed: float = 1.0, **kwargs
    ) -> tuple[bytes, int]:
        """Generate speech audio from text with optional voice blending.

        Args:
            text: Text to synthesize.
            voice: Voice specification -- single voice name or blend spec.
            speed: Speech speed multiplier.

        Returns:
            Tuple of (wav_bytes, sample_rate).
        """
        voice_or_tensor, lang_code = self._resolve_voice(voice)
        pipeline = self._get_pipeline(lang_code)

        chunks = []
        for _, _, audio in pipeline(text, voice=voice_or_tensor, speed=speed):
            chunks.append(audio)

        if not chunks:
            return b"", 24000

        full_audio = np.concatenate(chunks)
        buf = io.BytesIO()
        sf.write(buf, full_audio, 24000, format="WAV")
        return buf.getvalue(), 24000

    def list_voices(self) -> list[dict]:
        """Return available voices as a list of dicts with 'id' and 'name'."""
        return [
            {"id": vid, "name": vname} for vid, vname in KOKORO_VOICES.items()
        ]
