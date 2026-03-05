"""
vLLM deployment and GPU verification tests.

Test tiers
----------
1. **Script structure** — Always run; verify scripts exist and are well-formed.
2. **GPU detection** — Require ``nvidia-smi``; auto-skipped on machines
   without an NVIDIA driver.
3. **Live vLLM server** — Require a running vLLM instance; enable with
   ``VLLM_INTEGRATION=1`` environment variable.

Usage::

    # Run fast/unit-level tests only (CI-safe, no GPU required)
    pytest tests/test_vllm_deployment.py -v

    # Include GPU detection tests (needs nvidia-smi)
    pytest tests/test_vllm_deployment.py -v

    # Include live integration tests against a running vLLM server
    VLLM_INTEGRATION=1 pytest tests/test_vllm_deployment.py -v
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants & markers
# ---------------------------------------------------------------------------

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

VLLM_HOST = os.environ.get("VLLM_HOST", "localhost")
VLLM_PORT = os.environ.get("VLLM_PORT", "8000")
VLLM_BASE_URL = f"http://{VLLM_HOST}:{VLLM_PORT}"

requires_gpu = pytest.mark.skipif(
    shutil.which("nvidia-smi") is None,
    reason="nvidia-smi not found — no NVIDIA GPU available",
)

requires_vllm_server = pytest.mark.skipif(
    os.environ.get("VLLM_INTEGRATION", "0") != "1",
    reason="Set VLLM_INTEGRATION=1 to run live vLLM server tests",
)


# ===================================================================
# 1. Script structure tests — always run
# ===================================================================


class TestScriptFiles:
    """Deployment scripts must exist, have a shebang, and be non-trivial."""

    EXPECTED_SCRIPTS = [
        "check_gpu.sh",
        "start_vllm.sh",
        "stop_vllm.sh",
        "check_vllm.sh",
    ]

    @pytest.mark.parametrize("name", EXPECTED_SCRIPTS)
    def test_script_exists(self, name: str) -> None:
        """Each vLLM deployment script must exist in scripts/."""
        path = SCRIPTS_DIR / name
        assert path.exists(), f"Missing script: {path}"

    @pytest.mark.parametrize("name", EXPECTED_SCRIPTS)
    def test_script_has_shebang(self, name: str) -> None:
        """Each script should start with a bash shebang."""
        path = SCRIPTS_DIR / name
        if not path.exists():
            pytest.skip(f"{name} not found")
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
        assert first_line.startswith("#!/"), f"{name} missing shebang: {first_line}"

    @pytest.mark.parametrize("name", EXPECTED_SCRIPTS)
    def test_script_not_trivially_empty(self, name: str) -> None:
        """Each script must contain meaningful content (> 10 lines)."""
        path = SCRIPTS_DIR / name
        if not path.exists():
            pytest.skip(f"{name} not found")
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) > 10, f"{name} only has {len(lines)} lines"


class TestStartVllmDefaults:
    """Verify start_vllm.sh embeds the correct default configuration."""

    @pytest.fixture()
    def script_content(self) -> str:
        path = SCRIPTS_DIR / "start_vllm.sh"
        if not path.exists():
            pytest.skip("start_vllm.sh not found")
        return path.read_text(encoding="utf-8")

    def test_default_model(self, script_content: str) -> None:
        """Default model must be Qwen/Qwen3-30B-A3B (per Sprint task)."""
        assert "Qwen/Qwen3-30B-A3B" in script_content

    def test_default_port(self, script_content: str) -> None:
        """Default port must be 8000 (matches agent-api.yaml local vLLM)."""
        assert "8000" in script_content

    def test_tensor_parallel_default_is_two(self, script_content: str) -> None:
        """Default tensor-parallel-size should be 2 for 2×4090."""
        # Match the bash default pattern: ${VLLM_TP_SIZE:-2}
        assert ":-2}" in script_content or 'TP_SIZE:-2' in script_content

    def test_gpu_memory_utilization(self, script_content: str) -> None:
        """GPU memory utilization should default to 0.85."""
        assert "0.85" in script_content

    def test_prefix_caching_enabled(self, script_content: str) -> None:
        """--enable-prefix-caching must be present for throughput."""
        assert "--enable-prefix-caching" in script_content

    def test_trust_remote_code(self, script_content: str) -> None:
        """--trust-remote-code is required for Qwen models."""
        assert "--trust-remote-code" in script_content

    def test_daemon_flag_supported(self, script_content: str) -> None:
        """Script must support a --daemon flag for background mode."""
        assert "--daemon" in script_content


class TestStopVllmScript:
    """Verify stop_vllm.sh handles PID-based and fallback shutdown."""

    @pytest.fixture()
    def script_content(self) -> str:
        path = SCRIPTS_DIR / "stop_vllm.sh"
        if not path.exists():
            pytest.skip("stop_vllm.sh not found")
        return path.read_text(encoding="utf-8")

    def test_sends_sigterm(self, script_content: str) -> None:
        """Graceful shutdown should use SIGTERM first."""
        assert "SIGTERM" in script_content or "TERM" in script_content

    def test_has_sigkill_fallback(self, script_content: str) -> None:
        """Force-kill fallback should use SIGKILL."""
        assert "SIGKILL" in script_content or "KILL" in script_content or "kill -9" in script_content


class TestCheckVllmScript:
    """Verify check_vllm.sh probes the /v1/models endpoint."""

    @pytest.fixture()
    def script_content(self) -> str:
        path = SCRIPTS_DIR / "check_vllm.sh"
        if not path.exists():
            pytest.skip("check_vllm.sh not found")
        return path.read_text(encoding="utf-8")

    def test_calls_v1_models(self, script_content: str) -> None:
        """/v1/models must be the health-check target."""
        assert "/v1/models" in script_content

    def test_uses_curl(self, script_content: str) -> None:
        """Health check should use curl."""
        assert "curl" in script_content


# ===================================================================
# 2. GPU detection tests — require nvidia-smi
# ===================================================================


class TestGPU:
    """GPU detection tests. Auto-skipped when nvidia-smi is absent."""

    @requires_gpu
    def test_nvidia_smi_runs(self) -> None:
        """nvidia-smi should execute without errors."""
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"nvidia-smi failed:\n{result.stderr}"
        assert "NVIDIA" in result.stdout, "nvidia-smi output missing 'NVIDIA'"

    @requires_gpu
    def test_gpu_count_at_least_one(self) -> None:
        """At least 1 GPU must be present."""
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        gpus = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        assert len(gpus) >= 1, f"Expected ≥1 GPU, found {len(gpus)}"

    @requires_gpu
    def test_gpu_count_at_least_two(self) -> None:
        """2 GPUs required for tensor-parallel-size=2."""
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        gpus = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        assert len(gpus) >= 2, (
            f"Expected ≥2 GPUs for tp=2, found {len(gpus)}: {gpus}"
        )

    @requires_gpu
    def test_check_gpu_script_passes(self) -> None:
        """scripts/check_gpu.sh should exit 0 on a healthy GPU machine."""
        script = SCRIPTS_DIR / "check_gpu.sh"
        if not script.exists():
            pytest.skip("check_gpu.sh not found")
        result = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"check_gpu.sh failed (rc={result.returncode}):\n{result.stdout}\n{result.stderr}"
        )


# ===================================================================
# 3. Live vLLM integration tests — require VLLM_INTEGRATION=1
# ===================================================================


class TestVllmLive:
    """Integration tests against a running vLLM server.

    Enable with ``VLLM_INTEGRATION=1``.
    The server must already be running on ``VLLM_HOST:VLLM_PORT``
    (defaults to ``localhost:8000``).
    """

    @requires_vllm_server
    def test_models_endpoint_returns_200(self) -> None:
        """GET /v1/models must return HTTP 200."""
        requests = pytest.importorskip("requests")
        resp = requests.get(f"{VLLM_BASE_URL}/v1/models", timeout=10)
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code}"

    @requires_vllm_server
    def test_models_endpoint_has_data(self) -> None:
        """GET /v1/models must return at least one model entry."""
        requests = pytest.importorskip("requests")
        resp = requests.get(f"{VLLM_BASE_URL}/v1/models", timeout=10)
        data = resp.json()
        assert "data" in data, f"Response missing 'data': {data}"
        assert len(data["data"]) > 0, "No models loaded"

    @requires_vllm_server
    def test_model_id_contains_qwen(self) -> None:
        """The loaded model ID should reference Qwen."""
        requests = pytest.importorskip("requests")
        resp = requests.get(f"{VLLM_BASE_URL}/v1/models", timeout=10)
        model_ids = [m.get("id", "") for m in resp.json().get("data", [])]
        assert any("qwen" in mid.lower() for mid in model_ids), (
            f"Expected a Qwen model, found: {model_ids}"
        )

    @requires_vllm_server
    def test_completions_returns_text(self) -> None:
        """POST /v1/completions should generate non-empty text."""
        requests = pytest.importorskip("requests")

        # Discover the model name dynamically
        models_resp = requests.get(f"{VLLM_BASE_URL}/v1/models", timeout=10)
        model_id = models_resp.json()["data"][0]["id"]

        payload = {
            "model": model_id,
            "prompt": "Hello",
            "max_tokens": 16,
            "temperature": 0.0,
        }
        resp = requests.post(
            f"{VLLM_BASE_URL}/v1/completions",
            json=payload,
            timeout=60,
        )
        assert resp.status_code == 200, f"Completions failed: {resp.text}"
        data = resp.json()
        assert "choices" in data and len(data["choices"]) > 0
        generated = data["choices"][0].get("text", "")
        assert generated.strip(), "Completion returned empty text"

    @requires_vllm_server
    def test_chat_completions_endpoint(self) -> None:
        """POST /v1/chat/completions should work (used by Agent engine)."""
        requests = pytest.importorskip("requests")

        models_resp = requests.get(f"{VLLM_BASE_URL}/v1/models", timeout=10)
        model_id = models_resp.json()["data"][0]["id"]

        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 16,
            "temperature": 0.0,
        }
        resp = requests.post(
            f"{VLLM_BASE_URL}/v1/chat/completions",
            json=payload,
            timeout=60,
        )
        assert resp.status_code == 200, f"Chat completions failed: {resp.text}"
        data = resp.json()
        assert "choices" in data and len(data["choices"]) > 0

    @requires_vllm_server
    def test_check_vllm_script_passes(self) -> None:
        """scripts/check_vllm.sh should exit 0 when the server is healthy."""
        script = SCRIPTS_DIR / "check_vllm.sh"
        if not script.exists():
            pytest.skip("check_vllm.sh not found")
        result = subprocess.run(
            ["bash", str(script), VLLM_HOST, VLLM_PORT],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"check_vllm.sh failed:\n{result.stdout}\n{result.stderr}"
        )
