#!/usr/bin/env python3
"""Environment setup verifier for Sirus AI CRM.

This module provides helpers to verify that the host machine satisfies the
runtime prerequisites defined in the Sprint-1 task card (S1_W5):

* Python ≥ 3.11
* NVIDIA GPU driver reachable via ``nvidia-smi``
* Base pip dependencies installable from ``requirements.txt``

Usage
-----
Run directly to perform a quick health-check::

    python -m orchestrator.env_setup          # verify only
    python -m orchestrator.env_setup --install # also pip-install deps

The exit code is **0** when all checks pass, **1** otherwise.
"""

from __future__ import annotations

import argparse
import logging
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Minimum version requirements
# ---------------------------------------------------------------------------
MIN_PYTHON: Tuple[int, int] = (3, 11)
REQUIREMENTS_FILE: str = "requirements.txt"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class CheckResult:
    """Result of a single environment check."""

    name: str
    passed: bool
    message: str
    details: Optional[str] = None


@dataclass
class EnvReport:
    """Aggregated report for all environment checks."""

    checks: List[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Return ``True`` when every check passed."""
        return all(c.passed for c in self.checks)

    def summary(self) -> str:
        """Return a human-readable summary string."""
        lines: List[str] = []
        for c in self.checks:
            icon = "✅" if c.passed else "❌"
            lines.append(f"  {icon} {c.name}: {c.message}")
            if c.details:
                for detail_line in c.details.strip().splitlines():
                    lines.append(f"      {detail_line}")
        status = "PASS" if self.ok else "FAIL"
        lines.insert(0, f"Environment check: {status}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_python_version() -> CheckResult:
    """Verify that the running Python interpreter meets the minimum version.

    Returns
    -------
    CheckResult
        Passes when ``sys.version_info >= MIN_PYTHON``.
    """
    current = sys.version_info[:2]
    passed = current >= MIN_PYTHON
    ver_str = platform.python_version()
    if passed:
        msg = f"Python {ver_str} >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    else:
        msg = (
            f"Python {ver_str} < {MIN_PYTHON[0]}.{MIN_PYTHON[1]} — "
            "please install Python 3.11+"
        )
    return CheckResult(name="python_version", passed=passed, message=msg)


def check_nvidia_smi() -> CheckResult:
    """Verify that ``nvidia-smi`` is available and executes successfully.

    Returns
    -------
    CheckResult
        Passes when ``nvidia-smi`` exits with code 0.
    """
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        return CheckResult(
            name="nvidia_smi",
            passed=False,
            message="nvidia-smi not found on PATH",
        )
    try:
        proc = subprocess.run(
            [nvidia_smi],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            # Grab the first two meaningful lines for details.
            detail_lines = [
                ln
                for ln in proc.stdout.splitlines()
                if ln.strip()
            ][:6]
            return CheckResult(
                name="nvidia_smi",
                passed=True,
                message="nvidia-smi executed successfully",
                details="\n".join(detail_lines) if detail_lines else None,
            )
        return CheckResult(
            name="nvidia_smi",
            passed=False,
            message=f"nvidia-smi exited with code {proc.returncode}",
            details=proc.stderr[:500] if proc.stderr else None,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name="nvidia_smi",
            passed=False,
            message="nvidia-smi timed out (>30s)",
        )
    except OSError as exc:
        return CheckResult(
            name="nvidia_smi",
            passed=False,
            message=f"nvidia-smi execution error: {exc}",
        )


def check_requirements_file(
    requirements_path: str = REQUIREMENTS_FILE,
) -> CheckResult:
    """Verify that the project ``requirements.txt`` exists and is non-empty.

    Parameters
    ----------
    requirements_path:
        Relative or absolute path to the requirements file.

    Returns
    -------
    CheckResult
    """
    path = Path(requirements_path)
    if not path.exists():
        return CheckResult(
            name="requirements_file",
            passed=False,
            message=f"{requirements_path} not found",
        )
    content = path.read_text(encoding="utf-8").strip()
    non_comment_lines = [
        ln
        for ln in content.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    if not non_comment_lines:
        return CheckResult(
            name="requirements_file",
            passed=False,
            message=f"{requirements_path} is empty (no dependencies listed)",
        )
    return CheckResult(
        name="requirements_file",
        passed=True,
        message=f"{requirements_path} found with {len(non_comment_lines)} dependencies",
    )


def install_requirements(
    requirements_path: str = REQUIREMENTS_FILE,
) -> CheckResult:
    """Install dependencies from ``requirements.txt`` via pip.

    Parameters
    ----------
    requirements_path:
        Path to the requirements file.

    Returns
    -------
    CheckResult
    """
    path = Path(requirements_path)
    if not path.exists():
        return CheckResult(
            name="pip_install",
            passed=False,
            message=f"{requirements_path} not found — cannot install",
        )
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                str(path),
                "--quiet",
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode == 0:
            return CheckResult(
                name="pip_install",
                passed=True,
                message="pip install succeeded",
            )
        return CheckResult(
            name="pip_install",
            passed=False,
            message=f"pip install failed (exit {proc.returncode})",
            details=proc.stderr[:1000] if proc.stderr else None,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name="pip_install",
            passed=False,
            message="pip install timed out (>600s)",
        )
    except OSError as exc:
        return CheckResult(
            name="pip_install",
            passed=False,
            message=f"pip execution error: {exc}",
        )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_checks(
    *,
    install: bool = False,
    requirements_path: str = REQUIREMENTS_FILE,
    skip_gpu: bool = False,
) -> EnvReport:
    """Execute all environment checks and return an :class:`EnvReport`.

    Parameters
    ----------
    install:
        When ``True``, also run ``pip install -r requirements.txt``.
    requirements_path:
        Path to the requirements file.
    skip_gpu:
        When ``True``, skip the ``nvidia-smi`` check (useful in CI
        environments without a GPU).

    Returns
    -------
    EnvReport
    """
    report = EnvReport()

    report.checks.append(check_python_version())

    if not skip_gpu:
        report.checks.append(check_nvidia_smi())

    report.checks.append(check_requirements_file(requirements_path))

    if install:
        report.checks.append(install_requirements(requirements_path))

    return report


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry-point.

    Returns
    -------
    int
        ``0`` on success, ``1`` on failure.
    """
    parser = argparse.ArgumentParser(
        description="Verify Sirus AI CRM environment prerequisites.",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Also pip-install dependencies from requirements.txt",
    )
    parser.add_argument(
        "--requirements",
        default=REQUIREMENTS_FILE,
        help="Path to requirements.txt (default: %(default)s)",
    )
    parser.add_argument(
        "--skip-gpu",
        action="store_true",
        help="Skip nvidia-smi check (e.g. in CI without GPU)",
    )
    args = parser.parse_args(argv)

    report = run_checks(
        install=args.install,
        requirements_path=args.requirements,
        skip_gpu=args.skip_gpu,
    )
    print(report.summary())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
