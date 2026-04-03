"""
Integration tests for POST /invoke/{deployment_id} — uses a real Docker daemon.

Run with: pytest -m integration -v
"""

import pytest

from tests.integration.conftest import (
    SIMPLE_HANDLER,
    DIVIDE_HANDLER,
    PRINT_HANDLER,
    SLOW_HANDLER,
    IMPORT_HANDLER,
    deploy_function,
)


@pytest.mark.integration
class TestInvokeIntegration:

    def test_invoke_returns_correct_result(
        self, integration_client, tracking_containers
    ):
        dep = deploy_function(integration_client, tracking_containers, SIMPLE_HANDLER)
        deployment_id = dep.json()["deployment_id"]

        resp = integration_client.post(
            f"/invoke/{deployment_id}",
            json={"event": {"a": 3, "b": 4}, "context": {}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"] == {"sum": 7}
        assert body["error"] is None
        assert body["duration_ms"] >= 0

    def test_invoke_with_zero_values(
        self, integration_client, tracking_containers
    ):
        dep = deploy_function(integration_client, tracking_containers, SIMPLE_HANDLER)
        deployment_id = dep.json()["deployment_id"]

        resp = integration_client.post(
            f"/invoke/{deployment_id}",
            json={"event": {"a": 0, "b": 0}, "context": {}},
        )
        assert resp.status_code == 200
        assert resp.json()["result"] == {"sum": 0}

    def test_invoke_captures_function_exception_in_error_field(
        self, integration_client, tracking_containers
    ):
        """Division by zero should not crash the runner — error comes back in body."""
        dep = deploy_function(integration_client, tracking_containers, DIVIDE_HANDLER)
        deployment_id = dep.json()["deployment_id"]

        resp = integration_client.post(
            f"/invoke/{deployment_id}",
            json={"event": {"a": 10, "b": 0}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"] is None
        assert "ZeroDivisionError" in body["error"]

    def test_invoke_captures_stdout_and_logging_in_logs(
        self, integration_client, tracking_containers
    ):
        dep = deploy_function(integration_client, tracking_containers, PRINT_HANDLER)
        deployment_id = dep.json()["deployment_id"]

        resp = integration_client.post(
            f"/invoke/{deployment_id}",
            json={"event": {}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"] == {"ok": True}
        assert "hello from stdout" in body["logs"]

    def test_invoke_multiple_times_same_container(
        self, integration_client, tracking_containers
    ):
        """Container should stay alive and handle sequential invocations."""
        dep = deploy_function(integration_client, tracking_containers, SIMPLE_HANDLER)
        deployment_id = dep.json()["deployment_id"]

        for i in range(5):
            resp = integration_client.post(
                f"/invoke/{deployment_id}",
                json={"event": {"a": i, "b": 1}},
            )
            assert resp.status_code == 200
            assert resp.json()["result"] == {"sum": i + 1}

    def test_invoke_records_duration(
        self, integration_client, tracking_containers
    ):
        dep = deploy_function(integration_client, tracking_containers, SIMPLE_HANDLER)
        deployment_id = dep.json()["deployment_id"]

        resp = integration_client.post(
            f"/invoke/{deployment_id}",
            json={"event": {"a": 1, "b": 2}},
        )
        assert resp.status_code == 200
        assert resp.json()["duration_ms"] > 0

    def test_invoke_slow_function_hits_timeout(
        self, integration_client, tracking_containers
    ):
        """A function that sleeps 30s should hit the 15s exec timeout."""
        dep = deploy_function(integration_client, tracking_containers, SLOW_HANDLER)
        deployment_id = dep.json()["deployment_id"]

        resp = integration_client.post(
            f"/invoke/{deployment_id}",
            json={"event": {}},
            # Give the HTTP client more than the docker exec timeout
            timeout=20,
        )
        # Either 408 (TimeoutError caught) or 500 (subprocess.TimeoutExpired propagated)
        assert resp.status_code in (408, 500)

    def test_invoke_container_has_no_network_access(
        self, integration_client, tracking_containers
    ):
        """Function should not be able to reach external hosts."""
        no_network_handler = b"""\
import socket
def handler(event, context):
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return {"network": True}
    except OSError:
        return {"network": False}
"""
        dep = deploy_function(integration_client, tracking_containers, no_network_handler)
        deployment_id = dep.json()["deployment_id"]

        resp = integration_client.post(f"/invoke/{deployment_id}", json={"event": {}})
        assert resp.status_code == 200
        assert resp.json()["result"] == {"network": False}

    def test_invoke_passes_event_correctly_for_complex_payload(
        self, integration_client, tracking_containers
    ):
        nested_handler = b"""\
def handler(event, context):
    return {
        "nested": event["outer"]["inner"],
        "list_item": event["items"][1],
    }
"""
        dep = deploy_function(integration_client, tracking_containers, nested_handler)
        deployment_id = dep.json()["deployment_id"]

        resp = integration_client.post(
            f"/invoke/{deployment_id}",
            json={"event": {"outer": {"inner": "deep_value"}, "items": ["a", "b", "c"]}},
        )
        assert resp.status_code == 200
        assert resp.json()["result"] == {"nested": "deep_value", "list_item": "b"}

    def test_invoke_404_after_delete(
        self, integration_client, tracking_containers
    ):
        dep = deploy_function(integration_client, tracking_containers, SIMPLE_HANDLER)
        deployment_id = dep.json()["deployment_id"]

        integration_client.delete(f"/deployments/{deployment_id}")

        resp = integration_client.post(
            f"/invoke/{deployment_id}", json={"event": {}}
        )
        assert resp.status_code == 404
