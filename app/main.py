from __future__ import annotations

from json import JSONDecodeError
import os
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


LLAMA_SERVER_URL = os.getenv("LLAMA_SERVER_URL", "http://127.0.0.1:8080").rstrip("/")
MODEL_NAME = os.getenv("MODEL_NAME", "AngelSlim/Hy-MT1.5-1.8B-1.25bit-GGUF")
DEFAULT_MAX_TOKENS = int(os.getenv("DEFAULT_MAX_TOKENS", "512"))
DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.0"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "600"))


def parse_api_keys(api_keys: str | None, api_key: str | None) -> set[str]:
    values: list[str] = []
    if api_keys:
        values.extend(api_keys.split(","))
    if api_key:
        values.append(api_key)
    return {value.strip() for value in values if value.strip()}


API_KEYS = parse_api_keys(os.getenv("API_KEYS"), os.getenv("API_KEY"))

app = FastAPI(
    title="Hy-MT1.5 FastAPI Service",
    description="FastAPI wrapper around llama.cpp server for AngelSlim Hy-MT1.5 1.25bit GGUF.",
    version="0.1.0",
)


class OpenAIHTTPException(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
        error_type: str,
        code: str | None = None,
        param: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.error_type = error_type
        self.code = code
        self.param = param


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


def openai_error_payload(
    message: str,
    error_type: str,
    code: str | None = None,
    param: str | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "message": message,
            "type": error_type,
            "param": param,
            "code": code,
        }
    }


@app.exception_handler(OpenAIHTTPException)
async def openai_exception_handler(_request: Request, exc: OpenAIHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=openai_error_payload(exc.message, exc.error_type, exc.code, exc.param),
    )


async def require_openai_auth(authorization: str | None = Header(default=None)) -> None:
    if not API_KEYS:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise OpenAIHTTPException(
            status_code=401,
            message="Missing bearer token.",
            error_type="authentication_error",
            code="missing_api_key",
        )
    token = authorization.removeprefix("Bearer ").strip()
    if token not in API_KEYS:
        raise OpenAIHTTPException(
            status_code=401,
            message="Invalid bearer token.",
            error_type="authentication_error",
            code="invalid_api_key",
        )


def model_metadata() -> dict[str, Any]:
    return {
        "id": MODEL_NAME,
        "object": "model",
        "created": 0,
        "owned_by": "hy-mt-fastapi",
    }


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
            raise OpenAIHTTPException(
                status_code=exc.response.status_code,
                message=detail,
                error_type="upstream_error",
                code="llama_server_error",
            ) from exc
        except httpx.HTTPError as exc:
            raise OpenAIHTTPException(
                status_code=502,
                message=f"llama-server is not reachable at {LLAMA_SERVER_URL}: {exc}",
                error_type="upstream_error",
                code="llama_server_unreachable",
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


@app.get("/v1/models", dependencies=[Depends(require_openai_auth)])
async def list_models() -> dict[str, Any]:
    return {"object": "list", "data": [model_metadata()]}


@app.post("/v1/chat/completions", dependencies=[Depends(require_openai_auth)])
async def chat_completions(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except JSONDecodeError as exc:
        raise OpenAIHTTPException(
            status_code=400,
            message="JSON body must be a valid object.",
            error_type="invalid_request_error",
            code="invalid_json_body",
        ) from exc
    if not isinstance(payload, dict):
        raise OpenAIHTTPException(
            status_code=400,
            message="JSON body must be an object.",
            error_type="invalid_request_error",
            code="invalid_json_body",
        )
    payload.setdefault("model", MODEL_NAME)
    return await post_llama("/v1/chat/completions", payload)
