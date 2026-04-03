"""
Executes a staged user function and emits a single JSON response on stdout.
"""

import importlib.util
import io
import json
import logging
import math
import sys
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


FUNCTION_PATH = Path("/function/main.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("user_main", FUNCTION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {FUNCTION_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_handler(module, entry_point: str):
    module_name, _, handler_name = entry_point.rpartition(".")
    if module_name not in ("", "main"):
        raise ValueError(f"Unsupported entry point module: {module_name}")

    handler = getattr(module, handler_name, None)
    if handler is None:
        raise AttributeError(f"Handler not found: {entry_point}")
    return handler


def _retarget_logging(stream: io.StringIO):
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if hasattr(handler, "stream"):
            handler.stream = stream


def main() -> int:
    if len(sys.argv) != 3:
        print(
            json.dumps(
                {
                    "result": None,
                    "logs": "",
                    "error": "Usage: user_runner.py <entry_point> <payload_path>",
                    "duration_ms": 0,
                }
            )
        )
        return 1

    entry_point = sys.argv[1]
    payload_path = Path(sys.argv[2])

    payload = json.loads(payload_path.read_text())
    event = payload.get("event", {})
    context = payload.get("context", {})

    module = _load_module()
    handler = _resolve_handler(module, entry_point)

    log_buffer = io.StringIO()
    start = time.perf_counter()

    try:
        _retarget_logging(log_buffer)
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            result = handler(event, context)
        error = None
    except Exception:
        result = None
        error = traceback.format_exc()

    response = {
        "result": result,
        "logs": log_buffer.getvalue(),
        "error": error,
        "duration_ms": max(1, math.ceil((time.perf_counter() - start) * 1000)),
    }
    print(json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
