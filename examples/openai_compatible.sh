#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:4547}"

HEADERS=(-H "Content-Type: application/json")
if [[ -n "${API_KEY:-}" ]]; then
  HEADERS+=(-H "Authorization: Bearer ${API_KEY}")
fi

curl -sS "${API_URL}/v1/chat/completions" \
  "${HEADERS[@]}" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "Translate the following segment into Chinese, without additional explanation.\n\nHello, how are you today?"
      }
    ],
    "temperature": 0,
    "max_tokens": 128,
    "stream": false
  }' | python -m json.tool
