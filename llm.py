#!/usr/bin/env python3
"""
Docker Container Chat Manager
A production-ready script for managing Docker containers with Python chat functionality.
"""

import subprocess
import sys
import os
import random
import string
import getpass
import shutil
from typing import List, Optional, Tuple


class Colors:
    """ANSI color codes for terminal output."""
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_info(msg: str) -> None:
    """Print an info message."""
    print(f"{Colors.BLUE}ℹ {msg}{Colors.END}")


def print_success(msg: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")


def print_warning(msg: str) -> None:
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.END}")


def print_error(msg: str) -> None:
    """Print an error message."""
    print(f"{Colors.RED}✗ {msg}{Colors.END}", file=sys.stderr)


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
    print_info(f"Creating container '{name}' from image '{image}'...")
    print_info(f"Mapping port {port}:5000 (host:container)")
    
    result = run_command([
        "docker", "run",
        "-d",
        "--name", name,
        "-p", f"{port}:5000",  # Port mapping for Flask
        "-v", f"{os.getcwd()}/.env:/app/.env:ro",  # Mount .env file as read-only
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


def get_python_version(container: str) -> Optional[str]:
    """Get the Python version inside the container."""
    result = exec_in_container(container, ["python3", "--version"])
    if result and result.returncode == 0:
        # Output format: "Python 3.X.Y"
        version = result.stdout.strip().split()[1]
        return version.split('.')[:2]  # Return ['3', 'X']
    return None


def setup_python_environment(container: str) -> bool:
    """
    Setup Python and virtual environment inside the container.
    
    Returns:
        True on success, False on failure
    """
    print_info("Installing Python and required packages...")
    
    # Update apt
    print_info("Running apt-get update...")
    if not exec_in_container(container, ["apt-get", "update", "-y"]):
        return False
    
    # Install base packages
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
    
    # Check if python3-distutils is needed
    print_info("Checking Python installation...")
    test_result = exec_in_container(
        container,
        ["python3", "-c", "import distutils"],
        check=False
    )
    
    if test_result and test_result.returncode != 0:
        print_warning("python3-distutils not found, installing...")
        
        # Get Python version
        py_version = get_python_version(container)
        if not py_version:
            print_error("Could not determine Python version")
            return False
        
        version_str = '.'.join(py_version)
        print_info(f"Detected Python version: {version_str}")
        
        # Enable universe repository
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
        
        # Install versioned distutils and venv
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
    
    # Create virtual environment
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
    
    # Install pip packages in venv
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


def create_chat_script(container: str) -> bool:
    """
    Create the chat script inside the container.
    
    Returns:
        True on success, False on failure
    """
    print_info("Creating chat script at /tmp/chat_inside.py...")
    
    chat_script = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive chat script using Groq API with streaming support and tool calling.
Supports file creation, code execution, and file management.
"""

import os
import sys
import io
import json
import subprocess
import traceback as tb
from pathlib import Path
from groq import Groq

# Ensure UTF-8 encoding for stdout/stderr
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Working directory for all file operations
WORKSPACE = Path("/workspace")
WORKSPACE.mkdir(exist_ok=True)

# Tool definitions for the LLM
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create or overwrite a file with the given content. Use this to create .py, .txt, .sh, or any other text files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Path to the file (relative to /workspace). Example: 'script.py' or 'data/notes.txt'"
                    },
                    "content": {
                        "type": "string",
                        "description": "The complete content to write to the file"
                    }
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of an existing file",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Path to the file (relative to /workspace)"
                    }
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files and directories in a given path",
            "parameters": {
                "type": "object",
                "properties": {
                    "dirpath": {
                        "type": "string",
                        "description": "Directory path (relative to /workspace). Use '.' for root workspace."
                    }
                },
                "required": ["dirpath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_python",
            "description": "Execute Python code and return the output. Use this to run Python scripts or test code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute"
                    }
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_bash",
            "description": "Execute a bash command and return the output. Use this for shell commands.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Bash command to execute"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file or directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Path to the file or directory (relative to /workspace)"
                    }
                },
                "required": ["filepath"]
            }
        }
    }
]


def create_file(filepath, content):
    """Create or overwrite a file with content."""
    try:
        full_path = WORKSPACE / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding='utf-8')
        return {"success": True, "message": f"File created: {filepath}", "path": str(full_path)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def read_file(filepath):
    """Read file contents."""
    try:
        full_path = WORKSPACE / filepath
        content = full_path.read_text(encoding='utf-8')
        return {"success": True, "content": content, "size": len(content)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_files(dirpath="."):
    """List files and directories."""
    try:
        full_path = WORKSPACE / dirpath
        items = []
        for item in sorted(full_path.iterdir()):
            rel_path = item.relative_to(WORKSPACE)
            items.append({
                "name": item.name,
                "path": str(rel_path),
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None
            })
        return {"success": True, "items": items, "count": len(items)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def execute_python(code):
    """Execute Python code."""
    try:
        result = subprocess.run(
            ["python3", "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(WORKSPACE)
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Execution timed out (30s limit)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def execute_bash(command):
    """Execute bash command."""
    try:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(WORKSPACE)
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Execution timed out (30s limit)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_file(filepath):
    """Delete a file or directory."""
    try:
        full_path = WORKSPACE / filepath
        if full_path.is_file():
            full_path.unlink()
            return {"success": True, "message": f"File deleted: {filepath}"}
        elif full_path.is_dir():
            import shutil
            shutil.rmtree(full_path)
            return {"success": True, "message": f"Directory deleted: {filepath}"}
        else:
            return {"success": False, "error": "Path does not exist"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Function dispatcher
FUNCTION_MAP = {
    "create_file": create_file,
    "read_file": read_file,
    "list_files": list_files,
    "execute_python": execute_python,
    "execute_bash": execute_bash,
    "delete_file": delete_file
}


def execute_tool_call(tool_call):
    """Execute a tool call and return the result."""
    func_name = tool_call.function.name
    func_args = json.loads(tool_call.function.arguments)
    
    if func_name in FUNCTION_MAP:
        result = FUNCTION_MAP[func_name](**func_args)
        return json.dumps(result, ensure_ascii=False)
    else:
        return json.dumps({"success": False, "error": f"Unknown function: {func_name}"})


def main():
    # Load API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    # Initialize Groq client
    try:
        client = Groq(api_key=api_key)
    except Exception as e:
        print(f"ERROR: Failed to initialize Groq client: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Chat history
    messages = []
    
    # System message explaining capabilities
    system_message = {
        "role": "system",
        "content": """You are a helpful AI assistant with access to file creation and code execution tools inside a Docker container.

You can:
- Create, read, and delete files (Python, text, shell scripts, etc.)
- Execute Python code and bash commands
- List files and directories
- Help users build and test projects

All file operations are relative to /workspace directory.
When creating files, always use clear, well-commented code.
When executing code, explain what you're doing and show the results."""
    }
    messages.append(system_message)
    
    print("=" * 70)
    print("Interactive Chat with Groq (openai/gpt-oss-120b)")
    print("=" * 70)
    print("The AI can create files, execute code, and manage the workspace.")
    print("All files are stored in: /workspace")
    print("Type 'exit', 'quit', or press Ctrl+D to end the session")
    print("=" * 70)
    print()
    
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            # Check for exit commands
            if user_input.lower() in ["exit", "quit"]:
                print("\\nGoodbye!")
                break
            
            if not user_input:
                continue
            
            # Add user message to history
            messages.append({
                "role": "user",
                "content": user_input
            })
            
            # Loop to handle tool calls
            while True:
                try:
                    # Call Groq API with tools
                    response = client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=messages,
                        tools=TOOLS,
                        tool_choice="auto"
                    )
                    
                    assistant_message = response.choices[0].message
                    
                    # Check if there are tool calls
                    if assistant_message.tool_calls:
                        # Add assistant message with tool calls to history
                        messages.append({
                            "role": "assistant",
                            "content": assistant_message.content,
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments
                                    }
                                }
                                for tc in assistant_message.tool_calls
                            ]
                        })
                        
                        # Execute each tool call
                        for tool_call in assistant_message.tool_calls:
                            func_name = tool_call.function.name
                            func_args = json.loads(tool_call.function.arguments)
                            
                            print(f"\\n[Executing: {func_name}({json.dumps(func_args, ensure_ascii=False)})]")
                            
                            result = execute_tool_call(tool_call)
                            
                            # Add tool result to messages
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": result
                            })
                            
                            # Show result
                            result_data = json.loads(result)
                            if result_data.get("success"):
                                print(f"[Success: {result_data.get('message', 'Done')}]")
                            else:
                                print(f"[Error: {result_data.get('error', 'Unknown error')}]")
                        
                        # Continue loop to get final response
                        continue
                    else:
                        # No tool calls, display the response
                        print("Assistant: ", end="", flush=True)
                        content = assistant_message.content or ""
                        
                        try:
                            print(content)
                        except UnicodeEncodeError:
                            print(content.encode('utf-8', errors='replace').decode('utf-8'))
                        
                        print()
                        
                        # Add to history
                        messages.append({
                            "role": "assistant",
                            "content": content
                        })
                        
                        # Break out of tool call loop
                        break
                
                except Exception as e:
                    print(f"\\nERROR: {e}", file=sys.stderr)
                    tb.print_exc(file=sys.stderr)
                    # Remove the failed user message
                    if messages[-1]["role"] == "user":
                        messages.pop()
                    break
        
        except EOFError:
            print("\\n\\nGoodbye!")
            break
        except KeyboardInterrupt:
            print("\\n\\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\\nERROR: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
'''
    
    # Write script to container using docker exec with stdin
    try:
        process = subprocess.Popen(
            ["docker", "exec", "-i", container, "tee", "/tmp/chat_inside.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(input=chat_script)
        
        if process.returncode != 0:
            print_error("Failed to create chat script")
            if stderr:
                print_error(f"Error: {stderr}")
            return False
        
        # Make script executable
        result = exec_in_container(container, ["chmod", "+x", "/tmp/chat_inside.py"])
        if not result or result.returncode != 0:
            print_warning("Failed to make script executable (not critical)")
        
        print_success("Chat script created successfully")
        return True
        
    except Exception as e:
        print_error(f"Failed to create chat script: {e}")
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
        # Run docker exec interactively
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
    """Main execution flow."""
    print()
    print(f"{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}Docker Container Chat Manager{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.END}")
    print()
    
    # Check Docker installation
    print_info("Checking Docker installation...")
    if not check_docker_installed():
        print_error("Docker is not installed or not accessible")
        print_error("Please install Docker and ensure it's running")
        sys.exit(1)
    
    print_success("Docker is installed and accessible")
    print()
    
    # Configuration
    image = "ubuntu:latest"
    container_name = generate_container_name()
    
    # Display planned operations
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
    
    # Ask for confirmation
    if not get_user_confirmation("Do you want to proceed?", default=True):
        print_info("Operation cancelled by user")
        sys.exit(0)
    
    print()
    container_id = None
    
    try:
        # Pull image
        if not pull_docker_image(image):
            print_error("Failed to pull Docker image")
            sys.exit(1)
        
        print()
        
        # Create container
        container_id = create_container(image, container_name)
        if not container_id:
            print_error("Failed to create container")
            sys.exit(1)
        
        print()
        
        # Setup Python environment
        if not setup_python_environment(container_name):
            print_error("Failed to setup Python environment")
            sys.exit(1)
        
        print()
        
        # Create chat script
        if not create_chat_script(container_name):
            print_error("Failed to create chat script")
            sys.exit(1)
        
        print()
        
        # Get API key from user
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
        
        # Run interactive chat
        run_interactive_chat(container_name, api_key)
        
        print()
        
        # Cleanup prompt
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