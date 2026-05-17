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

MODEL_REPO="${MODEL_REPO:-AngelSlim/Hy-MT1.5-1.8B-1.25bit-GGUF}"
MODEL_FILE="${MODEL_FILE:-Hy-MT1.5-1.8B-1.25bit.gguf}"
MODEL_PATH="${MODEL_PATH:-}"

if [[ -n "${MODEL_PATH}" ]]; then
  MODEL_DIR="${MODEL_DIR:-$(dirname "${MODEL_PATH}")}"
else
  MODEL_DIR="${MODEL_DIR:-./models/Hy-MT1.5-1.8B-1.25bit-GGUF}"
  MODEL_PATH="${MODEL_DIR}/${MODEL_FILE}"
fi

if [[ -f "${MODEL_PATH}" ]]; then
  echo "Model already exists: ${MODEL_PATH}"
  exit 0
fi

mkdir -p "${MODEL_DIR}"

echo "Downloading ${MODEL_REPO}/${MODEL_FILE} to ${MODEL_DIR}"
huggingface-cli download "${MODEL_REPO}" \
  "${MODEL_FILE}" \
  --local-dir "${MODEL_DIR}" \
  --local-dir-use-symlinks False

echo "Model ready: ${MODEL_PATH}"
