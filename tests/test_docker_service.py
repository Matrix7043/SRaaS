"""
Unit tests for DockerService — all subprocess calls are mocked.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from app.docker_service import DockerService


FAKE_CODE_PATH = Path("/tmp/scaas/staging/dep_123/main.py")


@pytest.fixture
def svc():
    return DockerService()


class TestIsDockerAvailable:

    def test_returns_true_when_docker_info_succeeds(self, svc):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert svc.is_docker_available() is True

    def test_returns_false_when_docker_info_fails(self, svc):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert svc.is_docker_available() is False

    def test_returns_false_on_timeout(self, svc):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 5)):
            assert svc.is_docker_available() is False


class TestStartContainer:

    def _mock_run_success(self):
        m = MagicMock()
        m.returncode = 0
        m.stdout = "container_id_abc\n"
        m.stderr = ""
        return m

    def test_start_container_returns_deployment_id_as_name(self, svc):
        with patch("subprocess.run", return_value=self._mock_run_success()), \
             patch.object(Path, "exists", return_value=True):
            name = svc.start_container(
                deployment_id="dep_abc",
                code_path=FAKE_CODE_PATH,
                entry_point="main.handler",
                cpu_cores=0.5,
                memory_mb=256,
                pid_limit=64,
            )
        assert name == "dep_abc"

    def test_start_container_removes_stale_container_first(self, svc):
        calls = []
        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            m = MagicMock()
            m.returncode = 0
            m.stderr = ""
            return m

        with patch("subprocess.run", side_effect=fake_run), \
             patch.object(Path, "exists", return_value=True):
            svc.start_container(
                deployment_id="dep_abc",
                code_path=FAKE_CODE_PATH,
                entry_point="main.handler",
                cpu_cores=0.5,
                memory_mb=256,
                pid_limit=64,
            )

        # First call should be 'docker rm -f dep_abc'
        assert calls[0] == ["docker", "rm", "-f", "dep_abc"]
        # Second call should be 'docker run ...'
        assert calls[1][0] == "docker"
        assert calls[1][1] == "run"

    def test_start_container_uses_no_network(self, svc):
        captured = {}
        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            m = MagicMock()
            m.returncode = 0
            m.stderr = ""
            return m

        with patch("subprocess.run", side_effect=fake_run), \
             patch.object(Path, "exists", return_value=True):
            svc.start_container("dep_x", FAKE_CODE_PATH, "main.h", 0.5, 128, 32)

        run_cmd = captured["cmd"]
        assert "--network" in run_cmd
        none_idx = run_cmd.index("--network")
        assert run_cmd[none_idx + 1] == "none"

    def test_start_container_passes_resource_limits(self, svc):
        captured = {}
        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            m = MagicMock()
            m.returncode = 0
            m.stderr = ""
            return m

        with patch("subprocess.run", side_effect=fake_run), \
             patch.object(Path, "exists", return_value=True):
            svc.start_container("dep_x", FAKE_CODE_PATH, "main.h", 1.5, 512, 48)

        run_cmd = " ".join(captured["cmd"])
        assert "--cpus 1.5" in run_cmd
        assert "--memory 512m" in run_cmd
        assert "--pids-limit 48" in run_cmd

    def test_start_container_mounts_staged_user_runner(self, svc):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            m = MagicMock()
            m.returncode = 0
            m.stderr = ""
            return m

        with patch("subprocess.run", side_effect=fake_run), \
             patch.object(Path, "exists", return_value=True):
            svc.start_container("dep_x", FAKE_CODE_PATH, "main.h", 0.5, 128, 32)

        run_cmd = captured["cmd"]
        mount_idx = run_cmd.index("-v", run_cmd.index("-v") + 1)
        assert run_cmd[mount_idx + 1] == "/tmp/scaas/staging/dep_123/user_runner.py:/function/user_runner.py:ro"

    def test_start_container_raises_on_docker_error(self, svc):
        m = MagicMock()
        m.returncode = 1
        m.stderr = "image not found"
        with patch("subprocess.run", return_value=m), \
             patch.object(Path, "exists", return_value=True):
            with pytest.raises(RuntimeError, match="docker run failed"):
                svc.start_container("dep_x", FAKE_CODE_PATH, "main.h", 0.5, 256, 64)

    def test_start_container_raises_when_staged_runner_missing(self, svc):
        with patch("subprocess.run") as mock_run:
            with pytest.raises(RuntimeError, match="Runner file not found"):
                svc.start_container("dep_x", FAKE_CODE_PATH, "main.h", 0.5, 256, 64)
        mock_run.assert_called_once()


class TestInvokeFunction:

    def _make_run(self, output: dict):
        """Returns a side_effect function for subprocess.run."""
        call_count = {"n": 0}

        def fake_run(cmd, **kwargs):
            call_count["n"] += 1
            m = MagicMock()
            m.returncode = 0
            m.stderr = ""
            if call_count["n"] == 1:
                # First call: writing payload
                m.stdout = ""
            else:
                # Second call: exec
                m.stdout = json.dumps(output)
            return m

        return fake_run

    def test_invoke_returns_parsed_result(self, svc):
        expected = {"result": {"sum": 5}, "logs": "", "error": None, "duration_ms": 10}
        with patch("subprocess.run", side_effect=self._make_run(expected)):
            result = svc.invoke_function("c1", "main.handler", {"a": 2, "b": 3}, {})
        assert result["result"] == {"sum": 5}
        assert result["duration_ms"] == 10

    def test_invoke_passes_event_in_payload(self, svc):
        written_payloads = []
        call_count = {"n": 0}

        def capture_run(cmd, **kwargs):
            call_count["n"] += 1
            m = MagicMock()
            m.returncode = 0
            m.stderr = ""
            if call_count["n"] == 1:
                written_payloads.append(kwargs["input"])
                m.stdout = ""
            else:
                m.stdout = json.dumps({"result": None, "logs": "", "error": None, "duration_ms": 0})
            return m

        with patch("subprocess.run", side_effect=capture_run):
            svc.invoke_function("c1", "main.handler", {"key": "val"}, {"ctx": 1})

        assert '"key": "val"' in written_payloads[0]

    def test_invoke_raises_on_timeout(self, svc):
        def fake_run(cmd, **kwargs):
            if "sh" in cmd:
                m = MagicMock()
                m.returncode = 0
                m.stdout = ""
                m.stderr = ""
                return m
            raise subprocess.TimeoutExpired(cmd, 15)

        with patch("subprocess.run", side_effect=fake_run):
            with pytest.raises(TimeoutError):
                svc.invoke_function("c1", "main.handler", {}, {})

    def test_invoke_returns_error_dict_on_bad_json_output(self, svc):
        call_count = {"n": 0}

        def fake_run(cmd, **kwargs):
            call_count["n"] += 1
            m = MagicMock()
            m.returncode = 0
            m.stderr = ""
            m.stdout = "not json!!!" if call_count["n"] > 1 else ""
            return m

        with patch("subprocess.run", side_effect=fake_run):
            result = svc.invoke_function("c1", "main.handler", {}, {})

        assert result["result"] is None
        assert "Invalid JSON" in result["error"]


class TestStopContainer:

    def test_stop_calls_docker_rm(self, svc):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            svc.stop_container("dep_abc")
            mock_run.assert_called_once_with(
                ["docker", "rm", "-f", "dep_abc"],
                capture_output=True,
                timeout=10,
            )

    def test_stop_nonexistent_does_not_raise(self, svc):
        m = MagicMock()
        m.returncode = 1  # container not found — docker returns 1
        with patch("subprocess.run", return_value=m):
            svc.stop_container("ghost")  # should not raise
