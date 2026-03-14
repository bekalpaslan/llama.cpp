"""Tests for voice cloning module (VC-01, VC-02, VC-04)."""

import base64
import io
import shutil
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf
import torch


class TestLoadModel:
    """Tests for load_model() function."""

    @patch("voice_clone.importlib.import_module")
    def test_load_model_turbo(self, mock_import):
        """load_model('turbo') imports ChatterboxTurboTTS and calls from_pretrained."""
        from voice_clone import load_model

        mock_module = MagicMock()
        mock_model_instance = MagicMock()
        mock_module.ChatterboxTurboTTS.from_pretrained.return_value = mock_model_instance
        mock_import.return_value = mock_module

        model = load_model("turbo", device="cpu")

        mock_import.assert_called_with("chatterbox.tts_turbo")
        mock_module.ChatterboxTurboTTS.from_pretrained.assert_called_once_with(
            device="cpu"
        )
        assert model is mock_model_instance

    @patch("voice_clone.importlib.import_module")
    def test_load_model_multilingual(self, mock_import):
        """load_model('multilingual') imports ChatterboxMultilingualTTS and calls from_pretrained."""
        from voice_clone import load_model

        mock_module = MagicMock()
        mock_model_instance = MagicMock()
        mock_module.ChatterboxMultilingualTTS.from_pretrained.return_value = (
            mock_model_instance
        )
        mock_import.return_value = mock_module

        model = load_model("multilingual", device="cpu")

        mock_import.assert_called_with("chatterbox.mtl_tts")
        mock_module.ChatterboxMultilingualTTS.from_pretrained.assert_called_once_with(
            device="cpu"
        )
        assert model is mock_model_instance

    @patch("voice_clone.importlib.import_module")
    def test_load_model_original(self, mock_import):
        """load_model('original') imports ChatterboxTTS and calls from_pretrained."""
        from voice_clone import load_model

        mock_module = MagicMock()
        mock_model_instance = MagicMock()
        mock_module.ChatterboxTTS.from_pretrained.return_value = mock_model_instance
        mock_import.return_value = mock_module

        model = load_model("original", device="cpu")

        mock_import.assert_called_with("chatterbox.tts")
        mock_module.ChatterboxTTS.from_pretrained.assert_called_once_with(device="cpu")
        assert model is mock_model_instance


class TestCloneVoice:
    """Tests for clone_voice() function."""

    def test_clone_voice_basic(self, mock_chatterbox_model, tmp_path):
        """clone_voice() calls model.generate with text and audio_prompt_path."""
        from voice_clone import clone_voice

        ref_path = str(tmp_path / "ref.wav")
        # Create a dummy file for the path
        open(ref_path, "w").close()

        wav, sr = clone_voice(mock_chatterbox_model, "Hello world", ref_path)

        mock_chatterbox_model.generate.assert_called_once()
        call_args = mock_chatterbox_model.generate.call_args
        assert call_args[0][0] == "Hello world"
        assert call_args[1]["audio_prompt_path"] == ref_path
        assert sr == 24000
        assert isinstance(wav, torch.Tensor)

    def test_clone_voice_multilingual_passes_language_id(
        self, mock_chatterbox_model, tmp_path
    ):
        """When variant is multilingual, language_id is passed to generate()."""
        from voice_clone import clone_voice

        ref_path = str(tmp_path / "ref.wav")
        open(ref_path, "w").close()

        clone_voice(
            mock_chatterbox_model,
            "Bonjour le monde",
            ref_path,
            language_id="fr",
        )

        call_kwargs = mock_chatterbox_model.generate.call_args[1]
        assert call_kwargs["language_id"] == "fr"

    def test_clone_voice_passes_exaggeration_and_cfg_weight(
        self, mock_chatterbox_model, tmp_path
    ):
        """exaggeration and cfg_weight kwargs forwarded to generate()."""
        from voice_clone import clone_voice

        ref_path = str(tmp_path / "ref.wav")
        open(ref_path, "w").close()

        clone_voice(
            mock_chatterbox_model,
            "Test text",
            ref_path,
            exaggeration=0.8,
            cfg_weight=0.3,
        )

        call_kwargs = mock_chatterbox_model.generate.call_args[1]
        assert call_kwargs["exaggeration"] == 0.8
        assert call_kwargs["cfg_weight"] == 0.3


class TestEncodeOutput:
    """Tests for encode_output() function."""

    def test_encode_output_wav_48khz(self):
        """encode_output() resamples 24kHz tensor to 48kHz, returns (base64_string, 'wav')."""
        from voice_clone import encode_output

        # Small tensor: 0.1s at 24kHz = 2400 samples
        wav = torch.randn(1, 2400)
        b64_str, fmt = encode_output(wav, native_sr=24000, output_format="wav", target_sr=48000)

        assert fmt == "wav"
        assert isinstance(b64_str, str)

        # Decode and verify it's valid WAV at 48kHz
        audio_bytes = base64.b64decode(b64_str)
        buf = io.BytesIO(audio_bytes)
        data, sr = sf.read(buf)
        assert sr == 48000
        # After 2x upsample, should have ~4800 samples
        assert len(data) > 2400

    @pytest.mark.skipif(
        not shutil.which("ffmpeg"), reason="ffmpeg not available"
    )
    def test_encode_output_mp3(self):
        """encode_output() produces MP3 via ffmpeg subprocess, returns (base64_string, 'mp3')."""
        from voice_clone import encode_output

        wav = torch.randn(1, 2400)
        b64_str, fmt = encode_output(wav, native_sr=24000, output_format="mp3", target_sr=48000)

        assert fmt == "mp3"
        assert isinstance(b64_str, str)

        # Verify base64 decodes to non-empty bytes
        audio_bytes = base64.b64decode(b64_str)
        assert len(audio_bytes) > 0

    def test_encode_output_no_resample_when_same(self):
        """When target_sr == native_sr, no resample call."""
        from voice_clone import encode_output

        wav = torch.randn(1, 2400)
        with patch("voice_clone.F.resample") as mock_resample:
            b64_str, fmt = encode_output(
                wav, native_sr=24000, output_format="wav", target_sr=24000
            )

            mock_resample.assert_not_called()

        assert fmt == "wav"
        # Verify WAV at 24kHz
        audio_bytes = base64.b64decode(b64_str)
        buf = io.BytesIO(audio_bytes)
        data, sr = sf.read(buf)
        assert sr == 24000
