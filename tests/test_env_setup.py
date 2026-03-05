"""Tests for orchestrator.env_setup — environment verification helpers.

These tests are designed to run in *any* CI environment (with or without a
GPU).  GPU-specific behaviour is tested via mocking.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path
from unittest import mock

import pytest

from orchestrator.env_setup import (
    CheckResult,
    EnvReport,
    check_nvidia_smi,
    check_python_version,
    check_requirements_file,
    install_requirements,
    main,
    run_checks,
)


# ── CheckResult / EnvReport unit tests ──────────────────────────────

class TestCheckResult:
    """Basic data-class behaviour."""

    def test_fields(self):
        r = CheckResult(name="foo", passed=True, message="ok")
        assert r.name == "foo"
        assert r.passed is True
        assert r.message == "ok"
        assert r.details is None

    def test_with_details(self):
        r = CheckResult(name="bar", passed=False, message="fail", details="x")
        assert r.details == "x"


class TestEnvReport:
    """Aggregated report logic."""

    def test_ok_when_all_pass(self):
        rpt = EnvReport(
            checks=[
                CheckResult("a", True, "good"),
                CheckResult("b", True, "good"),
            ]
        )
        assert rpt.ok is True

    def test_not_ok_when_any_fails(self):
        rpt = EnvReport(
            checks=[
                CheckResult("a", True, "good"),
                CheckResult("b", False, "bad"),
            ]
        )
        assert rpt.ok is False

    def test_empty_report_is_ok(self):
        assert EnvReport().ok is True

    def test_summary_contains_status(self):
        rpt = EnvReport(
            checks=[CheckResult("a", True, "good")]
        )
        s = rpt.summary()
        assert "PASS" in s

    def test_summary_fail(self):
        rpt = EnvReport(
            checks=[CheckResult("a", False, "bad")]
        )
        s = rpt.summary()
        assert "FAIL" in s

    def test_summary_includes_details(self):
        rpt = EnvReport(
            checks=[CheckResult("a", True, "ok", details="detail line")]
        )
        assert "detail line" in rpt.summary()


# ── check_python_version ─────────────────────────────────────────────

class TestCheckPythonVersion:
    """Python version verification."""

    def test_passes_on_current_interpreter(self):
        """We require 3.11+ and the test suite itself runs on 3.11+."""
        result = check_python_version()
        # If someone runs tests on 3.10 this will correctly fail.
        if sys.version_info >= (3, 11):
            assert result.passed is True
        else:
            assert result.passed is False

    def test_message_contains_version(self):
        result = check_python_version()
        assert "Python" in result.message


# ── check_nvidia_smi ─────────────────────────────────────────────────

class TestCheckNvidiaSmi:
    """nvidia-smi verification (mocked)."""

    def test_not_found(self):
        with mock.patch("orchestrator.env_setup.shutil.which", return_value=None):
            result = check_nvidia_smi()
        assert result.passed is False
        assert "not found" in result.message

    def test_success(self):
        fake_output = "NVIDIA-SMI 550.0  Driver Version: 550.0  CUDA Version: 12.4\n"
        proc = subprocess.CompletedProcess(
            args=["nvidia-smi"],
            returncode=0,
            stdout=fake_output,
            stderr="",
        )
        with (
            mock.patch("orchestrator.env_setup.shutil.which", return_value="/usr/bin/nvidia-smi"),
            mock.patch("orchestrator.env_setup.subprocess.run", return_value=proc),
        ):
            result = check_nvidia_smi()
        assert result.passed is True
        assert result.details is not None

    def test_nonzero_exit(self):
        proc = subprocess.CompletedProcess(
            args=["nvidia-smi"],
            returncode=1,
            stdout="",
            stderr="error msg",
        )
        with (
            mock.patch("orchestrator.env_setup.shutil.which", return_value="/usr/bin/nvidia-smi"),
            mock.patch("orchestrator.env_setup.subprocess.run", return_value=proc),
        ):
            result = check_nvidia_smi()
        assert result.passed is False

    def test_timeout(self):
        with (
            mock.patch("orchestrator.env_setup.shutil.which", return_value="/usr/bin/nvidia-smi"),
            mock.patch(
                "orchestrator.env_setup.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=30),
            ),
        ):
            result = check_nvidia_smi()
        assert result.passed is False
        assert "timed out" in result.message

    def test_os_error(self):
        with (
            mock.patch("orchestrator.env_setup.shutil.which", return_value="/usr/bin/nvidia-smi"),
            mock.patch(
                "orchestrator.env_setup.subprocess.run",
                side_effect=OSError("permission denied"),
            ),
        ):
            result = check_nvidia_smi()
        assert result.passed is False
        assert "execution error" in result.message


# ── check_requirements_file ──────────────────────────────────────────

class TestCheckRequirementsFile:
    """requirements.txt existence / content checks."""

    def test_missing_file(self, tmp_path: Path):
        result = check_requirements_file(str(tmp_path / "nope.txt"))
        assert result.passed is False
        assert "not found" in result.message

    def test_empty_file(self, tmp_path: Path):
        f = tmp_path / "requirements.txt"
        f.write_text("# only a comment\n")
        result = check_requirements_file(str(f))
        assert result.passed is False
        assert "empty" in result.message

    def test_valid_file(self, tmp_path: Path):
        f = tmp_path / "requirements.txt"
        f.write_text("fastapi>=0.115\nuvicorn\n")
        result = check_requirements_file(str(f))
        assert result.passed is True
        assert "2 dependencies" in result.message

    def test_real_requirements_txt(self):
        """The project's own requirements.txt should pass."""
        result = check_requirements_file("requirements.txt")
        assert result.passed is True


# ── install_requirements ─────────────────────────────────────────────

class TestInstallRequirements:
    """pip install verification (mocked)."""

    def test_missing_file(self, tmp_path: Path):
        result = install_requirements(str(tmp_path / "nope.txt"))
        assert result.passed is False

    def test_success(self, tmp_path: Path):
        f = tmp_path / "requirements.txt"
        f.write_text("somelib\n")
        proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with mock.patch("orchestrator.env_setup.subprocess.run", return_value=proc):
            result = install_requirements(str(f))
        assert result.passed is True

    def test_failure(self, tmp_path: Path):
        f = tmp_path / "requirements.txt"
        f.write_text("somelib\n")
        proc = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="ERROR"
        )
        with mock.patch("orchestrator.env_setup.subprocess.run", return_value=proc):
            result = install_requirements(str(f))
        assert result.passed is False

    def test_timeout(self, tmp_path: Path):
        f = tmp_path / "requirements.txt"
        f.write_text("somelib\n")
        with mock.patch(
            "orchestrator.env_setup.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="pip", timeout=600),
        ):
            result = install_requirements(str(f))
        assert result.passed is False
        assert "timed out" in result.message


# ── run_checks integration ───────────────────────────────────────────

class TestRunChecks:
    """High-level run_checks orchestrator."""

    def test_skip_gpu(self, tmp_path: Path):
        f = tmp_path / "requirements.txt"
        f.write_text("fastapi\n")
        report = run_checks(skip_gpu=True, requirements_path=str(f))
        names = [c.name for c in report.checks]
        assert "nvidia_smi" not in names
        assert "python_version" in names
        assert "requirements_file" in names

    def test_includes_gpu_by_default(self, tmp_path: Path):
        f = tmp_path / "requirements.txt"
        f.write_text("fastapi\n")
        with mock.patch("orchestrator.env_setup.shutil.which", return_value=None):
            report = run_checks(requirements_path=str(f))
        names = [c.name for c in report.checks]
        assert "nvidia_smi" in names

    def test_install_flag(self, tmp_path: Path):
        f = tmp_path / "requirements.txt"
        f.write_text("fastapi\n")
        proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with (
            mock.patch("orchestrator.env_setup.shutil.which", return_value=None),
            mock.patch("orchestrator.env_setup.subprocess.run", return_value=proc),
        ):
            report = run_checks(
                install=True, skip_gpu=True, requirements_path=str(f)
            )
        names = [c.name for c in report.checks]
        assert "pip_install" in names


# ── CLI main() ───────────────────────────────────────────────────────

class TestCLI:
    """CLI entry-point tests."""

    def test_returns_zero_on_success(self, tmp_path: Path):
        f = tmp_path / "requirements.txt"
        f.write_text("fastapi\n")
        rc = main(["--skip-gpu", "--requirements", str(f)])
        if sys.version_info >= (3, 11):
            assert rc == 0
        else:
            assert rc == 1

    def test_returns_one_on_failure(self, tmp_path: Path):
        rc = main(["--skip-gpu", "--requirements", str(tmp_path / "nope.txt")])
        assert rc == 1

    def test_install_flag_accepted(self, tmp_path: Path):
        f = tmp_path / "requirements.txt"
        f.write_text("fastapi\n")
        proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with mock.patch("orchestrator.env_setup.subprocess.run", return_value=proc):
            rc = main(["--skip-gpu", "--install", "--requirements", str(f)])
        if sys.version_info >= (3, 11):
            assert rc == 0
