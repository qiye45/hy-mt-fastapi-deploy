#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

MODEL_PATH="${MODEL_PATH:-./models/Hy-MT1.5-1.8B-1.25bit-GGUF/Hy-MT1.5-1.8B-1.25bit.gguf}"
LLAMA_CPP_DIR="${LLAMA_CPP_DIR:-./vendor/llama.cpp}"
LLAMA_BIN="${LLAMA_BIN:-${LLAMA_CPP_DIR}/build/bin/llama-server}"
LLAMA_HOST="${LLAMA_HOST:-127.0.0.1}"
LLAMA_PORT="${LLAMA_PORT:-8080}"
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-4547}"
CTX_SIZE="${CTX_SIZE:-4096}"
N_GPU_LAYERS="${N_GPU_LAYERS:-0}"
THREADS="${THREADS:-0}"
LLAMA_EXTRA_ARGS="${LLAMA_EXTRA_ARGS:-}"

if [[ ! -x "${LLAMA_BIN}" ]]; then
  echo "llama-server not found: ${LLAMA_BIN}" >&2
  echo "Run ./scripts/install_linux.sh first, or use Docker." >&2
  exit 1
fi

if [[ ! -f "${MODEL_PATH}" ]]; then
  echo "Model file not found: ${MODEL_PATH}"
  ./scripts/download_model.sh
fi

if [[ "${THREADS}" == "0" ]]; then
  THREADS="$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || echo 4)"
fi

export LLAMA_SERVER_URL="${LLAMA_SERVER_URL:-http://127.0.0.1:${LLAMA_PORT}}"

cleanup() {
  if [[ -n "${LLAMA_PID:-}" ]] && kill -0 "${LLAMA_PID}" 2>/dev/null; then
    kill "${LLAMA_PID}"
    wait "${LLAMA_PID}" || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting llama-server on ${LLAMA_HOST}:${LLAMA_PORT}"
"${LLAMA_BIN}" \
  -m "${MODEL_PATH}" \
  --host "${LLAMA_HOST}" \
  --port "${LLAMA_PORT}" \
  --ctx-size "${CTX_SIZE}" \
  --n-gpu-layers "${N_GPU_LAYERS}" \
  --threads "${THREADS}" \
  --jinja \
  ${LLAMA_EXTRA_ARGS} &
LLAMA_PID="$!"

echo "Waiting for llama-server at ${LLAMA_SERVER_URL}"
for _ in $(seq 1 120); do
  if curl -fsS "${LLAMA_SERVER_URL}/health" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "${LLAMA_PID}" 2>/dev/null; then
    echo "llama-server exited before becoming healthy." >&2
    wait "${LLAMA_PID}"
  fi
  sleep 1
done

if ! curl -fsS "${LLAMA_SERVER_URL}/health" >/dev/null 2>&1; then
  echo "llama-server did not become healthy in time." >&2
  exit 1
fi

echo "Starting FastAPI on ${API_HOST}:${API_PORT}"
exec uvicorn app.main:app --host "${API_HOST}" --port "${API_PORT}"
