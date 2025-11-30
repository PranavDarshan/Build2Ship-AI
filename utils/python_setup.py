#!/usr/bin/env python3
"""Python environment setup utilities for Docker containers"""

from typing import Optional
from .docker_ops import exec_in_container
from .colors import print_info, print_success, print_error, print_warning


def get_python_version(container: str) -> Optional[str]:
    """Get the Python version inside the container."""
    result = exec_in_container(container, ["python3", "--version"])
    if result and result.returncode == 0:
        version = result.stdout.strip().split()[1]
        return version.split('.')[:2]
    return None


def setup_python_environment(container: str) -> bool:
    """
    Setup Python and virtual environment inside the container.

    Returns:
        True on success, False on failure
    """
    print_info("Installing Python and required packages...")

    print_info("Running apt-get update...")
    if not exec_in_container(container, ["apt-get", "update", "-y"]):
        return False

    print_info("Installing python3, python3-venv, python3-pip, curl...")
    packages = ["python3", "python3-venv", "python3-pip", "curl"]
    result = exec_in_container(
        container,
        ["apt-get", "install", "-y"] + packages,
        capture_output=False
    )

    if not result or result.returncode != 0:
        print_error("Failed to install base packages")
        return False

    print_info("Checking Python installation...")
    test_result = exec_in_container(
        container,
        ["python3", "-c", "import distutils"],
        check=False
    )

    if test_result and test_result.returncode != 0:
        print_warning("python3-distutils not found, installing...")

        py_version = get_python_version(container)
        if not py_version:
            print_error("Could not determine Python version")
            return False

        version_str = '.'.join(py_version)
        print_info(f"Detected Python version: {version_str}")

        print_info("Enabling universe repository...")
        exec_in_container(
            container,
            ["apt-get", "install", "-y", "software-properties-common"],
            capture_output=False
        )
        exec_in_container(
            container,
            ["add-apt-repository", "-y", "universe"],
            capture_output=False
        )
        exec_in_container(container, ["apt-get", "update", "-y"])

        distutils_pkg = f"python{version_str}-distutils"
        venv_pkg = f"python{version_str}-venv"
        print_info(f"Installing {distutils_pkg} and {venv_pkg}...")

        result = exec_in_container(
            container,
            ["apt-get", "install", "-y", distutils_pkg, venv_pkg],
            capture_output=False,
            check=False
        )

        if not result or result.returncode != 0:
            print_warning(f"Could not install {distutils_pkg}, continuing anyway...")

    print_info("Creating virtual environment at /opt/venv...")
    result = exec_in_container(
        container,
        ["python3", "-m", "venv", "/opt/venv"],
        capture_output=False
    )

    if not result or result.returncode != 0:
        print_error("Failed to create virtual environment")
        return False

    print_success("Virtual environment created successfully")

    print_info("Installing pip packages (groq, python-dotenv) in virtual environment...")
    result = exec_in_container(
        container,
        ["/opt/venv/bin/pip", "install", "groq", "python-dotenv"],
        capture_output=False
    )

    if not result or result.returncode != 0:
        print_error("Failed to install pip packages")
        return False

    print_success("Python environment setup completed")
    return True
