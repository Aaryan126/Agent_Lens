from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from pydantic import BaseModel


class AuditLog:
    def append(self, event_type: str, payload: BaseModel | dict[str, Any]) -> None:
        raise NotImplementedError

    def read_all(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class NullAuditLog(AuditLog):
    def append(self, event_type: str, payload: BaseModel | dict[str, Any]) -> None:
        return None

    def read_all(self) -> list[dict[str, Any]]:
        return []


class JsonlAuditLog(AuditLog):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = RLock()

    def append(self, event_type: str, payload: BaseModel | dict[str, Any]) -> None:
        record = {
            "event_type": event_type,
            "created_at": datetime.now(UTC).isoformat(),
            "payload": self._serialize_payload(payload),
        }
        line = json.dumps(record, separators=(",", ":"))
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(f"{line}\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self._lock:
            records: list[dict[str, Any]] = []
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
            return records

    def _serialize_payload(self, payload: BaseModel | dict[str, Any]) -> dict[str, Any]:
        if isinstance(payload, BaseModel):
            return payload.model_dump(mode="json")
        return payload
