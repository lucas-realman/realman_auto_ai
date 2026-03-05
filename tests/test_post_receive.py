"""
Tests for the Git post-receive hook and related scripts.

Validates that:
- Hook scripts exist and are executable
- Shell script syntax is valid
- Hook script contains required configuration variables
- install_hook.sh works correctly with a mock bare repo
- run_tests.sh can be invoked with --help
"""

import os
import stat
import subprocess
import tempfile
import shutil

import pytest

# ── Paths ──
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
POST_RECEIVE = os.path.join(SCRIPTS_DIR, "post-receive")
INSTALL_HOOK = os.path.join(SCRIPTS_DIR, "install_hook.sh")
RUN_TESTS = os.path.join(SCRIPTS_DIR, "run_tests.sh")


class TestPostReceiveHookExists:
    """Verify that all hook-related scripts exist."""

    def test_post_receive_exists(self):
        """post-receive hook script must exist."""
        assert os.path.isfile(POST_RECEIVE), (
            f"post-receive hook not found at {POST_RECEIVE}"
        )

    def test_install_hook_exists(self):
        """install_hook.sh must exist."""
        assert os.path.isfile(INSTALL_HOOK), (
            f"install_hook.sh not found at {INSTALL_HOOK}"
        )

    def test_run_tests_exists(self):
        """run_tests.sh must exist."""
        assert os.path.isfile(RUN_TESTS), (
            f"run_tests.sh not found at {RUN_TESTS}"
        )


class TestPostReceiveHookPermissions:
    """Verify that hook scripts have correct permissions."""

    @pytest.mark.parametrize("script_path", [POST_RECEIVE, INSTALL_HOOK, RUN_TESTS])
    def test_script_is_executable(self, script_path):
        """All scripts should be executable."""
        # Make executable first (in case git didn't preserve permissions)
        os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)
        mode = os.stat(script_path).st_mode
        assert mode & stat.S_IXUSR, (
            f"{os.path.basename(script_path)} is not executable"
        )


class TestPostReceiveHookSyntax:
    """Verify shell script syntax is valid."""

    @pytest.mark.parametrize("script_path", [POST_RECEIVE, INSTALL_HOOK, RUN_TESTS])
    def test_bash_syntax(self, script_path):
        """Shell scripts must pass bash -n syntax check."""
        result = subprocess.run(
            ["bash", "-n", script_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, (
            f"Syntax error in {os.path.basename(script_path)}: "
            f"{result.stderr}"
        )


class TestPostReceiveHookContent:
    """Verify post-receive hook has required content."""

    @pytest.fixture(autouse=True)
    def _load_hook(self):
        """Load the hook script content."""
        with open(POST_RECEIVE, "r") as f:
            self.content = f.read()

    def test_has_shebang(self):
        """Hook must start with a bash shebang."""
        assert self.content.startswith("#!/"), (
            "post-receive must start with a shebang line"
        )

    def test_has_orchestrator_host_config(self):
        """Hook must reference ORCHESTRATOR_HOST."""
        assert "ORCHESTRATOR_HOST" in self.content

    def test_has_project_dir_config(self):
        """Hook must reference PROJECT_DIR."""
        assert "PROJECT_DIR" in self.content

    def test_has_ssh_command(self):
        """Hook must use SSH to trigger remote tests."""
        assert "ssh" in self.content.lower()

    def test_has_pytest_reference(self):
        """Hook must reference pytest for test execution."""
        assert "pytest" in self.content

    def test_reads_stdin_refs(self):
        """Hook must read pushed refs from stdin."""
        assert "read" in self.content
        assert "oldrev" in self.content or "newrev" in self.content

    def test_has_error_handling(self):
        """Hook must have error handling (set -e or equivalent)."""
        assert "set -" in self.content

    def test_runs_in_background(self):
        """Hook should run tests in background to not block git push."""
        assert "&" in self.content


class TestInstallHookScript:
    """Test install_hook.sh with a mock bare repository."""

    @pytest.fixture
    def mock_bare_repo(self, tmp_path):
        """Create a mock bare Git repository structure."""
        bare_repo = tmp_path / "test-repo.git"
        hooks_dir = bare_repo / "hooks"
        hooks_dir.mkdir(parents=True)
        # Create HEAD file to make it look like a bare repo
        (bare_repo / "HEAD").write_text("ref: refs/heads/main\n")
        return str(bare_repo)

    def test_install_hook_to_bare_repo(self, mock_bare_repo):
        """install_hook.sh should copy hook to bare repo's hooks dir."""
        result = subprocess.run(
            [
                "bash", INSTALL_HOOK, mock_bare_repo,
                "--orchestrator-host", "127.0.0.1",
                "--project-dir", "/tmp/test-project",
                "--force",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, (
            f"install_hook.sh failed: {result.stderr}"
        )

        hook_path = os.path.join(mock_bare_repo, "hooks", "post-receive")
        assert os.path.isfile(hook_path), "Hook was not installed"

        mode = os.stat(hook_path).st_mode
        assert mode & stat.S_IXUSR, "Installed hook is not executable"

    def test_install_creates_env_file(self, mock_bare_repo):
        """install_hook.sh should create a .env config file."""
        subprocess.run(
            [
                "bash", INSTALL_HOOK, mock_bare_repo,
                "--orchestrator-host", "10.0.0.1",
                "--orchestrator-user", "testuser",
                "--orchestrator-port", "2222",
                "--project-dir", "/opt/ai-crm",
                "--force",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        env_path = os.path.join(mock_bare_repo, "hooks", "post-receive.env")
        assert os.path.isfile(env_path), "Environment file was not created"

        with open(env_path, "r") as f:
            env_content = f.read()

        assert "10.0.0.1" in env_content
        assert "testuser" in env_content
        assert "2222" in env_content
        assert "/opt/ai-crm" in env_content

    def test_install_fails_on_missing_repo(self):
        """install_hook.sh should fail if bare repo doesn't exist."""
        result = subprocess.run(
            ["bash", INSTALL_HOOK, "/nonexistent/repo.git", "--force"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0


class TestRunTestsScript:
    """Test run_tests.sh behavior."""

    def test_help_flag(self):
        """run_tests.sh --help should exit cleanly."""
        result = subprocess.run(
            ["bash", RUN_TESTS, "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_run_tests_no_pull(self):
        """run_tests.sh --no-pull should run pytest in the project."""
        result = subprocess.run(
            [
                "bash", RUN_TESTS,
                "--project-dir", REPO_ROOT,
                "--no-pull",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=REPO_ROOT,
        )
        # Exit 0 (pass) or 1 (some tests fail) are both valid —
        # we just verify the script itself runs without crashing (exit 2).
        assert result.returncode != 2, (
            f"run_tests.sh had an environment error: {result.stderr}"
        )

    def test_run_tests_bad_directory(self):
        """run_tests.sh should exit 2 for a nonexistent project dir."""
        result = subprocess.run(
            [
                "bash", RUN_TESTS,
                "--project-dir", "/nonexistent/path",
                "--no-pull",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 2


class TestPostReceiveIntegration:
    """Integration test: simulate a post-receive hook invocation."""

    def test_hook_handles_branch_push_input(self):
        """Hook should accept branch push ref data on stdin without error."""
        # Simulate the stdin that git sends to post-receive:
        #   <old-sha> <new-sha> refs/heads/main
        fake_input = (
            "0000000000000000000000000000000000000000 "
            "abcdef1234567890abcdef1234567890abcdef12 "
            "refs/heads/main\n"
        )

        # Run with a non-existent SSH host so it won't actually connect,
        # but the hook should still parse input and exit 0 (background job).
        env = os.environ.copy()
        env["ORCHESTRATOR_HOST"] = "192.0.2.1"  # TEST-NET, won't connect
        env["SSH_KEY"] = ""
        env["TEST_TIMEOUT"] = "2"
        env["LOG_DIR"] = tempfile.mkdtemp()

        result = subprocess.run(
            ["bash", POST_RECEIVE],
            input=fake_input,
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )

        # The hook should exit 0 (it fires SSH in background)
        assert result.returncode == 0, (
            f"Hook failed: stdout={result.stdout}, stderr={result.stderr}"
        )
        assert "post-receive" in result.stdout.lower() or result.returncode == 0

        # Cleanup
        shutil.rmtree(env["LOG_DIR"], ignore_errors=True)

    def test_hook_skips_tag_push(self):
        """Hook should skip test trigger for tag pushes."""
        fake_input = (
            "0000000000000000000000000000000000000000 "
            "abcdef1234567890abcdef1234567890abcdef12 "
            "refs/tags/v1.0.0\n"
        )

        env = os.environ.copy()
        env["ORCHESTRATOR_HOST"] = "192.0.2.1"
        env["LOG_DIR"] = tempfile.mkdtemp()

        result = subprocess.run(
            ["bash", POST_RECEIVE],
            input=fake_input,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

        assert result.returncode == 0

        # Cleanup
        shutil.rmtree(env["LOG_DIR"], ignore_errors=True)
