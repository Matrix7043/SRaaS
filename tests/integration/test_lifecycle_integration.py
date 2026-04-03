"""
Integration tests for DELETE /deployments and end-to-end lifecycle.

Run with: pytest -m integration -v
"""

import subprocess
import time
import pytest

from tests.integration.conftest import SIMPLE_HANDLER, deploy_function


@pytest.mark.integration
class TestDeleteIntegration:

    def test_delete_stops_and_removes_container(
        self, integration_client, tracking_containers
    ):
        dep = deploy_function(integration_client, tracking_containers, SIMPLE_HANDLER)
        body = dep.json()
        deployment_id = body["deployment_id"]
        container_name = body["container_name"]

        resp = integration_client.delete(f"/deployments/{deployment_id}")
        assert resp.status_code == 200

        # Give background task time to complete
        time.sleep(1)

        result = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
        )
        # Container should no longer exist
        assert result.returncode != 0

    def test_delete_removes_staging_directory(
        self, integration_client, tracking_containers
    ):
        import os
        dep = deploy_function(integration_client, tracking_containers, SIMPLE_HANDLER)
        deployment_id = dep.json()["deployment_id"]

        from app.main import store
        record = store.get(deployment_id)
        staging_dir = record["staging_dir"]

        assert os.path.exists(staging_dir)

        integration_client.delete(f"/deployments/{deployment_id}")
        time.sleep(1)

        assert not os.path.exists(staging_dir)

    def test_delete_is_idempotent(
        self, integration_client, tracking_containers
    ):
        dep = deploy_function(integration_client, tracking_containers, SIMPLE_HANDLER)
        deployment_id = dep.json()["deployment_id"]

        r1 = integration_client.delete(f"/deployments/{deployment_id}")
        assert r1.status_code == 200

        r2 = integration_client.delete(f"/deployments/{deployment_id}")
        assert r2.status_code == 404


@pytest.mark.integration
class TestFullLifecycleIntegration:

    def test_deploy_invoke_delete_full_cycle(
        self, integration_client, tracking_containers
    ):
        """
        Full happy path: deploy → invoke (success) → invoke (error) → delete → invoke 404.
        This mirrors exactly what Spring Boot orchestrates.
        """
        # 1. Deploy
        dep = deploy_function(integration_client, tracking_containers, SIMPLE_HANDLER)
        assert dep.status_code == 200
        deployment_id = dep.json()["deployment_id"]
        invocation_url = dep.json()["invocation_url"]
        assert invocation_url == f"/invoke/{deployment_id}"

        # 2. Successful invocation
        r1 = integration_client.post(
            invocation_url,
            json={"event": {"a": 10, "b": 5}},
        )
        assert r1.status_code == 200
        assert r1.json()["result"] == {"sum": 15}
        assert r1.json()["error"] is None

        # 3. Error invocation (missing key) — runner should return error in body, not 5xx
        r2 = integration_client.post(
            invocation_url,
            json={"event": {}},  # handler will raise KeyError
        )
        assert r2.status_code == 200
        assert r2.json()["result"] is None
        assert r2.json()["error"] is not None

        # 4. Delete
        rd = integration_client.delete(f"/deployments/{deployment_id}")
        assert rd.status_code == 200
        time.sleep(1)

        # 5. Invoke after delete → 404
        r3 = integration_client.post(invocation_url, json={"event": {}})
        assert r3.status_code == 404

    def test_two_deployments_are_independent(
        self, integration_client, tracking_containers
    ):
        """Two functions deployed concurrently should not share state."""
        handler_a = b"""\
def handler(event, context):
    return {"owner": "A", "val": event["x"]}
"""
        handler_b = b"""\
def handler(event, context):
    return {"owner": "B", "val": event["x"] * 2}
"""
        dep_a = deploy_function(
            integration_client, tracking_containers, handler_a, function_id="fn-a"
        )
        dep_b = deploy_function(
            integration_client, tracking_containers, handler_b, function_id="fn-b"
        )

        id_a = dep_a.json()["deployment_id"]
        id_b = dep_b.json()["deployment_id"]

        ra = integration_client.post(f"/invoke/{id_a}", json={"event": {"x": 5}})
        rb = integration_client.post(f"/invoke/{id_b}", json={"event": {"x": 5}})

        assert ra.json()["result"] == {"owner": "A", "val": 5}
        assert rb.json()["result"] == {"owner": "B", "val": 10}
