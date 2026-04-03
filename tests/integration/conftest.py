"""
Fixtures for integration tests that use a real Docker daemon.

Run with:
    pytest -m integration -v

Skipped automatically when Docker is not available.
"""

import hashlib
import subprocess
import pytest
from fastapi.testclient import TestClient

from app.main import app, store
from app.docker_service import DockerService

# ── sample functions used across integration tests ─────────────────────────

SIMPLE_HANDLER = b"""\
def handler(event, context):
    return {"sum": event["a"] + event["b"]}
"""

DIVIDE_HANDLER = b"""\
def handler(event, context):
    return {"quotient": event["a"] / event["b"]}
"""

PRINT_HANDLER = b"""\
import logging
logging.basicConfig(level=logging.INFO)

def handler(event, context):
    print("hello from stdout")
    logging.info("hello from logging")
    return {"ok": True}
"""

SLOW_HANDLER = b"""\
import time
def handler(event, context):
    time.sleep(30)
    return {"done": True}
"""

IMPORT_HANDLER = b"""\
import os
import json
def handler(event, context):
    return {"pid": os.getpid(), "env_keys": list(os.environ.keys())}
"""


def _hash(code: bytes) -> str:
    return hashlib.sha256(code).hexdigest()


# ── session-scoped Docker availability check ───────────────────────────────

def _docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def pytest_configure(config):
    """Register the integration marker (also done in pytest.ini, belt-and-suspenders)."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests that require a live Docker daemon",
    )


# ── fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def require_docker():
    """Skip entire integration session if Docker is not reachable."""
    if not _docker_available():
        pytest.skip("Docker daemon not available — skipping integration tests")


@pytest.fixture(scope="session")
def pull_image():
    """Pull python:3.11-slim once per test session."""
    subprocess.run(
        ["docker", "pull", "python:3.11-slim"],
        check=True,
        timeout=120,
    )


@pytest.fixture
def integration_client(pull_image):
    """
    TestClient backed by the REAL DockerService (no mocks).
    Clears the store before each test.
    """
    for did in store.all_ids():
        store.remove(did)
    yield TestClient(app)


@pytest.fixture
def tracking_containers():
    """
    Keeps track of container names created during a test so they can be
    force-removed in teardown even if the test fails.
    """
    names = []
    yield names
    for name in names:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def deploy_function(
    client,
    tracking_containers,
    code: bytes,
    function_id: str = "test-fn-001",
    entry_point: str = "main.handler",
    cpu_cores: float = 0.5,
    memory_mb: int = 256,
    pid_limit: int = 64,
) -> dict:
    """Helper: deploy a function and register its container for cleanup."""
    h = _hash(code)
    resp = client.post(
        "/deploy",
        params={
            "function_id": function_id,
            "hash_code": h,
            "entry_point": entry_point,
            "cpu_cores": cpu_cores,
            "memory_mb": memory_mb,
            "pid_limit": pid_limit,
        },
        files={"file": ("main.py", code, "text/plain")},
    )
    if resp.status_code == 200:
        tracking_containers.append(resp.json()["container_name"])
    return resp
