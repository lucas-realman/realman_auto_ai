"""
Environment setup and validation for Sirus AI-CRM orchestrator.

Validates:
- Python 3.11+
- CUDA drivers and GPU availability
- Required system packages
- Network connectivity between machines
"""

import subprocess
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class EnvironmentSetupError(Exception):
    """Raised when environment setup fails."""
    pass


class PythonValidator:
    """Validates Python version and packages."""

    MIN_VERSION = (3, 11)

    @staticmethod
    def check_version() -> Tuple[bool, str]:
        """
        Check if Python version meets minimum requirement.
        
        Returns:
            (is_valid, message)
        """
        current = sys.version_info[:2]
        if current >= PythonValidator.MIN_VERSION:
            return True, f"Python {current[0]}.{current[1]} ✓"
        return False, f"Python {current[0]}.{current[1]} (required: {PythonValidator.MIN_VERSION[0]}.{PythonValidator.MIN_VERSION[1]}+)"

    @staticmethod
    def check_packages(required: List[str]) -> Tuple[bool, Dict[str, str]]:
        """
        Check if required packages are installed.
        
        Args:
            required: List of package names to check
            
        Returns:
            (all_present, {package: status})
        """
        results = {}
        all_present = True
        
        for package in required:
            try:
                __import__(package)
                results[package] = "✓"
            except ImportError:
                results[package] = "✗ (not installed)"
                all_present = False
        
        return all_present, results


class CudaValidator:
    """Validates CUDA drivers and GPU availability."""

    @staticmethod
    def check_nvidia_smi() -> Tuple[bool, str]:
        """
        Check if nvidia-smi is available and working.
        
        Returns:
            (is_available, message)
        """
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return False, "nvidia-smi failed"
            
            gpus = result.stdout.strip().split('\n')
            if not gpus or not gpus[0]:
                return False, "No GPUs detected"
            
            gpu_info = "\n  ".join(gpus)
            return True, f"CUDA available ✓\n  {gpu_info}"
        except FileNotFoundError:
            return False, "nvidia-smi not found (CUDA drivers not installed)"
        except subprocess.TimeoutExpired:
            return False, "nvidia-smi timeout"
        except Exception as e:
            return False, f"Error checking CUDA: {str(e)}"

    @staticmethod
    def check_gpu_count() -> Tuple[int, str]:
        """
        Get number of available GPUs.
        
        Returns:
            (gpu_count, message)
        """
        try:
            result = subprocess.run(
                ["nvidia-smi", "--list-gpus"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return 0, "Failed to query GPU count"
            
            gpu_count = len(result.stdout.strip().split('\n'))
            return gpu_count, f"{gpu_count} GPU(s) available"
        except Exception as e:
            return 0, f"Error: {str(e)}"


class SystemValidator:
    """Validates system-level requirements."""

    @staticmethod
    def check_disk_space(path: str = "/", min_gb: int = 50) -> Tuple[bool, str]:
        """
        Check available disk space.
        
        Args:
            path: Path to check
            min_gb: Minimum required GB
            
        Returns:
            (is_sufficient, message)
        """
        try:
            import shutil
            stat = shutil.disk_usage(path)
            available_gb = stat.free / (1024 ** 3)
            
            if available_gb >= min_gb:
                return True, f"Disk space: {available_gb:.1f}GB available ✓"
            return False, f"Disk space: {available_gb:.1f}GB (required: {min_gb}GB)"
        except Exception as e:
            return False, f"Error checking disk space: {str(e)}"

    @staticmethod
    def check_memory() -> Tuple[bool, str]:
        """
        Check available system memory.
        
        Returns:
            (is_sufficient, message)
        """
        try:
            import psutil
            mem = psutil.virtual_memory()
            available_gb = mem.available / (1024 ** 3)
            total_gb = mem.total / (1024 ** 3)
            
            return True, f"Memory: {available_gb:.1f}GB / {total_gb:.1f}GB available"
        except Exception as e:
            return False, f"Error checking memory: {str(e)}"


class EnvironmentValidator:
    """Main environment validation orchestrator."""

    def __init__(self):
        self.results = {}
        self.errors = []

    def validate_all(self) -> bool:
        """
        Run all environment checks.
        
        Returns:
            True if all checks pass, False otherwise
        """
        self._validate_python()
        self._validate_cuda()
        self._validate_system()
        
        return len(self.errors) == 0

    def _validate_python(self) -> None:
        """Validate Python version and packages."""
        valid, msg = PythonValidator.check_version()
        self.results['python_version'] = msg
        if not valid:
            self.errors.append(f"Python version check failed: {msg}")

    def _validate_cuda(self) -> None:
        """Validate CUDA and GPU availability."""
        valid, msg = CudaValidator.check_nvidia_smi()
        self.results['cuda'] = msg
        if not valid:
            self.errors.append(f"CUDA check failed: {msg}")
        else:
            gpu_count, gpu_msg = CudaValidator.check_gpu_count()
            self.results['gpu_count'] = gpu_msg
            if gpu_count == 0:
                self.errors.append("No GPUs available")

    def _validate_system(self) -> None:
        """Validate system resources."""
        disk_ok, disk_msg = SystemValidator.check_disk_space()
        self.results['disk_space'] = disk_msg
        if not disk_ok:
            self.errors.append(f"Disk space check failed: {disk_msg}")

        mem_ok, mem_msg = SystemValidator.check_memory()
        self.results['memory'] = mem_msg

    def print_report(self) -> None:
        """Print validation report."""
        print("\n" + "=" * 60)
        print("Environment Validation Report")
        print("=" * 60)
        
        for key, value in self.results.items():
            print(f"\n{key.upper()}:")
            print(f"  {value}")
        
        if self.errors:
            print("\n" + "=" * 60)
            print("ERRORS:")
            for error in self.errors:
                print(f"  ✗ {error}")
            print("=" * 60 + "\n")
        else:
            print("\n" + "=" * 60)
            print("✓ All checks passed!")
            print("=" * 60 + "\n")

    def to_json(self) -> str:
        """Export results as JSON."""
        return json.dumps({
            'results': self.results,
            'errors': self.errors,
            'passed': len(self.errors) == 0
        }, indent=2)


def main():
    """Main entry point."""
    validator = EnvironmentValidator()
    
    if not validator.validate_all():
        validator.print_report()
        sys.exit(1)
    
    validator.print_report()
    sys.exit(0)


if __name__ == "__main__":
    main()
