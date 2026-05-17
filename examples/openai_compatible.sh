#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000}"

curl -sS "${API_URL}/v1/chat/completions" \
  -H "Content-Type: application/json" \
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
