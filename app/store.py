"""
Thread-safe in-memory store for active deployments.
In production this would be backed by Redis or a DB.
"""

import threading
from typing import Any, Optional


class DeploymentStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, Any]] = {}

    def put(self, deployment_id: str, record: dict[str, Any]) -> None:
        with self._lock:
            self._data[deployment_id] = record

    def get(self, deployment_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            return self._data.get(deployment_id)

    def remove(self, deployment_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            return self._data.pop(deployment_id, None)

    def all_ids(self) -> list[str]:
        with self._lock:
            return list(self._data.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)
