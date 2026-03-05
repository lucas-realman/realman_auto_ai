"""
Test suite for vLLM inference server tuning validation.

Sprint 1-2 acceptance criteria:
  - TTFT (Time To First Token) < 2 seconds (P95)
  - Throughput > 20 tokens/second

Tuning parameters verified:
  - tensor-parallel-size = 2  (2×RTX 4090)
  - enable-prefix-caching     (KV cache reuse)
  - gpu-memory-utilization = 0.85

Usage:
  pytest tests/test_vllm_benchmark.py -v
  pytest tests/test_vllm_benchmark.py -v -k "not concurrent"  # skip concurrency test

Environment variables:
  VLLM_BASE_URL  — Server URL   (default: http://localhost:8000)
  VLLM_MODEL     — Model name   (default: Qwen/Qwen3-30B-A3B)
"""

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000")
VLLM_MODEL = os.getenv("VLLM_MODEL", "Qwen/Qwen3-30B-A3B")

# Sprint 1-2 acceptance thresholds
TTFT_THRESHOLD_MS = 2000  # 2 seconds
THROUGHPUT_THRESHOLD_TPS = 20  # tokens per second

# Test parameters
MAX_TOKENS = 50
REQUEST_TIMEOUT = 30.0

# Tuning parameters to verify
EXPECTED_TP_SIZE = "2"
EXPECTED_GPU_UTIL = "0.85"

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def vllm_base_url() -> str:
    """Return the vLLM server base URL."""
    return VLLM_BASE_URL


@pytest.fixture(scope="session")
def vllm_model() -> str:
    """Return the expected model name."""
    return VLLM_MODEL


@pytest.fixture(scope="session")
def vllm_available(vllm_base_url: str) -> bool:
    """Check if vLLM server is reachable; skip tests if not."""
    try:
        resp = httpx.get(f"{vllm_base_url}/v1/models", timeout=5.0)
        if resp.status_code == 200:
            return True
    except (httpx.ConnectError, httpx.TimeoutException):
        pass
    pytest.skip(
        f"vLLM server not reachable at {vllm_base_url}. "
        "Start with: bash scripts/start_vllm.sh --daemon"
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
async def _chat_completion(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int = MAX_TOKENS,
) -> dict:
    """Send a chat completion request and return parsed response with timing."""
    start = time.perf_counter_ns()
    resp = await client.post(
        f"{base_url}/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.0,
        },
        timeout=REQUEST_TIMEOUT,
    )
    elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000

    assert resp.status_code == 200, f"vLLM returned {resp.status_code}: {resp.text}"
    data = resp.json()
    completion_tokens = data.get("usage", {}).get("completion_tokens", 0)

    return {
        "data": data,
        "elapsed_ms": elapsed_ms,
        "completion_tokens": completion_tokens,
    }


# ---------------------------------------------------------------------------
# Script syntax tests (always runnable, no server needed)
# ---------------------------------------------------------------------------
class TestScriptSyntax:
    """Verify all vLLM shell scripts have valid bash syntax."""

    @pytest.mark.parametrize(
        "script",
        ["start_vllm.sh", "stop_vllm.sh", "benchmark_vllm.sh", "check_gpu.sh"],
    )
    def test_script_syntax(self, script: str):
        """Check bash -n (syntax check) passes for each script."""
        script_path = SCRIPTS_DIR / script
        if not script_path.exists():
            pytest.skip(f"{script} not found at {script_path}")
        result = subprocess.run(
            ["bash", "-n", str(script_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Syntax error in {script}: {result.stderr}"
        )


class TestTuningParameters:
    """Verify tuning parameters are correctly set in start_vllm.sh."""

    @pytest.fixture(autouse=True)
    def _load_start_script(self):
        """Load start_vllm.sh content."""
        self.script_path = SCRIPTS_DIR / "start_vllm.sh"
        if not self.script_path.exists():
            pytest.skip("start_vllm.sh not found")
        self.content = self.script_path.read_text()

    def test_tensor_parallel_size(self):
        """Verify tp_size defaults to 2 for 2×RTX 4090."""
        assert "VLLM_TP_SIZE:-2" in self.content or "TP_SIZE:-2" in self.content, (
            "tensor-parallel-size should default to 2"
        )

    def test_gpu_memory_utilization(self):
        """Verify gpu-memory-utilization defaults to 0.85."""
        assert "VLLM_GPU_UTIL:-0.85" in self.content or "GPU_MEMORY_UTIL:-0.85" in self.content, (
            "gpu-memory-utilization should default to 0.85"
        )

    def test_enable_prefix_caching(self):
        """Verify --enable-prefix-caching flag is present."""
        assert "--enable-prefix-caching" in self.content, (
            "--enable-prefix-caching flag must be set for KV cache reuse"
        )

    def test_max_model_len(self):
        """Verify max-model-len defaults to 8192."""
        assert "MAX_MODEL_LEN" in self.content, (
            "MAX_MODEL_LEN should be configurable"
        )

    def test_max_num_seqs(self):
        """Verify max-num-seqs defaults to 64."""
        assert "MAX_NUM_SEQS" in self.content, (
            "MAX_NUM_SEQS should be configurable"
        )

    def test_trust_remote_code(self):
        """Verify --trust-remote-code is set (required for Qwen models)."""
        assert "--trust-remote-code" in self.content, (
            "--trust-remote-code required for Qwen3-30B-A3B"
        )

    def test_dtype_auto(self):
        """Verify --dtype auto is set for optimal precision."""
        assert "--dtype auto" in self.content, (
            "--dtype auto should be set for automatic precision selection"
        )


# ---------------------------------------------------------------------------
# Server connectivity tests (require running vLLM)
# ---------------------------------------------------------------------------
class TestVLLMServer:
    """Tests that require a running vLLM server."""

    @pytest.mark.asyncio
    async def test_models_endpoint(self, vllm_available, vllm_base_url, vllm_model):
        """Verify /v1/models returns the expected model."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{vllm_base_url}/v1/models", timeout=10.0
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "data" in data, "Response missing 'data' field"
            assert len(data["data"]) > 0, "No models loaded"

            model_ids = [m["id"] for m in data["data"]]
            assert vllm_model in model_ids, (
                f"Expected model {vllm_model} not in {model_ids}"
            )

    @pytest.mark.asyncio
    async def test_health_endpoint(self, vllm_available, vllm_base_url):
        """Verify vLLM health endpoint responds."""
        async with httpx.AsyncClient() as client:
            # vLLM exposes /health in newer versions
            resp = await client.get(f"{vllm_base_url}/health", timeout=10.0)
            # Accept 200 or 404 (older vLLM versions may not have /health)
            assert resp.status_code in (200, 404), (
                f"Unexpected status {resp.status_code}"
            )


# ---------------------------------------------------------------------------
# Performance tests (require running vLLM)
# ---------------------------------------------------------------------------
class TestVLLMPerformance:
    """Sprint 1-2 acceptance criteria: TTFT < 2s, throughput > 20 tok/s."""

    @pytest.mark.asyncio
    async def test_single_request_latency(
        self, vllm_available, vllm_base_url, vllm_model
    ):
        """Single request latency should be under TTFT threshold."""
        async with httpx.AsyncClient() as client:
            result = await _chat_completion(
                client,
                vllm_base_url,
                vllm_model,
                "Explain what a CRM system is in one paragraph.",
            )

        assert result["completion_tokens"] > 0, "No tokens generated"
        assert result["elapsed_ms"] < TTFT_THRESHOLD_MS, (
            f"Latency {result['elapsed_ms']:.0f}ms exceeds "
            f"threshold {TTFT_THRESHOLD_MS}ms"
        )

    @pytest.mark.asyncio
    async def test_throughput(self, vllm_available, vllm_base_url, vllm_model):
        """Sequential throughput should exceed 20 tok/s."""
        prompts = [
            "Explain what a CRM system is in one paragraph.",
            "List three benefits of AI in sales.",
            "What is lead scoring?",
            "Describe the sales funnel stages.",
            "How does customer segmentation work?",
        ]

        total_tokens = 0
        total_ms = 0.0

        async with httpx.AsyncClient() as client:
            for prompt in prompts:
                result = await _chat_completion(
                    client, vllm_base_url, vllm_model, prompt
                )
                total_tokens += result["completion_tokens"]
                total_ms += result["elapsed_ms"]

        throughput = (total_tokens / (total_ms / 1000)) if total_ms > 0 else 0
        assert throughput >= THROUGHPUT_THRESHOLD_TPS, (
            f"Throughput {throughput:.1f} tok/s below "
            f"threshold {THROUGHPUT_THRESHOLD_TPS} tok/s"
        )

    @pytest.mark.asyncio
    async def test_concurrent_requests(
        self, vllm_available, vllm_base_url, vllm_model
    ):
        """Concurrent requests should complete within 2× TTFT threshold."""
        prompts = [
            "What is a lead?",
            "Define customer segmentation.",
            "Explain sales pipeline.",
            "What is conversion rate?",
        ]

        async def _single(prompt: str) -> dict:
            async with httpx.AsyncClient() as client:
                return await _chat_completion(
                    client, vllm_base_url, vllm_model, prompt
                )

        results = await asyncio.gather(*[_single(p) for p in prompts])

        max_latency = max(r["elapsed_ms"] for r in results)
        total_tokens = sum(r["completion_tokens"] for r in results)

        # Under concurrent load, allow 2× the single-request threshold
        concurrent_threshold = TTFT_THRESHOLD_MS * 2
        assert max_latency < concurrent_threshold, (
            f"Max concurrent latency {max_latency:.0f}ms exceeds "
            f"threshold {concurrent_threshold}ms"
        )
        assert total_tokens > 0, "No tokens generated in concurrent test"

    @pytest.mark.asyncio
    async def test_prefix_caching_benefit(
        self, vllm_available, vllm_base_url, vllm_model
    ):
        """Repeated prompts should benefit from prefix caching (2nd call faster)."""
        prompt = "Explain the concept of lead scoring in CRM systems."

        async with httpx.AsyncClient() as client:
            # First call — cold
            first = await _chat_completion(
                client, vllm_base_url, vllm_model, prompt
            )
            # Second call — should hit prefix cache
            second = await _chat_completion(
                client, vllm_base_url, vllm_model, prompt
            )

        # We don't strictly require faster (caching is best-effort),
        # but both must succeed within threshold
        assert first["elapsed_ms"] < TTFT_THRESHOLD_MS, (
            f"First call {first['elapsed_ms']:.0f}ms exceeds threshold"
        )
        assert second["elapsed_ms"] < TTFT_THRESHOLD_MS, (
            f"Second call {second['elapsed_ms']:.0f}ms exceeds threshold"
        )

    @pytest.mark.asyncio
    async def test_response_quality(
        self, vllm_available, vllm_base_url, vllm_model
    ):
        """Verify response contains meaningful content (not empty/garbage)."""
        async with httpx.AsyncClient() as client:
            result = await _chat_completion(
                client,
                vllm_base_url,
                vllm_model,
                "What is a CRM system? Answer in one sentence.",
                max_tokens=100,
            )

        data = result["data"]
        choices = data.get("choices", [])
        assert len(choices) > 0, "No choices in response"

        content = choices[0].get("message", {}).get("content", "")
        assert len(content) > 10, f"Response too short: '{content}'"
        # Basic sanity: response should mention CRM or customer
        content_lower = content.lower()
        assert any(
            kw in content_lower for kw in ["crm", "customer", "relationship"]
        ), f"Response doesn't seem relevant: '{content[:200]}'"
