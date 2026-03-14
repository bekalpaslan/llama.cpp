"""Tests for the generalized download_model module."""

import os

import pytest

from download_model import download_model, VOLUME_PATH, LOCAL_PATH


class TestDownloadModelValidation:
    """Tests for input validation."""

    def test_missing_repo_id(self, mock_hf_hub):
        """download_model('') raises RuntimeError."""
        with pytest.raises(RuntimeError, match="repo_id is required"):
            download_model("")

    def test_none_repo_id(self, mock_hf_hub):
        """download_model(None) raises RuntimeError."""
        with pytest.raises(RuntimeError, match="repo_id is required"):
            download_model(None)


class TestCachedModels:
    """Tests for cache hit paths."""

    def test_cached_model_volume(self, mock_hf_hub, monkeypatch):
        """When file exists at VOLUME_PATH, returns that path without downloading."""
        cached_path = os.path.join(VOLUME_PATH, "model.bin")

        monkeypatch.setattr(os.path, "isfile", lambda p: p == cached_path)
        monkeypatch.setattr(os.path, "getsize", lambda p: 4 * 1024**3)  # 4 GB

        result = download_model("org/repo", filename="model.bin")

        assert result == cached_path
        mock_hf_hub.hf_hub_download.assert_not_called()
        mock_hf_hub.snapshot_download.assert_not_called()

    def test_cached_model_local(self, mock_hf_hub, monkeypatch):
        """When file exists at LOCAL_PATH (no volume cache), returns that path."""
        cached_path = os.path.join(LOCAL_PATH, "model.bin")

        def fake_isfile(p):
            if p == os.path.join(VOLUME_PATH, "model.bin"):
                return False
            return p == cached_path

        monkeypatch.setattr(os.path, "isfile", fake_isfile)
        monkeypatch.setattr(os.path, "getsize", lambda p: 2 * 1024**3)  # 2 GB

        result = download_model("org/repo", filename="model.bin")

        assert result == cached_path
        mock_hf_hub.hf_hub_download.assert_not_called()


class TestDownloadPaths:
    """Tests for download destination selection and download calls."""

    def test_single_file_download(self, mock_hf_hub, monkeypatch):
        """When filename is provided, calls hf_hub_download with correct args."""
        monkeypatch.setattr(os.path, "isfile", lambda p: False)
        monkeypatch.setattr(os.path, "isdir", lambda p: p == "/runpod-volume")
        monkeypatch.setattr(os, "makedirs", lambda p, exist_ok=False: None)
        monkeypatch.setattr(os.path, "getsize", lambda p: 4 * 1024**3)

        expected_path = os.path.join(VOLUME_PATH, "model.bin")
        mock_hf_hub.hf_hub_download.return_value = expected_path

        result = download_model("org/repo", filename="model.bin", token="hf_test123")

        mock_hf_hub.hf_hub_download.assert_called_once_with(
            repo_id="org/repo",
            filename="model.bin",
            local_dir=VOLUME_PATH,
            token="hf_test123",
        )
        assert result == expected_path

    def test_snapshot_download(self, mock_hf_hub, monkeypatch):
        """When filename=None and snapshot=True, calls snapshot_download."""
        monkeypatch.setattr(os.path, "isfile", lambda p: False)
        monkeypatch.setattr(os.path, "isdir", lambda p: p == "/runpod-volume")
        monkeypatch.setattr(os, "makedirs", lambda p, exist_ok=False: None)

        expected_path = os.path.join(VOLUME_PATH, "org--repo")
        mock_hf_hub.snapshot_download.return_value = expected_path

        result = download_model(
            "org/repo",
            snapshot=True,
            token="hf_test",
            allow_patterns=["*.bin", "*.json"],
        )

        mock_hf_hub.snapshot_download.assert_called_once_with(
            repo_id="org/repo",
            local_dir=os.path.join(VOLUME_PATH, "org--repo"),
            token="hf_test",
            allow_patterns=["*.bin", "*.json"],
        )
        assert result == expected_path

    def test_volume_preferred_over_tmp(self, mock_hf_hub, monkeypatch):
        """When /runpod-volume exists, dest_dir is VOLUME_PATH not LOCAL_PATH."""
        monkeypatch.setattr(os.path, "isfile", lambda p: False)
        monkeypatch.setattr(os.path, "isdir", lambda p: p == "/runpod-volume")
        monkeypatch.setattr(os, "makedirs", lambda p, exist_ok=False: None)
        monkeypatch.setattr(os.path, "getsize", lambda p: 1024**3)

        mock_hf_hub.hf_hub_download.return_value = "/some/path"

        download_model("org/repo", filename="model.bin")

        call_kwargs = mock_hf_hub.hf_hub_download.call_args[1]
        assert call_kwargs["local_dir"] == VOLUME_PATH

    def test_fallback_to_tmp(self, mock_hf_hub, monkeypatch):
        """When /runpod-volume does not exist, dest_dir is LOCAL_PATH."""
        monkeypatch.setattr(os.path, "isfile", lambda p: False)
        monkeypatch.setattr(os.path, "isdir", lambda p: False)
        monkeypatch.setattr(os, "makedirs", lambda p, exist_ok=False: None)
        monkeypatch.setattr(os.path, "getsize", lambda p: 1024**3)

        mock_hf_hub.hf_hub_download.return_value = "/some/path"

        download_model("org/repo", filename="model.bin")

        call_kwargs = mock_hf_hub.hf_hub_download.call_args[1]
        assert call_kwargs["local_dir"] == LOCAL_PATH
