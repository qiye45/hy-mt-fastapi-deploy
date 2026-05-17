#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

LLAMA_CPP_DIR="${LLAMA_CPP_DIR:-./vendor/llama.cpp}"
LLAMA_CPP_REPO="${LLAMA_CPP_REPO:-https://github.com/ggml-org/llama.cpp.git}"
LLAMA_CPP_PR_BRANCH="${LLAMA_CPP_PR_BRANCH:-pr-22836-stq_0}"
LLAMA_CPP_PR_REF="${LLAMA_CPP_PR_REF:-pull/22836/head:${LLAMA_CPP_PR_BRANCH}}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

install_apt_deps() {
  if command -v apt-get >/dev/null 2>&1; then
    local sudo_cmd=""
    if [[ "${EUID}" -ne 0 ]]; then
      sudo_cmd="sudo"
    fi
    ${sudo_cmd} apt-get update
    ${sudo_cmd} apt-get install -y \
      build-essential \
      ca-certificates \
      cmake \
      curl \
      git \
      python3 \
      python3-pip \
      python3-venv
  else
    echo "apt-get not found. Install git, cmake, build tools, curl, python3, pip and venv manually." >&2
  fi
}

clone_or_update_llama_cpp() {
  mkdir -p "$(dirname "${LLAMA_CPP_DIR}")"
  if [[ ! -d "${LLAMA_CPP_DIR}/.git" ]]; then
    git clone "${LLAMA_CPP_REPO}" "${LLAMA_CPP_DIR}"
  fi

  git -C "${LLAMA_CPP_DIR}" fetch origin "${LLAMA_CPP_PR_REF}"
  git -C "${LLAMA_CPP_DIR}" checkout "${LLAMA_CPP_PR_BRANCH}"
}

build_llama_cpp() {
  cmake -S "${LLAMA_CPP_DIR}" -B "${LLAMA_CPP_DIR}/build" -DCMAKE_BUILD_TYPE=Release
  cmake --build "${LLAMA_CPP_DIR}/build" --config Release -j"$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || echo 4)"
}

setup_python() {
  "${PYTHON_BIN}" -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
}

main() {
  install_apt_deps
  clone_or_update_llama_cpp
  build_llama_cpp
  setup_python
  ./scripts/download_model.sh

  cat <<'MSG'

Install complete.

Start the service:
  source .venv/bin/activate
  ./scripts/start.sh

Test it:
  ./examples/translate.sh
MSG
}

main "$@"
