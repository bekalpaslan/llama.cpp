"""
Audio input/output utilities for RunPod audio workers.

Handles:
- Downloading audio from URLs (with SSRF protection)
- Decoding base64-encoded audio
- Encoding NumPy audio arrays to base64 for output
- Cleanup of temporary audio files
"""

import base64
import ipaddress
import os
import socket
import tempfile
from io import BytesIO
from urllib.parse import urlparse

import numpy as np
import requests
import soundfile as sf

# Allowed audio file extensions
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm", ".mp4"}

# Content-type to extension mapping
CONTENT_TYPE_MAP = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/m4a": ".m4a",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
    "audio/x-flac": ".flac",
    "audio/webm": ".webm",
}


def _validate_url(url: str) -> None:
    """
    Validate a URL for safety (SSRF prevention).

    Checks:
    - Scheme must be http or https
    - Hostname must be resolvable
    - Resolved IP must not be private, loopback, or link-local

    Raises:
        ValueError: If the URL is invalid or resolves to a restricted IP.
    """
    parsed = urlparse(url)

    # Check scheme
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Unsupported URL scheme '{parsed.scheme}'. "
            "Only http and https are allowed."
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must include a hostname.")

    # Resolve hostname to IP
    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or 443)
    except socket.gaierror as e:
        raise ValueError(f"Cannot resolve hostname '{hostname}': {e}")

    if not addr_info:
        raise ValueError(f"No addresses found for hostname '{hostname}'.")

    # Check the first resolved IP
    ip_str = addr_info[0][4][0]
    ip = ipaddress.ip_address(ip_str)

    if ip.is_private:
        raise ValueError(
            f"URL resolves to private/internal IP address ({ip_str}). "
            "Access to internal networks is not allowed."
        )

    if ip.is_loopback:
        raise ValueError(
            f"URL resolves to loopback address ({ip_str}). "
            "Access to localhost is not allowed."
        )

    if ip.is_link_local:
        raise ValueError(
            f"URL resolves to link-local address ({ip_str}). "
            "Access to link-local addresses is not allowed."
        )


def _detect_extension(url: str, content_type: str = "") -> str:
    """
    Detect audio file extension from URL path or content-type header.

    Args:
        url: The source URL.
        content_type: The Content-Type header value.

    Returns:
        File extension string (e.g., ".wav", ".mp3").
    """
    # Try URL path first
    parsed = urlparse(url)
    _, ext = os.path.splitext(parsed.path)
    ext = ext.lower()
    if ext in ALLOWED_EXTENSIONS:
        return ext

    # Fall back to content-type mapping
    ct = content_type.lower().split(";")[0].strip()
    if ct in CONTENT_TYPE_MAP:
        return CONTENT_TYPE_MAP[ct]

    # Default
    return ".wav"


def resolve_audio_input(job_input: dict) -> str:
    """
    Resolve audio input to a local temp file path.

    Accepts job_input with either:
    - {"audio_url": "https://..."} -- downloads the file
    - {"audio_base64": "UklGR..."} -- decodes base64 data

    Args:
        job_input: Dictionary with audio_url or audio_base64 key.

    Returns:
        Path to a temporary file containing the audio data.
        Caller must clean up via cleanup_audio().

    Raises:
        ValueError: If input is missing, URL is invalid, or SSRF detected.
    """
    if "audio_url" in job_input:
        url = job_input["audio_url"]

        # Validate URL for safety
        _validate_url(url)

        # Download with streaming
        response = requests.get(url, timeout=120, stream=True)
        response.raise_for_status()

        # Detect file extension
        content_type = response.headers.get("content-type", "")
        ext = _detect_extension(url, content_type)

        # Write to temp file
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        try:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    tmp.write(chunk)
            tmp.flush()
        finally:
            tmp.close()

        return tmp.name

    elif "audio_base64" in job_input:
        audio_data = base64.b64decode(job_input["audio_base64"])

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        try:
            tmp.write(audio_data)
            tmp.flush()
        finally:
            tmp.close()

        return tmp.name

    else:
        raise ValueError("Provide 'audio_url' or 'audio_base64' in the input.")


def cleanup_audio(path: str) -> None:
    """
    Remove a temporary audio file after processing.

    Silent on errors (file already deleted, permission issues, etc.).

    Args:
        path: Path to the temporary audio file.
    """
    try:
        os.unlink(path)
    except OSError:
        pass


def encode_audio_output(
    audio_array: np.ndarray,
    sample_rate: int,
    format: str = "wav",
) -> dict:
    """
    Encode a NumPy audio array to a base64 string with metadata.

    Args:
        audio_array: NumPy array of audio samples.
        sample_rate: Sample rate in Hz.
        format: Audio format (e.g., "wav", "flac").

    Returns:
        Dictionary with:
        - audio_base64: Base64-encoded audio data
        - format: Audio format string
        - sample_rate: Sample rate in Hz
        - duration_seconds: Duration of the audio in seconds
    """
    buf = BytesIO()
    sf.write(buf, audio_array, sample_rate, format=format)
    buf.seek(0)

    audio_b64 = base64.b64encode(buf.read()).decode("utf-8")
    duration = len(audio_array) / sample_rate

    return {
        "audio_base64": audio_b64,
        "format": format,
        "sample_rate": sample_rate,
        "duration_seconds": duration,
    }
