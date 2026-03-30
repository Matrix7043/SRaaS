"""
Shared pytest fixtures for the SCaaS runner test suite.
"""

import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app, store, docker_svc
from app.store import DeploymentStore
from app.docker_service import DockerService


SAMPLE_CODE = b"def handler(event, context):\n    return {'sum': event['a'] + event['b']}\n"
SAMPLE_HASH = hashlib.sha256(SAMPLE_CODE).hexdigest()
FUNCTION_ID = "550e8400-e29b-41d4-a716-446655440000"
DEPLOYMENT_ID = f"deployment_{FUNCTION_ID}_{SAMPLE_HASH}"


@pytest.fixture
def client():
    """FastAPI test client with a fresh store per test."""
    # Reset store state between tests
    for did in store.all_ids():
        store.remove(did)
    return TestClient(app)


@pytest.fixture
def mock_docker():
    """Patch DockerService so no real docker calls are made."""
    with patch.object(docker_svc, "is_docker_available", return_value=True), \
         patch.object(docker_svc, "start_container", return_value=DEPLOYMENT_ID) as start, \
         patch.object(docker_svc, "stop_container") as stop, \
         patch.object(docker_svc, "invoke_function") as invoke:
        yield {
            "start": start,
            "stop": stop,
            "invoke": invoke,
        }


@pytest.fixture
def deployed(client, mock_docker):
    """
    Convenience fixture: pre-deploys a function and returns (client, deployment_id).
    """
    response = client.post(
        "/deploy",
        params={
            "function_id": FUNCTION_ID,
            "hash_code": SAMPLE_HASH,
            "entry_point": "main.handler",
            "cpu_cores": 0.5,
            "memory_mb": 256,
            "pid_limit": 64,
        },
        files={"file": ("main.py", SAMPLE_CODE, "text/plain")},
    )
    assert response.status_code == 200
    return client, response.json()["deployment_id"]
