import subprocess
import sys
import json
import time

sys.path.insert(0, "/function")

TIMEOUT_SECONDS = 10

def run(handler_path, file):
    proc = subprocess.Popen(
        [sys.executable, "user_runner.py", handler_path, file],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        stdout, stderr = proc.communicate(
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
    file = sys.argv[2]
    try:
        with open(file) as f:
            json.load(f)
    except Exception as e:
        print(e)
        sys.exit(1)
    if not file or not handler:
        error = {
            "result": None,
            "error": "handler or file is empty"
        }
        print(json.dumps(error))
        sys.exit(1)
    print(json.dumps(run(handler, file)))
