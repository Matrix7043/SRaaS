"""
Tests for POST /deploy
"""

import hashlib
import json
from pathlib import Path

import pytest

from tests.conftest import SAMPLE_CODE, SAMPLE_HASH, FUNCTION_ID, DEPLOYMENT_ID


class TestDeploy:

    def test_deploy_success_returns_deployment_id(self, client, mock_docker):
        resp = client.post(
            "/deploy",
            params={"function_id": FUNCTION_ID, "hash_code": SAMPLE_HASH},
            files={"file": ("main.py", SAMPLE_CODE, "text/plain")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["deployment_id"] == DEPLOYMENT_ID
        assert body["container_name"] == DEPLOYMENT_ID
        assert body["invocation_url"] == f"/invoke/{DEPLOYMENT_ID}"

    def test_deploy_calls_start_container_with_correct_args(self, client, mock_docker):
        client.post(
            "/deploy",
            params={
                "function_id": FUNCTION_ID,
                "hash_code": SAMPLE_HASH,
                "entry_point": "main.handler",
                "cpu_cores": 1.0,
                "memory_mb": 512,
                "pid_limit": 32,
            },
            files={"file": ("main.py", SAMPLE_CODE, "text/plain")},
        )
        start = mock_docker["start"]
        start.assert_called_once()
        kwargs = start.call_args.kwargs
        assert kwargs["deployment_id"] == DEPLOYMENT_ID
        assert kwargs["entry_point"] == "main.handler"
        assert kwargs["cpu_cores"] == 1.0
        assert kwargs["memory_mb"] == 512
        assert kwargs["pid_limit"] == 32

    def test_deploy_stores_record_in_store(self, client, mock_docker):
        from app.main import store
        client.post(
            "/deploy",
            params={"function_id": FUNCTION_ID, "hash_code": SAMPLE_HASH},
            files={"file": ("main.py", SAMPLE_CODE, "text/plain")},
        )
        record = store.get(DEPLOYMENT_ID)
        assert record is not None
        assert record["function_id"] == FUNCTION_ID
        assert record["hash_code"] == SAMPLE_HASH
        assert record["entry_point"] == "main.handler"

    def test_deploy_stages_user_runner_next_to_uploaded_code(self, client, mock_docker):
        client.post(
            "/deploy",
            params={"function_id": FUNCTION_ID, "hash_code": SAMPLE_HASH},
            files={"file": ("main.py", SAMPLE_CODE, "text/plain")},
        )
        code_path = mock_docker["start"].call_args.kwargs["code_path"]
        runner_path = Path(code_path).parent / "user_runner.py"
        assert runner_path.exists()

    def test_deploy_rejects_non_py_file(self, client, mock_docker):
        resp = client.post(
            "/deploy",
            params={"function_id": FUNCTION_ID, "hash_code": "abc"},
            files={"file": ("main.js", b"console.log('hi')", "text/plain")},
        )
        assert resp.status_code == 400
        assert "Only .py files" in resp.json()["detail"]

    def test_deploy_rejects_mismatched_hash(self, client, mock_docker):
        wrong_hash = "a" * 64
        resp = client.post(
            "/deploy",
            params={"function_id": FUNCTION_ID, "hash_code": wrong_hash},
            files={"file": ("main.py", SAMPLE_CODE, "text/plain")},
        )
        assert resp.status_code == 400
        assert "Hash mismatch" in resp.json()["detail"]

    def test_deploy_returns_500_when_docker_fails(self, client, mock_docker):
        mock_docker["start"].side_effect = RuntimeError("docker daemon not running")
        resp = client.post(
            "/deploy",
            params={"function_id": FUNCTION_ID, "hash_code": SAMPLE_HASH},
            files={"file": ("main.py", SAMPLE_CODE, "text/plain")},
        )
        assert resp.status_code == 500
        assert "Deployment failed" in resp.json()["detail"]

    def test_deploy_uses_default_resource_limits(self, client, mock_docker):
        client.post(
            "/deploy",
            params={"function_id": FUNCTION_ID, "hash_code": SAMPLE_HASH},
            files={"file": ("main.py", SAMPLE_CODE, "text/plain")},
        )
        kwargs = mock_docker["start"].call_args.kwargs
        assert kwargs["cpu_cores"] == 0.5
        assert kwargs["memory_mb"] == 256
        assert kwargs["pid_limit"] == 64
