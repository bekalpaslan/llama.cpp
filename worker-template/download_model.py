"""
Download models from HuggingFace with network volume caching.

Checks /runpod-volume first (persistent across cold starts), then falls
back to /tmp/models. Supports single-file download via hf_hub_download
and full-repo download via snapshot_download.
"""

import os

from huggingface_hub import hf_hub_download, snapshot_download

VOLUME_PATH = "/runpod-volume/models"
LOCAL_PATH = "/tmp/models"


def download_model(
    repo_id: str,
    filename: str | None = None,
    token: str | None = None,
    allow_patterns: list[str] | None = None,
    snapshot: bool = False,
) -> str:
    """
    Download model file(s) from HuggingFace with volume caching.

    Args:
        repo_id: HuggingFace repo identifier (e.g., "org/model-name").
        filename: Specific file to download. If None and snapshot=True,
                  downloads the full repo via snapshot_download.
        token: HuggingFace API token for gated models.
        allow_patterns: File patterns to include in snapshot downloads
                        (e.g., ["*.bin", "*.json"]).
        snapshot: If True and filename is None, use snapshot_download
                  for the entire repo.

    Returns:
        Local path to the downloaded model file or directory.

    Raises:
        RuntimeError: If repo_id is empty or falsy.
    """
    if not repo_id:
        raise RuntimeError("repo_id is required")

    # Resolve token from env if not provided
    if token is None:
        token = os.environ.get("HF_TOKEN")

    # Check cached locations for single-file downloads
    if filename:
        for cache_dir in [VOLUME_PATH, LOCAL_PATH]:
            cached = os.path.join(cache_dir, filename)
            if os.path.isfile(cached):
                size_gb = os.path.getsize(cached) / (1024**3)
                print(f"Found cached model: {cached} ({size_gb:.2f} GB)")
                return cached

    # Determine download destination
    if os.path.isdir("/runpod-volume"):
        dest_dir = VOLUME_PATH
    else:
        dest_dir = LOCAL_PATH
    os.makedirs(dest_dir, exist_ok=True)

    if filename:
        # Single-file download
        print(f"Downloading {repo_id}/{filename} -> {dest_dir}")
        print("This may take a while for large models...")

        path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=dest_dir,
            token=token,
        )

        size_gb = os.path.getsize(path) / (1024**3)
        print(f"Download complete: {path} ({size_gb:.2f} GB)")
        return path

    elif snapshot:
        # Full repo snapshot download
        sub_dir = repo_id.replace("/", "--")
        snapshot_dest = os.path.join(dest_dir, sub_dir)
        os.makedirs(snapshot_dest, exist_ok=True)

        print(f"Downloading snapshot of {repo_id} -> {snapshot_dest}")
        print("This may take a while for large repos...")

        path = snapshot_download(
            repo_id=repo_id,
            local_dir=snapshot_dest,
            token=token,
            allow_patterns=allow_patterns,
        )

        print(f"Snapshot download complete: {path}")
        return path

    else:
        raise RuntimeError(
            "Either provide a filename for single-file download, "
            "or set snapshot=True for full repo download."
        )
