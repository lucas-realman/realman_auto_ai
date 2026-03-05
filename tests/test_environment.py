"""
Tests for environment setup and validation.

Validates Python version, CUDA availability, and system resources.
"""

import pytest
import subprocess
import sys
from pathlib import Path

# Add orchestrator to path
sys.path.insert(0, str(Path(__file__).parent.parent / "orchestrator"))

from setup_env import (
    PythonValidator,
    CudaValidator,
    SystemValidator,
    EnvironmentValidator,
)


class TestPythonValidator:
    """Tests for Python version validation."""

    def test_python_version_check(self):
        """Test Python version is 3.11+."""
        valid, msg = PythonValidator.check_version()
        assert valid, f"Python version check failed: {msg}"
        assert "3.11" in msg or "3.12" in msg or "3.13" in msg

    def test_python_version_message_format(self):
        """Test version message format."""
        valid, msg = PythonValidator.check_version()
        assert "Python" in msg
        assert "." in msg  # Has version separator


class TestCudaValidator:
    """Tests for CUDA and GPU validation."""

    def test_nvidia_smi_available(self):
        """Test nvidia-smi is available."""
        valid, msg = CudaValidator.check_nvidia_smi()
        assert valid, f"CUDA check failed: {msg}"
        assert "CUDA" in msg or "GPU" in msg

    def test_gpu_count_non_negative(self):
        """Test GPU count is non-negative."""
        count, msg = CudaValidator.check_gpu_count()
        assert count >= 0, f"GPU count should be non-negative: {msg}"
        assert "GPU" in msg or "available" in msg

    def test_gpu_count_matches_nvidia_smi(self):
        """Test GPU count matches nvidia-smi output."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--list-gpus"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                expected_count = len(result.stdout.strip().split('\n'))
                actual_count, _ = CudaValidator.check_gpu_count()
                assert actual_count == expected_count
        except FileNotFoundError:
            pytest.skip("nvidia-smi not available")


class TestSystemValidator:
    """Tests for system resource validation."""

    def test_disk_space_check(self):
        """Test disk space check returns valid result."""
        valid, msg = SystemValidator.check_disk_space()
        assert isinstance(valid, bool)
        assert "Disk" in msg or "space" in msg

    def test_memory_check(self):
        """Test memory check returns valid result."""
        valid, msg = SystemValidator.check_memory()
        assert isinstance(valid, bool)
        assert "Memory" in msg or "GB" in msg

    def test_disk_space_sufficient(self):
        """Test disk space is sufficient (at least 10GB)."""
        valid, msg = SystemValidator.check_disk_space(min_gb=10)
        assert valid, f"Insufficient disk space: {msg}"


class TestEnvironmentValidator:
    """Tests for full environment validation."""

    def test_validator_initialization(self):
        """Test validator initializes correctly."""
        validator = EnvironmentValidator()
        assert validator.results == {}
        assert validator.errors == []

    def test_validate_all_runs_without_error(self):
        """Test validate_all completes without exception."""
        validator = EnvironmentValidator()
        try:
            result = validator.validate_all()
            assert isinstance(result, bool)
        except Exception as e:
            pytest.fail(f"validate_all raised exception: {e}")

    def test_results_populated_after_validation(self):
        """Test results are populated after validation."""
        validator = EnvironmentValidator()
        validator.validate_all()
        assert len(validator.results) > 0
        assert 'python_version' in validator.results
        assert 'cuda' in validator.results

    def test_python_version_passes(self):
        """Test Python version validation passes."""
        validator = EnvironmentValidator()
        validator._validate_python()
        assert 'python_version' in validator.results
        # Should not have Python errors if running this test
        python_errors = [e for e in validator.errors if 'Python' in e]
        assert len(python_errors) == 0

    def test_to_json_format(self):
        """Test JSON export format."""
        validator = EnvironmentValidator()
        validator.validate_all()
        json_str = validator.to_json()
        
        import json
        data = json.loads(json_str)
        assert 'results' in data
        assert 'errors' in data
        assert 'passed' in data
        assert isinstance(data['passed'], bool)

    def test_print_report_no_exception(self):
        """Test print_report doesn't raise exception."""
        validator = EnvironmentValidator()
        validator.validate_all()
        try:
            validator.print_report()
        except Exception as e:
            pytest.fail(f"print_report raised exception: {e}")


class TestEnvironmentIntegration:
    """Integration tests for full environment setup."""

    def test_full_environment_check(self):
        """Test complete environment validation."""
        validator = EnvironmentValidator()
        result = validator.validate_all()
        
        # At minimum, Python should be valid
        assert 'python_version' in validator.results
        
        # CUDA check should run (may fail if no GPU, but shouldn't crash)
        assert 'cuda' in validator.results

    def test_environment_reproducible(self):
        """Test environment checks are reproducible."""
        validator1 = EnvironmentValidator()
        validator1.validate_all()
        
        validator2 = EnvironmentValidator()
        validator2.validate_all()
        
        # Results should be consistent
        assert validator1.results['python_version'] == validator2.results['python_version']
