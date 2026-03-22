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

# Install worker dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy worker code
COPY handler.py download_model.py audio_utils.py ./

ENV PYTHONUNBUFFERED=1

# Worker-specific env vars (customize per worker)
ENV HF_REPO_ID="" \
    HF_TOKEN="" \
    MODEL_NAME="default"

CMD ["python3", "-u", "handler.py"]
