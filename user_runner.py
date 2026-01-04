import importlib
import json
import sys
import io
import time
import traceback
import logging

sys.path.insert(0, "/function")

log_buffer = io.StringIO()

logging.basicConfig(
    level=logging.INFO,
    stream=log_buffer,
    format="%(levelname)s: %(message)s"
)

stdout_buffer = io.StringIO()
stderr_buffer = io.StringIO()

old_stdout = sys.stdout
old_stderr = sys.stderr

sys.stdout = stdout_buffer
sys.stderr = stderr_buffer

start_time = time.monotonic()

try:

    handler_path = sys.argv[1]
    
    path = sys.argv[2]
    
    with open(path) as f:
        payload = json.load(f)

    if payload.get("version", "") != "v1":
        raise ValueError("Unsupported or missing version")

    event = payload.get("event", {})
    context = payload.get("context", {})

    module_name, func_name = handler_path.rsplit(".", 1)

    module = importlib.import_module(module_name)

    handler = getattr(module, func_name)

    try:
        result = handler(event, {})
        error = None
    except Exception:
        result = None
        error = traceback.format_exc()

except Exception:
    result = None
    error = traceback.format_exc()

finally:
    sys.stdout = old_stdout
    sys.stderr = old_stderr

duration_ms = int((time.monotonic() -  start_time)*1000)

logs = (stdout_buffer.getvalue() + stderr_buffer.getvalue() + log_buffer.getvalue())

response = {
    "result": result,
    "logs": logs,
    "error": error,
    "duration_ms": duration_ms
}

print(json.dumps(response))
