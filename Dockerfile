# =============================================================================
# Stage 1: Build llama.cpp with CUDA support
# =============================================================================
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04 AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake git build-essential \
    && rm -rf /var/lib/apt/lists/*

ARG LLAMA_CPP_VERSION=master
RUN git clone --depth 1 --branch ${LLAMA_CPP_VERSION} \
    https://github.com/ggml-org/llama.cpp /llama.cpp

WORKDIR /llama.cpp

# Build for all RunPod GPU architectures:
#   75 = T4        80 = A100       86 = RTX 3090 / A6000 / A40
#   89 = RTX 4090 / L4 / L40      90 = H100
RUN cmake -B build \
    -DGGML_CUDA=ON \
    -DGGML_NATIVE=OFF \
    -DCMAKE_CUDA_ARCHITECTURES="75;80;86;89;90" \
    -DBUILD_SHARED_LIBS=OFF \
    && cmake --build build --config Release -j$(nproc) --target llama-server

# =============================================================================
# Stage 2: Runtime image
# =============================================================================
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

# Copy cuBLAS from builder (runtime image only has libcudart)
COPY --from=builder /usr/local/cuda/lib64/libcublas*.so* /usr/local/cuda/lib64/
COPY --from=builder /usr/local/cuda/lib64/libcublasLt*.so* /usr/local/cuda/lib64/
RUN ldconfig

# Install Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /usr/bin/python

# Copy llama-server binary
COPY --from=builder /llama.cpp/build/bin/llama-server /usr/local/bin/llama-server
RUN chmod +x /usr/local/bin/llama-server

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY handler.py .
COPY download_model.py .

ENV PYTHONUNBUFFERED=1

# Default environment variables (override via RunPod template config)
ENV HF_REPO_ID="" \
    HF_FILENAME="" \
    HF_TOKEN="" \
    MODEL_NAME="default" \
    N_GPU_LAYERS="99" \
    CTX_SIZE="8192" \
    N_PARALLEL="1" \
    FLASH_ATTN="on" \
    KV_CACHE_TYPE="f16" \
    EXTRA_ARGS="" \
    STARTUP_TIMEOUT="600"

CMD ["python3", "-u", "handler.py"]
