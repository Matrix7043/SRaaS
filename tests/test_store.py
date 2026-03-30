"""
Unit tests for the thread-safe DeploymentStore.
"""

import threading
import pytest
from app.store import DeploymentStore


class TestDeploymentStore:

    def test_put_and_get(self):
        s = DeploymentStore()
        s.put("d1", {"k": "v"})
        assert s.get("d1") == {"k": "v"}

    def test_get_missing_returns_none(self):
        s = DeploymentStore()
        assert s.get("nope") is None

    def test_remove_returns_record(self):
        s = DeploymentStore()
        s.put("d1", {"x": 1})
        removed = s.remove("d1")
        assert removed == {"x": 1}
        assert s.get("d1") is None

    def test_remove_missing_returns_none(self):
        s = DeploymentStore()
        assert s.remove("ghost") is None

    def test_len(self):
        s = DeploymentStore()
        assert len(s) == 0
        s.put("a", {})
        s.put("b", {})
        assert len(s) == 2
        s.remove("a")
        assert len(s) == 1

    def test_all_ids(self):
        s = DeploymentStore()
        s.put("x", {})
        s.put("y", {})
        ids = s.all_ids()
        assert set(ids) == {"x", "y"}

    def test_put_overwrites_existing(self):
        s = DeploymentStore()
        s.put("d1", {"v": 1})
        s.put("d1", {"v": 2})
        assert s.get("d1") == {"v": 2}

    def test_concurrent_puts_are_safe(self):
        """Stress test: 100 threads each writing a unique key."""
        s = DeploymentStore()
        threads = []
        for i in range(100):
            t = threading.Thread(target=s.put, args=(f"k{i}", {"i": i}))
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(s) == 100

    def test_concurrent_reads_and_writes_are_safe(self):
        s = DeploymentStore()
        s.put("shared", {"count": 0})
        errors = []

        def reader():
            try:
                for _ in range(50):
                    s.get("shared")
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(50):
                    s.put("shared", {"count": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(5)]
        threads += [threading.Thread(target=writer) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
