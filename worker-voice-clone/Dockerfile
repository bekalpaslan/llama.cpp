FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

# System deps: Python, ffmpeg (MP3 encoding), libsndfile (soundfile library)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /usr/bin/python

WORKDIR /app

# Install PyTorch with CUDA 12.4 support (no cache to save ~2.5GB)
RUN pip3 install --no-cache-dir \
    torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# Install remaining worker dependencies (includes chatterbox-tts)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy worker code
COPY handler.py voice_clone.py validate_reference.py download_model.py audio_utils.py ./

ENV PYTHONUNBUFFERED=1

# Prevent VRAM fragmentation (see 04-RESEARCH.md Pitfall 4)
ENV PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# Persistent model cache on RunPod network volume
ENV HF_HOME=/runpod-volume/.cache/huggingface

# Worker-specific env vars
ENV MODEL_VARIANT="multilingual" \
    MODEL_NAME="voice-clone"

CMD ["python3", "-u", "handler.py"]
