"""
Tests for vLLM inference server health and model availability.

These tests verify that the vLLM server is running and serving
the expected model (Qwen3-30B-A3B) via the OpenAI-compatible API.

Usage:
    pytest tests/test_vllm_health.py -v
    pytest tests/test_vllm_health.py -v -k test_models_endpoint

Environment variables:
    VLLM_BASE_URL  — vLLM server URL (default: http://localhost:8000)
    VLLM_MODEL     — Expected model name (default: Qwen/Qwen3-30B-A3B)
"""

import os

import httpx
import pytest

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000")
EXPECTED_MODEL = os.getenv("VLLM_MODEL", "Qwen/Qwen3-30B-A3B")

# Timeout for requests (model loading can be slow)
REQUEST_TIMEOUT = 10.0


def _vllm_is_reachable() -> bool:
    """Quick probe to check if the vLLM server is healthy.

    Returns True only when /v1/models responds with HTTP 200.
    Returns False for connection errors, timeouts, 502 Bad Gateway,
    or any other non-200 status — so tests skip gracefully.
    """
    try:
        resp = httpx.get(f"{VLLM_BASE_URL}/v1/models", timeout=5.0)
        return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError, OSError):
        return False


# Evaluate once at module import time.
_VLLM_AVAILABLE = _vllm_is_reachable()

# Skip ALL tests in this module when vLLM is not available.
# This prevents 502 / ConnectionError failures in CI or on machines
# where the inference server is not running.
pytestmark = pytest.mark.skipif(
    not _VLLM_AVAILABLE,
    reason=(
        f"vLLM server not reachable at {VLLM_BASE_URL} "
        "(connection refused, timeout, or non-200 response). "
        "Start it with: bash scripts/start_vllm.sh --daemon"
    ),
)


@pytest.fixture
def base_url() -> str:
    """Return the vLLM server base URL."""
    return VLLM_BASE_URL


class TestVLLMHealth:
    """Test suite for vLLM server health and model availability."""

    def test_models_endpoint_returns_200(self, base_url: str) -> None:
        """GET /v1/models should return HTTP 200."""
        response = httpx.get(f"{base_url}/v1/models", timeout=REQUEST_TIMEOUT)
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

    def test_models_endpoint_returns_json(self, base_url: str) -> None:
        """GET /v1/models should return valid JSON with expected structure."""
        response = httpx.get(f"{base_url}/v1/models", timeout=REQUEST_TIMEOUT)
        data = response.json()

        assert "data" in data, f"Response missing 'data' key: {data}"
        assert isinstance(data["data"], list), (
            f"'data' should be a list, got {type(data['data'])}"
        )
        assert len(data["data"]) > 0, "No models loaded"

    def test_expected_model_is_loaded(self, base_url: str) -> None:
        """The expected model (Qwen3-30B-A3B) should be present in model list."""
        response = httpx.get(f"{base_url}/v1/models", timeout=REQUEST_TIMEOUT)
        data = response.json()

        model_ids = [model["id"] for model in data["data"]]
        assert EXPECTED_MODEL in model_ids, (
            f"Expected model '{EXPECTED_MODEL}' not found. "
            f"Available models: {model_ids}"
        )

    def test_model_object_structure(self, base_url: str) -> None:
        """Each model object should have the required OpenAI-compatible fields."""
        response = httpx.get(f"{base_url}/v1/models", timeout=REQUEST_TIMEOUT)
        data = response.json()

        for model in data["data"]:
            assert "id" in model, f"Model missing 'id': {model}"
            assert "object" in model, f"Model missing 'object': {model}"
            assert model["object"] == "model", (
                f"Expected object='model', got '{model['object']}'"
            )

    def test_completions_endpoint_accepts_request(self, base_url: str) -> None:
        """POST /v1/completions should accept a basic request (smoke test)."""
        payload = {
            "model": EXPECTED_MODEL,
            "prompt": "Hello",
            "max_tokens": 5,
            "temperature": 0.0,
        }
        response = httpx.post(
            f"{base_url}/v1/completions",
            json=payload,
            timeout=30.0,
        )
        assert response.status_code == 200, (
            f"Completions failed with {response.status_code}: {response.text}"
        )
        data = response.json()
        assert "choices" in data, f"Response missing 'choices': {data}"
        assert len(data["choices"]) > 0, "No choices returned"

    def test_chat_completions_endpoint(self, base_url: str) -> None:
        """POST /v1/chat/completions should work (OpenAI chat format)."""
        payload = {
            "model": EXPECTED_MODEL,
            "messages": [
                {"role": "user", "content": "Say hello in one word."}
            ],
            "max_tokens": 10,
            "temperature": 0.0,
        }
        response = httpx.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            timeout=30.0,
        )
        assert response.status_code == 200, (
            f"Chat completions failed with {response.status_code}: {response.text}"
        )
        data = response.json()
        assert "choices" in data, f"Response missing 'choices': {data}"
        assert len(data["choices"]) > 0, "No choices returned"
        assert "message" in data["choices"][0], "Choice missing 'message'"


class TestVLLMConnectivity:
    """Test basic connectivity to the vLLM server."""

    def test_server_is_reachable(self, base_url: str) -> None:
        """The vLLM server should be reachable at the configured URL.

        Note: the module-level pytestmark already skips all tests when
        vLLM is unavailable, so if we reach this point the server was
        reachable at import time.  We re-check here to catch transient
        failures during the test run.
        """
        try:
            response = httpx.get(
                f"{base_url}/v1/models", timeout=REQUEST_TIMEOUT
            )
            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text}"
            )
        except httpx.ConnectError:
            pytest.fail(
                f"Cannot connect to vLLM at {base_url}. "
                "Is the server running? Start with: bash scripts/start_vllm.sh"
            )
        except httpx.TimeoutException:
            pytest.fail(
                f"Connection to vLLM at {base_url} timed out "
                f"after {REQUEST_TIMEOUT}s. The model may still be loading."
            )
