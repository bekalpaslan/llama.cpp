"""
RunPod Serverless handler for speech-to-text transcription.

Stub implementation -- will be replaced in GREEN phase.
"""

import os

import torch

from transcribe import transcribe_audio
from format_output import segments_to_srt, segments_to_vtt, segments_to_text
from audio_utils import resolve_audio_input, cleanup_audio

# Module-level variables for diarization
diarize_pipeline = None

try:
    import whisperx
except ImportError:
    whisperx = None


def handler(job):
    """Process a transcription job. Stub -- not implemented."""
    raise NotImplementedError("Handler not implemented yet")
