#!/usr/bin/env python3
"""Chat script creation and deployment utilities"""

import subprocess
from .docker_ops import exec_in_container
from .colors import print_info, print_success, print_error, print_warning


CHAT_SCRIPT_CONTENT = '''#!/usr/bin/env python3
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

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

WORKSPACE = Path("/workspace")
WORKSPACE.mkdir(exist_ok=True)

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
    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    try:
        client = Groq(api_key=api_key)
    except Exception as e:
        print(f"ERROR: Failed to initialize Groq client: {e}", file=sys.stderr)
        sys.exit(1)

    messages = []

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
            user_input = input("You: ").strip()

            if user_input.lower() in ["exit", "quit"]:
                print("\\nGoodbye!")
                break

            if not user_input:
                continue

            messages.append({
                "role": "user",
                "content": user_input
            })

            while True:
                try:
                    response = client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=messages,
                        tools=TOOLS,
                        tool_choice="auto"
                    )

                    assistant_message = response.choices[0].message

                    if assistant_message.tool_calls:
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

                        for tool_call in assistant_message.tool_calls:
                            func_name = tool_call.function.name
                            func_args = json.loads(tool_call.function.arguments)

                            print(f"\\n[Executing: {func_name}({json.dumps(func_args, ensure_ascii=False)})]")

                            result = execute_tool_call(tool_call)

                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": result
                            })

                            result_data = json.loads(result)
                            if result_data.get("success"):
                                print(f"[Success: {result_data.get('message', 'Done')}]")
                            else:
                                print(f"[Error: {result_data.get('error', 'Unknown error')}]")

                        continue
                    else:
                        print("Assistant: ", end="", flush=True)
                        content = assistant_message.content or ""

                        try:
                            print(content)
                        except UnicodeEncodeError:
                            print(content.encode('utf-8', errors='replace').decode('utf-8'))

                        print()

                        messages.append({
                            "role": "assistant",
                            "content": content
                        })

                        break

                except Exception as e:
                    print(f"\\nERROR: {e}", file=sys.stderr)
                    tb.print_exc(file=sys.stderr)
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


def create_chat_script(container: str) -> bool:
    """
    Create the chat script inside the container.

    Returns:
        True on success, False on failure
    """
    print_info("Creating chat script at /tmp/chat_inside.py...")

    try:
        process = subprocess.Popen(
            ["docker", "exec", "-i", container, "tee", "/tmp/chat_inside.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        stdout, stderr = process.communicate(input=CHAT_SCRIPT_CONTENT)

        if process.returncode != 0:
            print_error("Failed to create chat script")
            if stderr:
                print_error(f"Error: {stderr}")
            return False

        result = exec_in_container(container, ["chmod", "+x", "/tmp/chat_inside.py"])
        if not result or result.returncode != 0:
            print_warning("Failed to make script executable (not critical)")

        print_success("Chat script created successfully")
        return True

    except Exception as e:
        print_error(f"Failed to create chat script: {e}")
        return False
