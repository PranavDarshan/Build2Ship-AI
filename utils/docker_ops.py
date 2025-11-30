#!/usr/bin/env python3
"""Docker operations and container management utilities"""

import subprocess
import random
import string
from typing import List, Optional
from .colors import print_info, print_success, print_error, print_warning


def run_command(cmd: List[str], capture_output: bool = True, check: bool = True) -> Optional[subprocess.CompletedProcess]:
    """
    Run a command and handle errors gracefully.

    Args:
        cmd: Command as a list of arguments
        capture_output: Whether to capture stdout/stderr
        check: Whether to raise on non-zero exit

    Returns:
        CompletedProcess object or None on error
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            check=check
        )
        return result
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed: {' '.join(cmd)}")
        if e.stderr:
            print_error(f"Error: {e.stderr}")
        return None
    except FileNotFoundError:
        print_error(f"Command not found: {cmd[0]}")
        return None


def check_docker_installed() -> bool:
    """Check if Docker is installed and accessible."""
    result = run_command(["docker", "--version"], check=False)
    return result is not None and result.returncode == 0


def generate_container_name() -> str:
    """Generate a random container name."""
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"chat-container-{suffix}"


def pull_docker_image(image: str) -> bool:
    """Pull a Docker image."""
    print_info(f"Pulling Docker image: {image}")
    result = run_command(["docker", "pull", image], capture_output=False)
    return result is not None and result.returncode == 0


def create_container(image: str, name: str, port: int = 5000) -> Optional[str]:
    """
    Create a detached Docker container.

    Returns:
        Container ID or None on failure
    """
    import os

    print_info(f"Creating container '{name}' from image '{image}'...")
    print_info(f"Mapping port {port}:5000 (host:container)")

    result = run_command([
        "docker", "run",
        "-d",
        "--name", name,
        "-p", f"{port}:5000",
        "-v", f"{os.getcwd()}/.env:/app/.env:ro",
        image,
        "sleep", "infinity"
    ])

    if result and result.returncode == 0:
        container_id = result.stdout.strip()
        print_success(f"Container created with ID: {container_id}")
        return container_id
    return None


def exec_in_container(container: str, cmd: List[str], capture_output: bool = True, check: bool = True) -> Optional[subprocess.CompletedProcess]:
    """Execute a command inside the container."""
    docker_cmd = ["docker", "exec", container] + cmd
    return run_command(docker_cmd, capture_output=capture_output, check=check)


def cleanup_container(container: str) -> bool:
    """
    Remove the Docker container.

    Returns:
        True on success, False on failure
    """
    print_info(f"Removing container '{container}'...")
    result = run_command(["docker", "rm", "-f", container], capture_output=False)

    if result and result.returncode == 0:
        print_success("Container removed successfully")
        return True
    else:
        print_error("Failed to remove container")
        return False
