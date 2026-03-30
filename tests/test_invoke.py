"""
Tests for POST /invoke/{deployment_id}
"""

import pytest
from tests.conftest import DEPLOYMENT_ID


class TestInvoke:

    def test_invoke_success_returns_result(self, deployed, mock_docker):
        client, deployment_id = deployed
        mock_docker["invoke"].return_value = {
            "result": {"sum": 7},
            "logs": "",
            "error": None,
            "duration_ms": 42,
        }
        resp = client.post(
            f"/invoke/{deployment_id}",
            json={"version": "v1", "event": {"a": 3, "b": 4}, "context": {}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"] == {"sum": 7}
        assert body["duration_ms"] == 42
        assert body["error"] is None

    def test_invoke_passes_event_and_context_to_docker(self, deployed, mock_docker):
        client, deployment_id = deployed
        mock_docker["invoke"].return_value = {
            "result": None, "logs": "", "error": None, "duration_ms": 0
        }
        client.post(
            f"/invoke/{deployment_id}",
            json={"version": "v1", "event": {"x": 99}, "context": {"req_id": "abc"}},
        )
        call_kwargs = mock_docker["invoke"].call_args.kwargs
        assert call_kwargs["event"] == {"x": 99}
        assert call_kwargs["context"] == {"req_id": "abc"}
        assert call_kwargs["entry_point"] == "main.handler"

    def test_invoke_uses_correct_container_name(self, deployed, mock_docker):
        client, deployment_id = deployed
        mock_docker["invoke"].return_value = {
            "result": None, "logs": "", "error": None, "duration_ms": 0
        }
        client.post(f"/invoke/{deployment_id}", json={"event": {}})
        call_kwargs = mock_docker["invoke"].call_args.kwargs
        assert call_kwargs["container_name"] == deployment_id

    def test_invoke_returns_404_for_unknown_deployment(self, client, mock_docker):
        resp = client.post("/invoke/nonexistent", json={"event": {}})
        assert resp.status_code == 404

    def test_invoke_returns_function_error_in_response(self, deployed, mock_docker):
        client, deployment_id = deployed
        mock_docker["invoke"].return_value = {
            "result": None,
            "logs": "Traceback...",
            "error": "ZeroDivisionError: division by zero",
            "duration_ms": 5,
        }
        resp = client.post(f"/invoke/{deployment_id}", json={"event": {"a": 1, "b": 0}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"] is None
        assert "ZeroDivisionError" in body["error"]

    def test_invoke_returns_408_on_timeout(self, deployed, mock_docker):
        client, deployment_id = deployed
        mock_docker["invoke"].side_effect = TimeoutError("execution timed out")
        resp = client.post(f"/invoke/{deployment_id}", json={"event": {}})
        assert resp.status_code == 408

    def test_invoke_returns_500_on_docker_error(self, deployed, mock_docker):
        client, deployment_id = deployed
        mock_docker["invoke"].side_effect = RuntimeError("container exited unexpectedly")
        resp = client.post(f"/invoke/{deployment_id}", json={"event": {}})
        assert resp.status_code == 500

    def test_invoke_defaults_to_empty_event_and_context(self, deployed, mock_docker):
        client, deployment_id = deployed
        mock_docker["invoke"].return_value = {
            "result": "ok", "logs": "", "error": None, "duration_ms": 1
        }
        resp = client.post(f"/invoke/{deployment_id}", json={})
        assert resp.status_code == 200
        call_kwargs = mock_docker["invoke"].call_args.kwargs
        assert call_kwargs["event"] == {}
        assert call_kwargs["context"] == {}
