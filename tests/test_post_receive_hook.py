"""Tests for the Git post-receive hook mechanism.

Validates that:
1. The hook script exists and is well-formed
2. The install script exists and is well-formed
3. SSH configuration variables are present
4. Remote test execution logic is correct
"""

import os
import stat
import subprocess
from pathlib import Path

import pytest

# Resolve paths relative to project root (tests run from project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = PROJECT_ROOT / "scripts" / "post-receive"
INSTALL_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "install_hook.sh"


class TestPostReceiveHookFile:
    """Verify the post-receive hook script structure."""

    def test_hook_file_exists(self):
        """post-receive hook file must exist in scripts/."""
        assert HOOK_PATH.exists(), f"Hook file not found at {HOOK_PATH}"

    def test_hook_is_executable(self):
        """post-receive hook must have the executable bit set."""
        mode = HOOK_PATH.stat().st_mode
        assert mode & stat.S_IXUSR, "Hook file is not executable (missing u+x)"

    def test_hook_has_bash_shebang(self):
        """post-receive hook must start with a bash shebang."""
        first_line = HOOK_PATH.read_text().splitlines()[0].strip()
        assert first_line == "#!/usr/bin/env bash", (
            f"Expected '#!/usr/bin/env bash', got '{first_line}'"
        )

    def test_hook_uses_strict_mode(self):
        """Hook must use 'set -euo pipefail' for safety."""
        content = HOOK_PATH.read_text()
        assert "set -euo pipefail" in content, "Hook missing 'set -euo pipefail'"


class TestPostReceiveHookSSHLogic:
    """Verify the hook contains correct SSH trigger logic."""

    @pytest.fixture(autouse=True)
    def _load_hook(self):
        """Load hook content once for all tests in this class."""
        self.content = HOOK_PATH.read_text()

    def test_contains_ssh_command(self):
        """Hook must build an SSH command to reach the orchestrator."""
        assert "SSH_CMD" in self.content, "Hook missing SSH_CMD variable"

    def test_contains_remote_script(self):
        """Hook must define a REMOTE_SCRIPT to run on the orchestrator."""
        assert "REMOTE_SCRIPT" in self.content, "Hook missing REMOTE_SCRIPT block"

    def test_remote_script_runs_pytest(self):
        """The remote script must invoke pytest."""
        assert "pytest" in self.content, "Hook remote script does not invoke pytest"

    def test_remote_script_pulls_code(self):
        """The remote script must pull latest code before testing."""
        assert "git pull" in self.content or "git fetch" in self.content, (
            "Hook remote script does not pull latest code"
        )


class TestPostReceiveHookEnvironment:
    """Verify hook respects all required environment variables."""

    REQUIRED_ENV_VARS = [
        "ORCHESTRATOR_HOST",
        "ORCHESTRATOR_USER",
        "ORCHESTRATOR_PORT",
        "PROJECT_DIR",
        "TEST_TIMEOUT",
        "LOG_DIR",
    ]

    @pytest.fixture(autouse=True)
    def _load_hook(self):
        self.content = HOOK_PATH.read_text()

    @pytest.mark.parametrize("var", REQUIRED_ENV_VARS)
    def test_env_variable_present(self, var: str):
        """Each required env variable must appear in the hook."""
        assert var in self.content, f"Hook missing environment variable {var}"

    def test_env_vars_have_defaults(self):
        """Key variables must have sensible defaults via ${VAR:-default}."""
        assert '${ORCHESTRATOR_HOST:-' in self.content
        assert '${ORCHESTRATOR_PORT:-' in self.content
        assert '${TEST_TIMEOUT:-' in self.content


class TestPostReceiveHookLogging:
    """Verify hook has proper logging."""

    @pytest.fixture(autouse=True)
    def _load_hook(self):
        self.content = HOOK_PATH.read_text()

    def test_creates_log_directory(self):
        """Hook must create the log directory."""
        assert "mkdir -p" in self.content, "Hook missing log directory creation"

    def test_defines_log_file(self):
        """Hook must define a LOG_FILE variable."""
        assert "LOG_FILE" in self.content, "Hook missing LOG_FILE variable"

    def test_has_log_function(self):
        """Hook must define a log() helper function."""
        assert "log()" in self.content or "log " in self.content, (
            "Hook missing log function"
        )


class TestPostReceiveHookNonBlocking:
    """Verify hook does not block git push."""

    @pytest.fixture(autouse=True)
    def _load_hook(self):
        self.content = HOOK_PATH.read_text()

    def test_runs_tests_in_background(self):
        """Tests must run in a background sub-shell so push returns fast."""
        assert ") &" in self.content, (
            "Hook should run tests in a background sub-shell (') &')"
        )

    def test_exits_zero(self):
        """Hook must always exit 0 so the push is never rejected."""
        assert "exit 0" in self.content, "Hook should exit 0 (non-blocking)"

    def test_handles_timeout(self):
        """Hook must handle test timeout gracefully."""
        assert "timeout" in self.content.lower(), "Hook should handle test timeout"

    def test_captures_exit_code(self):
        """Hook must capture the exit code of the test run."""
        assert "EXIT_CODE" in self.content, "Hook should capture EXIT_CODE"


class TestPostReceiveHookRefFiltering:
    """Verify hook only triggers on branch pushes."""

    @pytest.fixture(autouse=True)
    def _load_hook(self):
        self.content = HOOK_PATH.read_text()

    def test_reads_stdin_refs(self):
        """Hook must read pushed refs from stdin."""
        assert "read" in self.content, "Hook must read refs from stdin"

    def test_filters_branch_pushes(self):
        """Hook should only trigger on refs/heads/* (branches)."""
        assert "refs/heads/" in self.content, (
            "Hook should filter for branch pushes (refs/heads/)"
        )


class TestInstallHookScript:
    """Verify the install_hook.sh helper script."""

    def test_install_script_exists(self):
        """install_hook.sh must exist."""
        assert INSTALL_SCRIPT_PATH.exists(), (
            f"Install script not found at {INSTALL_SCRIPT_PATH}"
        )

    def test_install_script_is_executable(self):
        """install_hook.sh must be executable."""
        mode = INSTALL_SCRIPT_PATH.stat().st_mode
        assert mode & stat.S_IXUSR, "Install script is not executable"

    def test_install_script_has_shebang(self):
        """install_hook.sh must have bash shebang."""
        first_line = INSTALL_SCRIPT_PATH.read_text().splitlines()[0].strip()
        assert first_line == "#!/usr/bin/env bash"

    def test_install_script_copies_hook(self):
        """Install script must copy the hook file."""
        content = INSTALL_SCRIPT_PATH.read_text()
        assert "cp " in content, "Install script must copy the hook"
        assert "chmod +x" in content, "Install script must make hook executable"

    def test_install_script_creates_env_file(self):
        """Install script must create a .env config file."""
        content = INSTALL_SCRIPT_PATH.read_text()
        assert "post-receive.env" in content, (
            "Install script should create post-receive.env"
        )

    def test_install_script_supports_force(self):
        """Install script must support --force flag."""
        content = INSTALL_SCRIPT_PATH.read_text()
        assert "--force" in content, "Install script should support --force"


class TestInstallHookIntegration:
    """Integration test: install hook into a temporary bare repo."""

    def test_install_to_temp_bare_repo(self, tmp_path: Path):
        """Create a temp bare repo, install the hook, verify it works."""
        # Create a bare repo
        bare_repo = tmp_path / "test-repo.git"
        subprocess.run(
            ["git", "init", "--bare", str(bare_repo)],
            check=True,
            capture_output=True,
        )
        assert (bare_repo / "hooks").is_dir()

        # Run install script with --force
        result = subprocess.run(
            [
                "bash", str(INSTALL_SCRIPT_PATH),
                str(bare_repo),
                "--force",
                "--orchestrator-host", "127.0.0.1",
                "--orchestrator-port", "22",
                "--project-dir", "/tmp/test-ai-crm",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Install failed: {result.stderr}"

        # Verify hook was installed
        installed_hook = bare_repo / "hooks" / "post-receive"
        assert installed_hook.exists(), "Hook not installed"
        assert installed_hook.stat().st_mode & stat.S_IXUSR, "Hook not executable"

        # Verify env file was created
        env_file = bare_repo / "hooks" / "post-receive.env"
        assert env_file.exists(), "Env file not created"
        env_content = env_file.read_text()
        assert "127.0.0.1" in env_content
        assert "/tmp/test-ai-crm" in env_content

        # Verify hook content includes env sourcing preamble
        hook_content = installed_hook.read_text()
        assert "post-receive.env" in hook_content, (
            "Installed hook should source the env file"
        )
        assert "pytest" in hook_content, (
            "Installed hook should still contain pytest logic"
        )


class TestHookShellSyntax:
    """Verify hook scripts pass basic shell syntax checking."""

    @pytest.mark.parametrize("script", [HOOK_PATH, INSTALL_SCRIPT_PATH])
    def test_bash_syntax_check(self, script: Path):
        """Run 'bash -n' to verify no syntax errors."""
        result = subprocess.run(
            ["bash", "-n", str(script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Syntax error in {script.name}: {result.stderr}"
        )


class TestOrchestratorConnectivity:
    """Smoke tests for orchestrator connectivity (skipped if unavailable)."""

    def test_pytest_is_available(self):
        """Verify pytest is available — the tool the hook triggers."""
        result = subprocess.run(
            ["python3", "-m", "pytest", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, "pytest not available"
        assert "pytest" in result.stdout

    def test_git_is_available(self):
        """Verify git is available — required for push/pull."""
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 0, "git not available"

    def test_ssh_client_is_available(self):
        """Verify ssh client is installed."""
        result = subprocess.run(
            ["ssh", "-V"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # ssh -V prints to stderr
        assert result.returncode == 0, "ssh client not available"
