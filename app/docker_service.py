"""
DockerService: manages the lifecycle of per-deployment Docker containers.

Architecture
------------
Each deployed function gets a LONG-RUNNING container that:
  - mounts the user's .py file at /function/main.py (read-only)
  - mounts user_runner.py at /function/user_runner.py (read-only)
  - has no network, a capped PID table, and a read-only root FS

Invocation is done by running a one-shot `docker exec` against the
long-running container, so startup cost is paid only once per deployment.

This matches the ContainerService stub in Spring Boot:
  deploy()  → start_container()
  delete()  → stop_container()
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Path to user_runner.py relative to THIS file's directory (project root)
_HERE = Path(__file__).parent.parent
USER_RUNNER = _HERE / "user_runner.py"

DOCKER_IMAGE = "python:3.11-slim"
EXEC_TIMEOUT = 15  # seconds for a single function invocation


class DockerService:
    """Wraps docker CLI calls for deploying and invoking sandboxed functions."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_docker_available(self) -> bool:
        try:
            subprocess.run(
                ["docker", "info"],
                check=True,
                capture_output=True,
                timeout=5,
            )
            return True
        except Exception:
            return False

    def start_container(
        self,
        deployment_id: str,
        code_path: Path,
        entry_point: str,
        cpu_cores: float,
        memory_mb: int,
        pid_limit: int,
    ) -> str:
        """
        Launch a long-running sandboxed container for this deployment.
        Returns the container name.
        """
        container_name = deployment_id  # reuse as container name

        # Kill any stale container with the same name first
        self._remove_container_if_exists(container_name)

        cmd = [
            "docker", "run",
            "--detach",
            "--name", container_name,
            # Resource limits
            "--cpus", str(cpu_cores),
            "--memory", f"{memory_mb}m",
            "--memory-swap", f"{memory_mb}m",
            "--pids-limit", str(pid_limit),
            # Security hardening
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--read-only",
            "--tmpfs", "/tmp:rw,size=64m",
            "--network", "none",
            # Mount user code and runner (read-only)
            "-v", f"{code_path.resolve()}:/function/main.py:ro",
            "-v", f"{USER_RUNNER.resolve()}:/function/user_runner.py:ro",
            DOCKER_IMAGE,
            # Keep container alive waiting for exec calls
            "sleep", "infinity",
        ]

        if not USER_RUNNER.exists():
            raise RuntimeError(f"Runner file not found: {USER_RUNNER}")

        logger.info("Starting container: %s", container_name)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            raise RuntimeError(
                f"docker run failed [{result.returncode}]: {result.stderr.strip()}"
            )

        logger.info("Container started: %s", container_name)
        return container_name

    def invoke_function(
        self,
        container_name: str,
        entry_point: str,
        event: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute the user function inside the running container via docker exec.
        Writes a temp JSON payload file into /tmp inside the container, then
        runs user_runner.py against it.
        """
        payload = json.dumps({
            "version": "v1",
            "event": event,
            "context": context,
        })

        # Write the payload into the container's /tmp (the only writable dir)
        write_cmd = [
            "docker", "exec", "-i", container_name,
            "sh", "-c",
            "cat > /tmp/input.json",
        ]
        wr = subprocess.run(
            write_cmd,
            input=payload,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if wr.returncode != 0:
            raise RuntimeError(f"Failed to write payload: {wr.stderr.strip()}")

        # Run the user_runner
        exec_cmd = [
            "docker", "exec", container_name,
            "python", "/function/user_runner.py",
            entry_point,
            "/tmp/input.json",
        ]
        try:
            result = subprocess.run(
                exec_cmd,
                capture_output=True,
                text=True,
                timeout=EXEC_TIMEOUT,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("Function execution timed out") from exc

        if result.returncode != 0 and not result.stdout.strip():
            raise RuntimeError(
                f"Execution failed [{result.returncode}]: {result.stderr.strip()}"
            )

        try:
            return json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            return {
                "result": None,
                "logs": result.stdout + result.stderr,
                "error": "Invalid JSON output from function",
                "duration_ms": 0,
            }

    def stop_container(self, container_name: str) -> None:
        """Stop and remove a running container."""
        self._remove_container_if_exists(container_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _remove_container_if_exists(self, container_name: str) -> None:
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True,
            timeout=10,
        )
