FROM python:3.11-slim AS builder

ARG LLAMA_CPP_REPO=https://github.com/ggml-org/llama.cpp.git
ARG LLAMA_CPP_PR_BRANCH=pr-22836-stq_0

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    cmake \
    git \
  && rm -rf /var/lib/apt/lists/*

RUN git clone "${LLAMA_CPP_REPO}" /opt/llama.cpp \
  && cd /opt/llama.cpp \
  && git fetch origin "pull/22836/head:${LLAMA_CPP_PR_BRANCH}" \
  && git checkout "${LLAMA_CPP_PR_BRANCH}" \
  && cmake -B build -DCMAKE_BUILD_TYPE=Release \
  && cmake --build build --config Release -j"$(nproc)"

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    LLAMA_CPP_DIR=/opt/llama.cpp \
    MODEL_PATH=/app/models/Hy-MT1.5-1.8B-1.25bit-GGUF/Hy-MT1.5-1.8B-1.25bit.gguf \
    LLAMA_HOST=127.0.0.1 \
    LLAMA_PORT=8080 \
    API_HOST=0.0.0.0 \
    API_PORT=4547 \
    CTX_SIZE=4096 \
    N_GPU_LAYERS=0 \
    THREADS=0

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libgomp1 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /opt/llama.cpp /opt/llama.cpp
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY examples ./examples

RUN chmod +x ./scripts/*.sh ./examples/*.sh

EXPOSE 4547

CMD ["./scripts/start.sh"]
