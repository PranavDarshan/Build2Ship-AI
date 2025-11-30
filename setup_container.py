#!/usr/bin/env python3
"""
Docker Container Setup Script
Sets up a Docker container with Python environment without initializing LLM
"""

import sys
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
    """
    Get yes/no confirmation from user.

    Args:
        prompt: The question to ask
        default: Default value if user just presses Enter

    Returns:
        True for yes, False for no
    """
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


def main():
    """Main execution flow for container setup."""
    print()
    print(f"{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}Docker Container Setup{Colors.END}")
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
    print(f"{Colors.BOLD}Setup Operations:{Colors.END}")
    print("  1. Pull Ubuntu Docker image (if needed)")
    print("  2. Create detached container")
    print("  3. Install Python 3 + venv + pip inside container")
    print("  4. Create virtual environment at /opt/venv")
    print("  5. Install groq and python-dotenv packages")
    print("  6. Deploy chat script to container")
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
        print_success("Container setup completed successfully!")
        print()
        print(f"{Colors.BOLD}Container Status:{Colors.END}")
        print_success(f"Container is running: {container_name}")
        print()
        print(f"{Colors.BOLD}Next Steps:{Colors.END}")
        print(f"  1. To start chatting, run: python3 chat.py {container_name}")
        print(f"  2. Press Ctrl+D or type 'exit' to end the chat session")
        print()
        print_info("The container will remain running. When ready to cleanup:")
        print(f"  • Run: docker rm -f {container_name}")
        print()
        print_info("Waiting for your confirmation...")

        try:
            while True:
                user_input = input(f"Press Enter to continue (or type 'cleanup' to remove container): ").strip().lower()
                if user_input == 'cleanup':
                    if get_user_confirmation("Are you sure you want to delete the container?", default=False):
                        cleanup_container(container_name)
                    break
                elif user_input == '':
                    print_info("Setup complete. Container is ready to use.")
                    break
        except (EOFError, KeyboardInterrupt):
            print()
            print_warning("Received exit signal")
            if get_user_confirmation("Do you want to delete the container?", default=False):
                cleanup_container(container_name)
            else:
                print_info(f"Container {container_name} is still running")

    except KeyboardInterrupt:
        print()
        print_warning("Operation interrupted by user")

        if container_id and get_user_confirmation("Do you want to delete the container?", default=False):
            cleanup_container(container_name)
        else:
            print_info(f"Container {container_name} is still running")

        sys.exit(130)

    except Exception as e:
        print_error(f"Unexpected error: {e}")

        if container_id and get_user_confirmation("Do you want to delete the container?", default=False):
            cleanup_container(container_name)
        else:
            print_info(f"Container {container_name} is still running")

        sys.exit(1)


if __name__ == "__main__":
    main()
