"""
Integration tests for POST /deploy — uses a real Docker daemon.

Run with: pytest -m integration -v
"""

import hashlib
import subprocess
import pytest

from tests.integration.conftest import (
    SIMPLE_HANDLER,
    DIVIDE_HANDLER,
    deploy_function,
    _hash,
)


@pytest.mark.integration
class TestDeployIntegration:

    def test_deploy_starts_a_real_container(
        self, integration_client, tracking_containers
    ):
        resp = deploy_function(integration_client, tracking_containers, SIMPLE_HANDLER)
        assert resp.status_code == 200

        container_name = resp.json()["container_name"]

        # Verify docker ps sees the container as running
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "running"

    def test_deploy_mounts_code_file_correctly(
        self, integration_client, tracking_containers
    ):
        resp = deploy_function(integration_client, tracking_containers, SIMPLE_HANDLER)
        container = resp.json()["container_name"]

        # Read the mounted file back out of the container
        cat = subprocess.run(
            ["docker", "exec", container, "cat", "/function/main.py"],
            capture_output=True,
            text=True,
        )
        assert cat.returncode == 0
        assert "def handler" in cat.stdout

    def test_deploy_container_has_no_network(
        self, integration_client, tracking_containers
    ):
        resp = deploy_function(integration_client, tracking_containers, SIMPLE_HANDLER)
        container = resp.json()["container_name"]

        # Network mode should be 'none'
        net = subprocess.run(
            ["docker", "inspect", "--format", "{{.HostConfig.NetworkMode}}", container],
            capture_output=True,
            text=True,
        )
        assert net.stdout.strip() == "none"

    def test_deploy_container_is_read_only(
        self, integration_client, tracking_containers
    ):
        resp = deploy_function(integration_client, tracking_containers, SIMPLE_HANDLER)
        container = resp.json()["container_name"]

        # Attempting to write outside /tmp should fail
        write = subprocess.run(
            ["docker", "exec", container, "sh", "-c", "echo x > /test_rw"],
            capture_output=True,
            text=True,
        )
        assert write.returncode != 0

    def test_deploy_container_can_write_to_tmp(
        self, integration_client, tracking_containers
    ):
        resp = deploy_function(integration_client, tracking_containers, SIMPLE_HANDLER)
        container = resp.json()["container_name"]

        write = subprocess.run(
            ["docker", "exec", container, "sh", "-c", "echo hello > /tmp/test.txt && cat /tmp/test.txt"],
            capture_output=True,
            text=True,
        )
        assert write.returncode == 0
        assert "hello" in write.stdout

    def test_deploy_second_call_same_id_replaces_container(
        self, integration_client, tracking_containers
    ):
        """Redeploying the same function ID should not leave orphan containers."""
        h = _hash(SIMPLE_HANDLER)
        params = {
            "function_id": "fn-redeploy",
            "hash_code": h,
        }
        files = {"file": ("main.py", SIMPLE_HANDLER, "text/plain")}

        r1 = integration_client.post("/deploy", params=params, files=files)
        assert r1.status_code == 200
        tracking_containers.append(r1.json()["container_name"])

        # Second deploy with different code
        h2 = _hash(DIVIDE_HANDLER)
        r2 = integration_client.post(
            "/deploy",
            params={**params, "hash_code": h2},
            files={"file": ("main.py", DIVIDE_HANDLER, "text/plain")},
        )
        assert r2.status_code == 200
        tracking_containers.append(r2.json()["container_name"])

        # Only one container with the base name should exist
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=deployment_fn-redeploy", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )
        running = [l for l in result.stdout.strip().splitlines() if l]
        assert len(running) == 1

    def test_deploy_enforces_memory_limit(
        self, integration_client, tracking_containers
    ):
        resp = deploy_function(
            integration_client, tracking_containers, SIMPLE_HANDLER, memory_mb=128
        )
        container = resp.json()["container_name"]

        mem = subprocess.run(
            ["docker", "inspect", "--format", "{{.HostConfig.Memory}}", container],
            capture_output=True,
            text=True,
        )
        # 128 MB in bytes
        assert mem.stdout.strip() == str(128 * 1024 * 1024)

    def test_deploy_enforces_pid_limit(
        self, integration_client, tracking_containers
    ):
        resp = deploy_function(
            integration_client, tracking_containers, SIMPLE_HANDLER, pid_limit=20
        )
        container = resp.json()["container_name"]

        pids = subprocess.run(
            ["docker", "inspect", "--format", "{{.HostConfig.PidsLimit}}", container],
            capture_output=True,
            text=True,
        )
        assert pids.stdout.strip() == "20"
