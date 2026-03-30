"""
Tests for DELETE /deployments/{deployment_id} and GET /health
"""

import pytest
from tests.conftest import DEPLOYMENT_ID


class TestDeleteDeployment:

    def test_delete_returns_200_and_removes_from_store(self, deployed, mock_docker):
        from app.main import store
        client, deployment_id = deployed
        assert store.get(deployment_id) is not None

        resp = client.delete(f"/deployments/{deployment_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["deployment_id"] == deployment_id
        assert "deleted" in body["message"].lower()

        # Store entry removed immediately
        assert store.get(deployment_id) is None

    def test_delete_returns_404_for_unknown_deployment(self, client, mock_docker):
        resp = client.delete("/deployments/ghost-deployment")
        assert resp.status_code == 404

    def test_delete_is_idempotent_second_call_gives_404(self, deployed, mock_docker):
        client, deployment_id = deployed
        client.delete(f"/deployments/{deployment_id}")
        resp = client.delete(f"/deployments/{deployment_id}")
        assert resp.status_code == 404

    def test_delete_triggers_container_stop_in_background(self, deployed, mock_docker):
        """
        Background tasks run synchronously in TestClient, so we can assert stop was called.
        """
        client, deployment_id = deployed
        client.delete(f"/deployments/{deployment_id}")
        mock_docker["stop"].assert_called_once_with(deployment_id)

    def test_delete_after_failed_deployment_not_in_store(self, client, mock_docker):
        """Deleting a never-deployed ID should 404 cleanly."""
        resp = client.delete("/deployments/deployment_fake_hash")
        assert resp.status_code == 404


class TestHealth:

    def test_health_returns_ok_when_docker_available(self, client, mock_docker):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["docker_available"] is True

    def test_health_returns_docker_unavailable(self, client):
        from unittest.mock import patch
        from app.main import docker_svc
        with patch.object(docker_svc, "is_docker_available", return_value=False):
            resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["docker_available"] is False
