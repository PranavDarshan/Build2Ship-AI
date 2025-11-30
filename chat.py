#!/usr/bin/env python3
"""
Interactive Chat Client
Connects to a Docker container and starts an interactive chat session with LLM
"""

import sys
import subprocess
import getpass
from utils import (
    Colors,
    print_info,
    print_success,
    print_error,
    print_warning
)


def list_running_containers():
    """List all running containers and return them as a list."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=True
        )
        containers = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        return containers
    except Exception as e:
        print_error(f"Failed to list containers: {e}")
        return []


def verify_container_exists(container_name: str) -> bool:
    """Verify that a container exists and is running."""
    try:
        result = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
            check=False
        )
        return result.returncode == 0
    except Exception:
        return False


def run_interactive_chat(container: str, api_key: str) -> bool:
    """
    Run the interactive chat script inside the container.

    Returns:
        True on success, False on failure
    """
    print_info("Starting interactive chat session...")
    print_info("Press Ctrl+D or type 'exit' or 'quit' to end the session")
    print()

    try:
        result = subprocess.run(
            [
                "docker", "exec",
                "-it",
                "-e", f"OPENAI_API_KEY={api_key}",
                container,
                "/opt/venv/bin/python", "/tmp/chat_inside.py"
            ],
            check=False
        )

        print()
        if result.returncode == 0:
            print_success("Chat session ended normally")
            return True
        else:
            print_warning(f"Chat session ended with code {result.returncode}")
            return False

    except Exception as e:
        print_error(f"Failed to run interactive chat: {e}")
        return False


def main():
    """Main execution flow for chat client."""
    print()
    print(f"{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}Docker Container Chat Client{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.END}")
    print()

    container_name = None

    if len(sys.argv) > 1:
        container_name = sys.argv[1]
        print_info(f"Using container: {container_name}")
    else:
        print_info("No container specified. Listing available containers...")
        containers = list_running_containers()

        if not containers:
            print_error("No running containers found")
            print_info("Please run 'python3 setup_container.py' first to create a container")
            sys.exit(1)

        print()
        print(f"{Colors.BOLD}Available Containers:{Colors.END}")
        for i, container in enumerate(containers, 1):
            print(f"  {i}. {container}")
        print()

        try:
            choice = input("Select a container (number or name): ").strip()

            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(containers):
                    container_name = containers[idx]
                else:
                    print_error("Invalid selection")
                    sys.exit(1)
            else:
                container_name = choice
        except (EOFError, KeyboardInterrupt):
            print()
            print_warning("Selection cancelled")
            sys.exit(0)

    print()

    if not verify_container_exists(container_name):
        print_error(f"Container '{container_name}' not found or not running")
        sys.exit(1)

    print_success(f"Container '{container_name}' verified")
    print()

    print(f"{Colors.BOLD}API Key Required{Colors.END}")
    print("Please enter your Groq API key (input will be hidden):")

    try:
        api_key = getpass.getpass("API Key: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        print_warning("API key input cancelled")
        sys.exit(0)

    if not api_key:
        print_error("No API key provided")
        sys.exit(1)

    print()

    run_interactive_chat(container_name, api_key)


if __name__ == "__main__":
    main()
