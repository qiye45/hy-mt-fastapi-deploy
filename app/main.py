from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field


LLAMA_SERVER_URL = os.getenv("LLAMA_SERVER_URL", "http://127.0.0.1:8080").rstrip("/")
MODEL_NAME = os.getenv("MODEL_NAME", "AngelSlim/Hy-MT1.5-1.8B-1.25bit-GGUF")
DEFAULT_MAX_TOKENS = int(os.getenv("DEFAULT_MAX_TOKENS", "512"))
DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.0"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "600"))

app = FastAPI(
    title="Hy-MT1.5 FastAPI Service",
    description="FastAPI wrapper around llama.cpp server for AngelSlim Hy-MT1.5 1.25bit GGUF.",
    version="0.1.0",
)


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text segment to translate.")
    target_language: str = Field("Chinese", description="Target language name, for example Chinese or English.")
    source_language: str | None = Field(None, description="Optional source language name.")
    max_tokens: int = Field(DEFAULT_MAX_TOKENS, ge=1, le=8192)
    temperature: float = Field(DEFAULT_TEMPERATURE, ge=0.0, le=2.0)


class TranslateResponse(BaseModel):
    translation: str
    model: str
    upstream: dict[str, Any]


def build_translation_prompt(payload: TranslateRequest) -> str:
    source = f" from {payload.source_language}" if payload.source_language else ""
    return (
        f"Translate the following segment{source} into {payload.target_language}, "
        "without additional explanation.\n\n"
        f"{payload.text}"
    )


async def post_llama(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{LLAMA_SERVER_URL}{path}"
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"llama-server is not reachable at {LLAMA_SERVER_URL}: {exc}",
            ) from exc
    return response.json()


def extract_message_content(response: dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=502, detail=f"Unexpected llama-server response: {response}") from exc
    if not isinstance(content, str):
        raise HTTPException(status_code=502, detail=f"Unexpected message content: {content!r}")
    return content.strip()


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "hy-mt-fastapi",
        "model": MODEL_NAME,
        "llama_server_url": LLAMA_SERVER_URL,
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    upstream: dict[str, Any] = {"ok": False}
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            response = await client.get(f"{LLAMA_SERVER_URL}/health")
            upstream = {
                "ok": response.status_code < 500,
                "status_code": response.status_code,
                "body": response.text[:500],
            }
        except httpx.HTTPError as exc:
            upstream = {"ok": False, "error": str(exc)}
    return {"ok": True, "llama_server": upstream}


@app.post("/translate", response_model=TranslateResponse)
async def translate(payload: TranslateRequest) -> TranslateResponse:
    prompt = build_translation_prompt(payload)
    upstream_payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": payload.temperature,
        "max_tokens": payload.max_tokens,
        "stream": False,
    }
    upstream = await post_llama("/v1/chat/completions", upstream_payload)
    return TranslateResponse(
        translation=extract_message_content(upstream),
        model=MODEL_NAME,
        upstream=upstream,
    )


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> dict[str, Any]:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object.")
    payload.setdefault("model", MODEL_NAME)
    return await post_llama("/v1/chat/completions", payload)
