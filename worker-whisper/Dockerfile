FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

# System deps: Python, ffmpeg (audio format conversion), libsndfile (soundfile library)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /usr/bin/python

WORKDIR /app

# Install PyTorch with CUDA 12.4 support (no cache to save ~2.5GB)
RUN pip3 install --no-cache-dir \
    torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# CRITICAL: Install faster-whisper BEFORE whisperx to avoid dependency conflicts
# (see 02-RESEARCH.md Pitfall 1)
RUN pip3 install --no-cache-dir faster-whisper>=1.2.1

# Install whisperx (pulls pyannote-audio and alignment dependencies)
RUN pip3 install --no-cache-dir whisperx>=3.8.2

# Install remaining worker dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy worker code
COPY handler.py transcribe.py format_output.py download_model.py audio_utils.py ./

ENV PYTHONUNBUFFERED=1

# Prevent VRAM fragmentation (see 02-RESEARCH.md Pitfall 5)
ENV PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# Worker-specific env vars
ENV HF_REPO_ID="" \
    HF_TOKEN="" \
    MODEL_NAME="whisper-stt" \
    MODEL_SIZE="large-v3-turbo" \
    COMPUTE_TYPE="int8"

CMD ["python3", "-u", "handler.py"]
