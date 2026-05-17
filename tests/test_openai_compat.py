from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app import main


class OpenAICompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(main.app)
        self.original_model_name = main.MODEL_NAME
        main.MODEL_NAME = "hy-mt-test"
        main.API_KEYS = set()

    def tearDown(self) -> None:
        main.MODEL_NAME = self.original_model_name
        main.API_KEYS = set()

    def test_models_returns_openai_compatible_single_model_list(self) -> None:
        response = self.client.get("/v1/models")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "object": "list",
                "data": [
                    {
                        "id": "hy-mt-test",
                        "object": "model",
                        "created": 0,
                        "owned_by": "hy-mt-fastapi",
                    }
                ],
            },
        )

    def test_openai_endpoints_require_bearer_token_when_api_keys_are_configured(self) -> None:
        main.API_KEYS = {"secret-token"}

        missing = self.client.get("/v1/models")
        wrong = self.client.get("/v1/models", headers={"Authorization": "Bearer wrong-token"})
        correct = self.client.get("/v1/models", headers={"Authorization": "Bearer secret-token"})

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(missing.json()["error"]["type"], "authentication_error")
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(wrong.json()["error"]["code"], "invalid_api_key")
        self.assertEqual(correct.status_code, 200)

    def test_chat_completions_injects_default_model_and_forwards_to_llama(self) -> None:
        upstream = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "choices": [{"message": {"role": "assistant", "content": "你好"}}],
        }

        with patch.object(main, "post_llama", new=AsyncMock(return_value=upstream)) as post_llama:
            response = self.client.post(
                "/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "Translate hello"}],
                    "stream": False,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), upstream)
        post_llama.assert_awaited_once()
        path, payload = post_llama.await_args.args
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual(payload["model"], "hy-mt-test")

    def test_chat_completions_rejects_non_object_json_with_openai_error_shape(self) -> None:
        response = self.client.post("/v1/chat/completions", json=["not", "an", "object"])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["type"], "invalid_request_error")
        self.assertEqual(response.json()["error"]["code"], "invalid_json_body")

    def test_chat_completions_rejects_malformed_json_with_openai_error_shape(self) -> None:
        response = self.client.post(
            "/v1/chat/completions",
            content="{",
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["type"], "invalid_request_error")
        self.assertEqual(response.json()["error"]["code"], "invalid_json_body")

    def test_post_llama_wraps_upstream_http_error_in_openai_error_shape(self) -> None:
        with patch.object(main, "LLAMA_SERVER_URL", "http://llama.test"):
            with patch("app.main.httpx.AsyncClient") as client_cls:
                response = httpx_response(429, "rate limited")
                client = client_cls.return_value.__aenter__.return_value
                client.post = AsyncMock(return_value=response)

                result = self.client.post(
                    "/v1/chat/completions",
                    json={"messages": [{"role": "user", "content": "hello"}]},
                )

        self.assertEqual(result.status_code, 429)
        self.assertEqual(result.json()["error"]["type"], "upstream_error")
        self.assertIn("rate limited", result.json()["error"]["message"])


def httpx_response(status_code: int, text: str):
    import httpx

    request = httpx.Request("POST", "http://llama.test/v1/chat/completions")
    return httpx.Response(status_code, text=text, request=request)


if __name__ == "__main__":
    unittest.main()
