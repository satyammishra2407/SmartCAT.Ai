"""Append-only audit trail for geocoding attempts."""
from __future__ import annotations

import csv
from pathlib import Path
from threading import Lock


class AuditLogger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        if not self.path.exists():
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(
                    [
                        "row_id",
                        "query",
                        "level",
                        "provider",
                        "lat",
                        "lon",
                        "success",
                        "message",
                    ]
                )

    def log(
        self,
        row_id: str,
        query: str,
        level: int,
        provider: str,
        lat: float | None,
        lon: float | None,
        success: bool,
        message: str = "",
    ) -> None:
        with self._lock:
            with open(self.path, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(
                    [
                        row_id,
                        query[:2000],
                        level,
                        provider,
                        lat if lat is not None else "",
                        lon if lon is not None else "",
                        success,
                        message[:500],
                    ]
                )
