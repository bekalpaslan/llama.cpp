"""Voice blending module for Kokoro TTS.

Provides weighted voice mixing by parsing voice specifications,
validating blend requests, and computing weighted-sum voice tensors.

Usage:
    from voice_blend import parse_voice_spec, blend_voices, validate_blend_request

    parts = parse_voice_spec("af_heart:70,af_bella:30")
    # [("af_heart", 0.7), ("af_bella", 0.3)]

    error = validate_blend_request("af_heart:70,af_bella:30", KOKORO_VOICES, "kokoro")
    # None (valid)

    blended_tensor = blend_voices(pipeline, parts)
    # torch.FloatTensor -- weighted sum of voice tensors
"""

MAX_BLEND_VOICES = 5


def parse_voice_spec(voice_spec: str) -> list[tuple[str, float]]:
    """Parse a voice specification string into a list of (name, weight) tuples.

    Supported formats:
        "af_heart"                      -> [("af_heart", 1.0)]
        "af_heart:100"                  -> [("af_heart", 1.0)]
        "af_heart,af_bella"             -> [("af_heart", 0.5), ("af_bella", 0.5)]
        "af_heart:70,af_bella:30"       -> [("af_heart", 0.7), ("af_bella", 0.3)]
        "af_heart:2,af_bella:1,af_sarah:1" -> [("af_heart", 0.5), ("af_bella", 0.25), ("af_sarah", 0.25)]

    Weights are normalized to sum to 1.0.

    Args:
        voice_spec: Voice specification string.

    Returns:
        List of (voice_name, normalized_weight) tuples.

    Raises:
        ValueError: If the spec is empty, has invalid weights, or exceeds MAX_BLEND_VOICES.
    """
    if not voice_spec or not voice_spec.strip():
        raise ValueError("Voice specification cannot be empty.")

    parts = voice_spec.split(",")

    if len(parts) > MAX_BLEND_VOICES:
        raise ValueError(
            f"Too many voices in blend: {len(parts)}. "
            f"Maximum is {MAX_BLEND_VOICES}."
        )

    voices = []
    weights = []

    for part in parts:
        part = part.strip()
        if not part:
            raise ValueError("Voice specification contains an empty entry.")

        if ":" in part:
            name, weight_str = part.rsplit(":", 1)
            name = name.strip()
            weight_str = weight_str.strip()

            if not name:
                raise ValueError("Voice name cannot be empty.")

            try:
                weight = float(weight_str)
            except ValueError:
                raise ValueError(
                    f"Weight for voice '{name}' must be numeric, got '{weight_str}'."
                )

            if weight <= 0:
                raise ValueError(
                    f"Weight for voice '{name}' must be positive, got {weight}."
                )

            voices.append(name)
            weights.append(weight)
        else:
            voices.append(part)
            weights.append(1.0)

    # Normalize weights to sum to 1.0
    total = sum(weights)
    weights = [w / total for w in weights]

    return list(zip(voices, weights))


def validate_blend_request(
    voice: str, known_voices: dict, engine: str
) -> str | None:
    """Validate a voice blend request before processing.

    Returns None if the request is valid, or an error message string if invalid.

    Args:
        voice: Voice specification string from the API request.
        known_voices: Dict of known voice IDs (keys) to display names (values).
        engine: TTS engine name (e.g., "kokoro", "dia").

    Returns:
        None if valid, error message string if invalid.
    """
    # Single voice without blend syntax -- no validation needed
    if "," not in voice:
        return None

    # Voice blending only supported for Kokoro
    if engine != "kokoro":
        return (
            f"Voice blending is only supported for the Kokoro engine, "
            f"not '{engine}'."
        )

    # Parse the spec (may raise ValueError for format issues)
    try:
        parts = parse_voice_spec(voice)
    except ValueError as e:
        return str(e)

    # Check all voice names are known
    for name, _ in parts:
        if name not in known_voices:
            return (
                f"Unknown voice: '{name}'. "
                f"Use list_voices to see available voices."
            )

    # Check all voices share the same language prefix
    prefixes = {name[0] for name, _ in parts}
    if len(prefixes) > 1:
        voice_names = [name for name, _ in parts]
        return (
            f"Cross-language voice blending is not supported. "
            f"All voices must share the same language prefix. "
            f"Got: {', '.join(voice_names)}"
        )

    return None


def blend_voices(pipeline, voice_parts: list[tuple[str, float]]):
    """Blend multiple voice tensors using weighted sum.

    Args:
        pipeline: KPipeline instance with a load_voice(name) method.
        voice_parts: List of (voice_name, weight) tuples from parse_voice_spec().

    Returns:
        torch.FloatTensor: Blended voice tensor (or single voice tensor).
    """
    import torch  # Lazy import -- keeps module importable without torch for validation-only use

    if len(voice_parts) == 1:
        name, _ = voice_parts[0]
        return pipeline.load_voice(name)

    # Load all voice tensors
    tensors = [pipeline.load_voice(name) for name, _ in voice_parts]
    weights = [weight for _, weight in voice_parts]

    # Compute weighted sum
    blended = sum(t * w for t, w in zip(tensors, weights))
    return blended
