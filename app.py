#!/usr/bin/env python3
"""
Flask Web Interface for Docker Container Management
Provides web-based file browsing, code execution, and terminal access
"""

from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import subprocess
import json
import os
import threading
import queue
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Global state
current_container = None
workspace_path = "/workspace"
openai_api_key = os.getenv('OPENAI_API_KEY', '')


def run_docker_command(container, cmd, capture_output=True, timeout=30):
    """Execute command in Docker container"""
    try:
        docker_cmd = ["docker", "exec", container] + cmd
        result = subprocess.run(
            docker_cmd,
            capture_output=capture_output,
            text=True,
            timeout=timeout
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')


@app.route('/api/containers', methods=['GET'])
def list_containers():
    """List all running Docker containers"""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return jsonify({"success": False, "error": "Failed to list containers"})
        
        containers = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split('|')
                if len(parts) >= 4:
                    containers.append({
                        "id": parts[0],
                        "name": parts[1],
                        "image": parts[2],
                        "status": parts[3]
                    })
        
        return jsonify({"success": True, "containers": containers})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/attach', methods=['POST'])
def attach_container():
    """Attach to a specific container"""
    global current_container
    
    data = request.json
    container_name = data.get('container')
    
    if not container_name:
        return jsonify({"success": False, "error": "No container specified"})
    
    # Verify container exists
    result = subprocess.run(
        ["docker", "inspect", container_name],
        capture_output=True
    )
    
    if result.returncode != 0:
        return jsonify({"success": False, "error": "Container not found"})
    
    current_container = container_name
    return jsonify({"success": True, "container": container_name})


@app.route('/api/files', methods=['GET'])
def list_files():
    """List files in the workspace"""
    global current_container

    if not current_container:
        return jsonify({"success": False, "error": "No container attached"})

    path = request.args.get('path', '.')

    # Build full path - ensure /workspace exists and is used
    if path == '.' or path == '' or path == '/':
        full_path = "/workspace"
    else:
        # Clean up path and ensure it starts with /workspace
        clean_path = path.lstrip('.').lstrip('/')
        full_path = f"/workspace/{clean_path}" if clean_path else "/workspace"

    # First check if workspace exists, if not create it
    check_result = run_docker_command(
        current_container,
        ["test", "-d", "/workspace"]
    )

    if not check_result["success"]:
        # Create workspace directory
        run_docker_command(
            current_container,
            ["mkdir", "-p", "/workspace"]
        )

    # List directory contents
    result = run_docker_command(
        current_container,
        ["ls", "-la", "--time-style=+%Y-%m-%d %H:%M:%S", full_path]
    )
    
    if not result["success"]:
        return jsonify({"success": False, "error": result.get("error", result.get("stderr"))})
    
    # Parse ls output
    files = []
    lines = result["stdout"].strip().split('\n')[1:]  # Skip 'total' line
    
    for line in lines:
        if not line:
            continue
        
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        
        permissions = parts[0]
        size = parts[4]
        date = parts[5]
        time_str = parts[6]
        name = parts[8]
        
        if name in ['.', '..']:
            continue
        
        is_dir = permissions.startswith('d')
        
        files.append({
            "name": name,
            "type": "directory" if is_dir else "file",
            "size": size if not is_dir else "-",
            "modified": f"{date} {time_str}",
            "permissions": permissions
        })
    
    return jsonify({"success": True, "path": path, "files": files})


@app.route('/api/file/read', methods=['POST'])
def read_file():
    """Read file contents"""
    global current_container
    
    if not current_container:
        return jsonify({"success": False, "error": "No container attached"})
    
    data = request.json
    filepath = data.get('filepath', '')
    
    if not filepath:
        return jsonify({"success": False, "error": "No filepath specified"})
    
    full_path = f"{workspace_path}/{filepath.lstrip('/')}"
    
    result = run_docker_command(
        current_container,
        ["cat", full_path]
    )
    
    if result["success"]:
        return jsonify({
            "success": True,
            "content": result["stdout"],
            "filepath": filepath
        })
    else:
        return jsonify({
            "success": False,
            "error": result.get("error", result.get("stderr"))
        })


@app.route('/api/file/write', methods=['POST'])
def write_file():
    """Write content to file"""
    global current_container
    
    if not current_container:
        return jsonify({"success": False, "error": "No container attached"})
    
    data = request.json
    filepath = data.get('filepath', '')
    content = data.get('content', '')
    
    if not filepath:
        return jsonify({"success": False, "error": "No filepath specified"})
    
    full_path = f"{workspace_path}/{filepath.lstrip('/')}"
    
    # Create parent directories
    parent_dir = str(Path(full_path).parent)
    run_docker_command(
        current_container,
        ["mkdir", "-p", parent_dir]
    )
    
    # Write file using tee
    try:
        process = subprocess.Popen(
            ["docker", "exec", "-i", current_container, "tee", full_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(input=content, timeout=10)
        
        if process.returncode == 0:
            return jsonify({
                "success": True,
                "message": f"File written: {filepath}"
            })
        else:
            return jsonify({
                "success": False,
                "error": stderr or "Failed to write file"
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/file/delete', methods=['POST'])
def delete_file():
    """Delete a file or directory"""
    global current_container
    
    if not current_container:
        return jsonify({"success": False, "error": "No container attached"})
    
    data = request.json
    filepath = data.get('filepath', '')
    
    if not filepath:
        return jsonify({"success": False, "error": "No filepath specified"})
    
    full_path = f"{workspace_path}/{filepath.lstrip('/')}"
    
    result = run_docker_command(
        current_container,
        ["rm", "-rf", full_path]
    )
    
    if result["success"]:
        return jsonify({
            "success": True,
            "message": f"Deleted: {filepath}"
        })
    else:
        return jsonify({
            "success": False,
            "error": result.get("error", result.get("stderr"))
        })


@app.route('/api/execute/python', methods=['POST'])
def execute_python():
    """Execute Python code"""
    global current_container
    
    if not current_container:
        return jsonify({"success": False, "error": "No container attached"})
    
    data = request.json
    code = data.get('code', '')
    
    if not code:
        return jsonify({"success": False, "error": "No code provided"})
    
    result = run_docker_command(
        current_container,
        ["python3", "-c", code],
        timeout=60
    )
    
    return jsonify({
        "success": result["success"],
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "returncode": result.get("returncode", -1)
    })


@app.route('/api/execute/bash', methods=['POST'])
def execute_bash():
    """Execute bash command"""
    global current_container
    
    if not current_container:
        return jsonify({"success": False, "error": "No container attached"})
    
    data = request.json
    command = data.get('command', '')
    
    if not command:
        return jsonify({"success": False, "error": "No command provided"})
    
    result = run_docker_command(
        current_container,
        ["bash", "-c", f"cd {workspace_path} && {command}"],
        timeout=60
    )
    
    return jsonify({
        "success": result["success"],
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "returncode": result.get("returncode", -1)
    })


@app.route('/api/terminal/stream', methods=['POST'])
def terminal_stream():
    """Stream terminal output (Server-Sent Events)"""
    global current_container
    
    if not current_container:
        return jsonify({"success": False, "error": "No container attached"})
    
    def generate():
        data = request.json
        command = data.get('command', '')
        
        if not command:
            yield f"data: {json.dumps({'error': 'No command provided'})}\n\n"
            return
        
        try:
            docker_cmd = ["docker", "exec", "-i", current_container, "bash", "-c", 
                         f"cd {workspace_path} && {command}"]
            
            process = subprocess.Popen(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            for line in iter(process.stdout.readline, ''):
                if line:
                    yield f"data: {json.dumps({'output': line})}\n\n"
            
            process.wait()
            yield f"data: {json.dumps({'done': True, 'returncode': process.returncode})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current status"""
    global current_container

    return jsonify({
        "success": True,
        "attached": current_container is not None,
        "container": current_container
    })


@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    """Handle AI chat requests"""
    global current_container, openai_api_key

    if not current_container:
        return jsonify({"success": False, "error": "No container attached"})

    if not openai_api_key:
        return jsonify({"success": False, "error": "OPENAI_API_KEY not configured. Please add it to .env file"})

    data = request.json
    message = data.get('message', '').strip()

    if not message:
        return jsonify({"success": False, "error": "No message provided"})

    try:
        # Escape single quotes in message for shell
        escaped_message = message.replace("'", "'\"'\"'")

        # Run the chat script with the message as input
        docker_cmd = [
            "docker", "exec",
            "-e", f"OPENAI_API_KEY={openai_api_key}",
            current_container,
            "/opt/venv/bin/python", "/tmp/chat_inside.py"
        ]

        # Create a process that can receive the message via stdin
        process = subprocess.Popen(
            docker_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        # Send message and get response with timeout
        try:
            stdout, stderr = process.communicate(input=message + '\nexit\n', timeout=120)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            return jsonify({"success": False, "error": "Request timed out", "returncode": -1})

        return jsonify({
            "success": process.returncode == 0,
            "response": stdout,
            "error": stderr if stderr else "",
            "returncode": process.returncode
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == '__main__':
    print("Starting Flask web interface...")
    print("Access the interface at: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)