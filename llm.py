#!/usr/bin/env python3
"""
Legacy LLM Script - Backward Compatibility Wrapper
This script maintains backward compatibility by providing the original all-in-one functionality.
For better modularity, use setup_container.py and chat.py separately.
"""

import sys
import getpass
from utils import (
    Colors,
    print_info,
    print_success,
    print_error,
    print_warning,
    check_docker_installed,
    generate_container_name,
    pull_docker_image,
    create_container,
    setup_python_environment,
    create_chat_script,
    cleanup_container
)


def get_user_confirmation(prompt: str, default: bool = False) -> bool:
    """Get yes/no confirmation from user."""
    default_str = "Y/n" if default else "y/N"

    while True:
        try:
            response = input(f"{prompt} [{default_str}]: ").strip().lower()

            if not response:
                return default

            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            else:
                print_warning("Please answer 'y' or 'n'")

        except (EOFError, KeyboardInterrupt):
            print()
            return False


def run_interactive_chat(container: str, api_key: str) -> bool:
    """Run the interactive chat script inside the container."""
    import subprocess

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
    """Main execution flow."""
    print()
    print(f"{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}Docker Container Chat Manager{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.END}")
    print()

    print_info("Checking Docker installation...")
    if not check_docker_installed():
        print_error("Docker is not installed or not accessible")
        print_error("Please install Docker and ensure it's running")
        sys.exit(1)

    print_success("Docker is installed and accessible")
    print()

    image = "ubuntu:latest"
    container_name = generate_container_name()

    print(f"{Colors.BOLD}Configuration:{Colors.END}")
    print(f"  Docker Image:    {image}")
    print(f"  Container Name:  {container_name}")
    print()
    print(f"{Colors.BOLD}Planned Operations:{Colors.END}")
    print("  1. Pull Ubuntu Docker image (if needed)")
    print("  2. Create detached container running 'sleep infinity'")
    print("  3. Install Python 3 + venv + pip inside container")
    print("  4. Create virtual environment at /opt/venv")
    print("  5. Install groq and python-dotenv packages")
    print("  6. Copy chat script into container")
    print("  7. Run interactive chat session")
    print("  8. Cleanup (optional)")
    print()

    if not get_user_confirmation("Do you want to proceed?", default=True):
        print_info("Operation cancelled by user")
        sys.exit(0)

    print()
    container_id = None

    try:
        if not pull_docker_image(image):
            print_error("Failed to pull Docker image")
            sys.exit(1)

        print()

        container_id = create_container(image, container_name)
        if not container_id:
            print_error("Failed to create container")
            sys.exit(1)

        print()

        if not setup_python_environment(container_name):
            print_error("Failed to setup Python environment")
            sys.exit(1)

        print()

        if not create_chat_script(container_name):
            print_error("Failed to create chat script")
            sys.exit(1)

        print()

        print(f"{Colors.BOLD}API Key Required{Colors.END}")
        print("Please enter your Groq API key (input will be hidden):")

        try:
            api_key = getpass.getpass("API Key: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print_warning("API key input cancelled")
            api_key = None

        if not api_key:
            print_error("No API key provided")
            sys.exit(1)

        print()

        run_interactive_chat(container_name, api_key)

        print()

        print(f"{Colors.BOLD}Cleanup{Colors.END}")
        if get_user_confirmation("Do you want to delete the container?", default=True):
            cleanup_container(container_name)
        else:
            print_info("Container kept running")
            print_info(f"To remove it later, run: docker rm -f {container_name}")

    except KeyboardInterrupt:
        print()
        print_warning("Operation interrupted by user")

        if container_id:
            print()
            if get_user_confirmation("Do you want to delete the container?", default=True):
                cleanup_container(container_name)
            else:
                print_info(f"To remove it later, run: docker rm -f {container_name}")

        sys.exit(130)

    except Exception as e:
        print_error(f"Unexpected error: {e}")

        if container_id:
            print()
            print_warning("Container may still be running")
            if get_user_confirmation("Do you want to delete the container?", default=True):
                cleanup_container(container_name)
            else:
                print_info(f"To remove it later, run: docker rm -f {container_name}")

        sys.exit(1)

    print()
    print_success("All operations completed successfully!")
    print()


if __name__ == "__main__":
    main()
