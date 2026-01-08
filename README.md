# SRaaS - Serverless Runner as a Service

A lightweight, secure sandbox execution environment for running Python functions in isolated Docker containers with resource limits and monitoring. Think AWS Lambda, but local and containerized.

## 🌟 Overview

SRaaS provides a secure execution environment for running untrusted Python code with:
- **Isolated Execution**: Each function runs in a dedicated Docker container
- **Resource Limits**: CPU, memory, and PID constraints prevent resource exhaustion
- **Security Hardening**: Capabilities dropped, no new privileges, read-only filesystem
- **Timeout Protection**: 10-second execution timeout prevents infinite loops
- **Comprehensive Logging**: Captures stdout, stderr, and logging output
- **GUI Interface**: Easy-to-use desktop application for testing functions

## 🏗️ Architecture

```
┌─────────────────┐
│   GUI (app.py)  │
│  CustomTkinter  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│   Docker Container              │
│  ┌──────────────────────────┐   │
│  │  runner.py               │   │
│  │  (Orchestrator)          │   │
│  └──────────┬───────────────┘   │
│             │                    │
│             ▼                    │
│  ┌──────────────────────────┐   │
│  │  user_runner.py          │   │
│  │  (Function Executor)     │   │
│  └──────────┬───────────────┘   │
│             │                    │
│             ▼                    │
│  ┌──────────────────────────┐   │
│  │  User Function           │   │
│  │  (main.py)               │   │
│  └──────────────────────────┘   │
└─────────────────────────────────┘
```

## 📋 Prerequisites

- Docker
- Python 3.11+
- pip

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Build the Runner Image

```bash
docker build -t sraas-runner .
```

### 3. Launch the GUI

```bash
python app.py
```

### 4. Run Your First Function

1. **Create a handler function** (e.g., `main.py`):
```python
def handler(event, context):
    return {
        "quotient": event["a"] / event["b"]
    }
```

2. **Create an input JSON** (e.g., `data.json`):
```json
{
  "version": "v1",
  "context": {},
  "event": {
    "a": 4,
    "b": 1
  }
}
```

3. In the GUI:
   - Set handler path: `main.handler`
   - Select your `main.py` file
   - Select your `data.json` file
   - Click "Run Container"

## 📁 Project Structure

```
SRaaS/
├── app.py              # GUI application (CustomTkinter)
├── runner.py           # Subprocess orchestrator with timeout
├── user_runner.py      # User function executor with logging capture
├── Dockerfile          # Container image definition
├── requirements.txt    # Python dependencies
├── main.py            # Example handler function
└── data.json          # Example input data
```

## 🔧 Components

### app.py - GUI Application
Desktop interface built with CustomTkinter for:
- Selecting Python code and JSON input files
- Configuring resource limits (CPU, memory, PIDs)
- Enabling/disabling network access
- Viewing real-time execution output

### runner.py - Execution Orchestrator
Manages the execution lifecycle:
- Validates inputs (handler path and JSON file)
- Spawns user_runner.py as a subprocess
- Enforces 10-second timeout
- Returns structured JSON response with results/errors

### user_runner.py - Function Executor
Handles the actual function execution:
- Dynamically imports user modules
- Captures stdout, stderr, and logging output
- Measures execution duration
- Handles exceptions gracefully
- Returns JSON response with results, logs, errors, and timing

### Dockerfile
Builds a minimal execution environment:
- Based on `python:3.11-slim`
- Copies only `runner.py`
- Sets runner as entrypoint

## ⚙️ Configuration Options

### Resource Limits

| Parameter | Default | Description |
|-----------|---------|-------------|
| CPU | 0.5 | CPU cores allocated |
| Memory | 256 MB | Memory limit (including swap) |
| PIDs | 64 | Maximum process/thread count |
| Network | Disabled | Network access toggle |
| Timeout | 10s | Maximum execution time |

### Security Hardening

The container runs with strict security policies:
```bash
--cap-drop=ALL                    # Drop all Linux capabilities
--security-opt=no-new-privileges  # Prevent privilege escalation
--read-only                       # Read-only root filesystem
--tmpfs /tmp:rw,size=64m         # Writable temp with size limit
--network none                    # No network access (default)
```

## 📝 Handler Function Format

Your handler must follow this signature:

```python
def handler(event: dict, context: dict) -> dict:
    """
    Args:
        event: Input data from JSON file's "event" field
        context: Context data from JSON file's "context" field
    
    Returns:
        dict: Your function's result (must be JSON-serializable)
    """
    # Your code here
    return {"result": "success"}
```

## 📄 Input JSON Format

```json
{
  "version": "v1",
  "context": {
    "request_id": "optional-context-data"
  },
  "event": {
    "your": "input",
    "data": "here"
  }
}
```

- **version**: Must be "v1" (required)
- **context**: Optional context information
- **event**: Your function's input data

## 📤 Output Format

The runner returns a JSON response:

```json
{
  "result": {"your": "output"},
  "logs": "Captured stdout/stderr/logging output",
  "error": "Stack trace if error occurred, null otherwise",
  "duration_ms": 145
}
```

## 🛡️ Security Features

1. **Container Isolation**: Each execution runs in a fresh container
2. **Resource Limits**: Prevents resource exhaustion attacks
3. **No Network Access**: By default, no internet connectivity
4. **Read-Only Filesystem**: Cannot modify system files
5. **Capability Dropping**: Removes all privileged operations
6. **Timeout Enforcement**: Kills runaway processes
7. **Size Limits**: Input JSON capped at 1MB

## 🎯 Use Cases

- **Function Testing**: Test serverless functions locally before deployment
- **Code Education**: Safe environment for running student code
- **API Sandboxing**: Execute user-provided code snippets
- **CI/CD Integration**: Automated testing of functions
- **Plugin Systems**: Safe execution of third-party plugins

## 🔍 Example Usage

### Simple Math Function

```python
# main.py
def handler(event, context):
    a = event.get("a", 0)
    b = event.get("b", 0)
    
    return {
        "sum": a + b,
        "product": a * b,
        "quotient": a / b if b != 0 else None
    }
```

### With Logging

```python
# main.py
import logging

def handler(event, context):
    logging.info(f"Processing event: {event}")
    
    result = event["value"] * 2
    
    logging.info(f"Result: {result}")
    return {"result": result}
```

### With Error Handling

```python
# main.py
def handler(event, context):
    try:
        # Your logic here
        if "required_field" not in event:
            raise ValueError("Missing required_field")
        
        return {"status": "success"}
    except Exception as e:
        # Errors are captured and returned in response
        raise
```

## 🐛 Troubleshooting

### Container fails to start
- Ensure Docker is running
- Check that the sraas-runner image is built
- Verify file paths are absolute and accessible

### Function times out
- Reduce computation complexity
- Check for infinite loops
- Consider increasing timeout in `runner.py`

### Import errors
- Ensure your handler module is valid Python
- Check module.function format (e.g., `main.handler`)
- Verify file is mounted correctly

### JSON validation fails
- Ensure JSON is valid (use a validator)
- Check that "version": "v1" is present
- Verify file size is under 1MB

## 🔄 Development Workflow

1. Write your function in a `.py` file
2. Create test input in a `.json` file
3. Use the GUI to execute and test
4. Review output, logs, and errors
5. Iterate on your function

## 🚀 Advanced: Direct Docker Usage

Run without the GUI:

```bash
docker run --rm \
  --cpus 0.5 \
  --memory 256m \
  --memory-swap 256m \
  --pids-limit 64 \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --read-only \
  --tmpfs /tmp:rw,size=64m \
  --network none \
  -v $(pwd)/main.py:/function/main.py:ro \
  -v $(pwd)/data.json:/input/input.json:ro \
  -v $(pwd)/user_runner.py:/function/user_runner.py:ro \
  python:3.11-slim \
  python /function/user_runner.py main.handler /input/input.json
```

## 📦 Deployment

### As a Service
Convert `runner.py` to a web service:
```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/execute', methods=['POST'])
def execute():
    # Use runner.py logic here
    return jsonify(result)
```

### As a CLI Tool
```bash
python runner.py main.handler data.json
```

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Support for other languages (Node.js, Go, etc.)
- Web-based interface
- Persistent storage options
- Metrics and monitoring
- Function versioning

## ⚠️ Limitations

- **Language**: Currently Python 3.11 only
- **Timeout**: Hard-coded 10-second limit
- **Size**: Input JSON limited to 1MB
- **State**: No persistence between executions
- **Dependencies**: No pip install during execution (must be in base image)

## 📄 License

Open source - check repository for license details.

## 🙏 Acknowledgments

Built with:
- Docker for containerization
- CustomTkinter for the GUI
- Python's subprocess and importlib for execution

---

**⚠️ Security Notice**: This tool executes arbitrary code. Always run in isolated environments and never expose to untrusted users without proper authentication and authorization.
