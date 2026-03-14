"""
Download GGUF models from HuggingFace with network volume caching.

Checks /runpod-volume first (persistent across cold starts), then falls
back to /tmp/models. If HF_FILENAME is not provided, auto-detects the
best GGUF file in the repo based on the preferred quantization.
"""

import os
import sys

from huggingface_hub import hf_hub_download, list_repo_files

VOLUME_PATH = "/runpod-volume/models"
LOCAL_PATH = "/tmp/models"

QUANT_PREFERENCE = [
    "Q4_K_M",
    "Q4_K_S",
    "Q5_K_M",
    "Q5_K_S",
    "Q3_K_M",
    "Q6_K",
    "Q8_0",
    "Q4_0",
]


def find_gguf_file(repo_id: str, preferred_quant: str = "Q4_K_M",
                   token: str | None = None) -> str | None:
    """Find the best GGUF file in a HuggingFace repo."""
    try:
        files = list_repo_files(repo_id, token=token)
    except Exception as e:
        print(f"Warning: could not list files in {repo_id}: {e}")
        return None

    gguf_files = [f for f in files if f.endswith(".gguf")]
    if not gguf_files:
        return None

    # Prefer single-file models (skip split shards like *-00001-of-00003.gguf)
    single_files = [f for f in gguf_files if "-of-" not in f]
    search_list = single_files if single_files else gguf_files

    # Try preferred quant first
    for f in search_list:
        if preferred_quant in f:
            return f

    # Try other quants in preference order
    for quant in QUANT_PREFERENCE:
        for f in search_list:
            if quant in f:
                return f

    # Fall back to first available
    return search_list[0]


def download_model(repo_id: str, filename: str | None = None,
                   token: str | None = None) -> str:
    """
    Download a GGUF model file from HuggingFace.

    Returns the local path to the downloaded model file.
    """
    # Auto-detect filename if not provided
    if not filename:
        print(f"No filename specified, scanning {repo_id} for GGUF files...")
        filename = find_gguf_file(repo_id, token=token)
        if not filename:
            print(f"ERROR: No GGUF files found in {repo_id}", file=sys.stderr)
            sys.exit(1)
        print(f"Auto-selected: {filename}")

    # Check cached locations
    for cache_dir in [VOLUME_PATH, LOCAL_PATH]:
        cached = os.path.join(cache_dir, filename)
        if os.path.isfile(cached):
            size_gb = os.path.getsize(cached) / (1024 ** 3)
            print(f"Found cached model: {cached} ({size_gb:.2f} GB)")
            return cached

    # Determine download destination
    if os.path.isdir("/runpod-volume"):
        dest_dir = VOLUME_PATH
    else:
        dest_dir = LOCAL_PATH
    os.makedirs(dest_dir, exist_ok=True)

    print(f"Downloading {repo_id}/{filename} → {dest_dir}")
    print("This may take a while for large models...")

    path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=dest_dir,
        token=token,
    )

    size_gb = os.path.getsize(path) / (1024 ** 3)
    print(f"Download complete: {path} ({size_gb:.2f} GB)")
    return path
