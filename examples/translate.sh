#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:4547}"

curl -sS "${API_URL}/translate" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, how are you today?",
    "target_language": "Chinese",
    "max_tokens": 128
  }' | python -m json.tool
