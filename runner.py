import subprocess
import sys
import json
import time

sys.path.insert(0, "/function")

TIMEOUT_SECONDS = 10

def run(handler_path, event):
    proc = subprocess.Popen(
        [sys.executable, "user_runner.py", handler_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        stdout, stderr = proc.communicate(
            input=json.dumps(event),
            timeout=TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired:
        proc.kill()
        return {
            "result": None,
            "error": "Execution Timed out",
            "duration_ms": TIMEOUT_SECONDS
        }

    if stderr:
        return {
            "result": None,
            "error": stderr
        }

    return json.loads(stdout)

if __name__ == "__main__":
    handler = sys.argv[1]
    event = json.loads(sys.stdin.read() or "{}")
    print(json.dumps(run(handler, event)))
