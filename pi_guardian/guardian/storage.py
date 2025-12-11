from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .config import CONFIG, BufferConfig


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    created_ts REAL NOT NULL,
    label TEXT NOT NULL,
    clip_path TEXT NOT NULL,
    thumbnail_path TEXT,
    duration REAL,
    metadata TEXT
);
"""


class EventStore:
    def __init__(self, cfg: BufferConfig | None = None):
        self.cfg = cfg or CONFIG.buffer
        self.db_path = self.cfg.metadata_db
        self._ensure_db()

    def _ensure_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(SCHEMA)
        finally:
            conn.close()

    def add_event(self, event_id: str, clip_path: Path, duration: float, label: str, metadata: dict[str, Any] | None = None, thumbnail_path: Path | None = None) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO events (id, created_ts, label, clip_path, thumbnail_path, duration, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    time.time(),
                    label,
                    str(clip_path),
                    str(thumbnail_path) if thumbnail_path else None,
                    duration,
                    json.dumps(metadata or {}),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def list_events(self) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute("SELECT id, created_ts, label, clip_path, thumbnail_path, duration, metadata FROM events ORDER BY created_ts DESC").fetchall()
            events = []
            for row in rows:
                events.append(
                    {
                        "id": row[0],
                        "created_ts": row[1],
                        "label": row[2],
                        "clip_path": row[3],
                        "thumbnail_path": row[4],
                        "duration": row[5],
                        "metadata": json.loads(row[6]) if row[6] else {},
                    }
                )
            return events
        finally:
            conn.close()


STORE = EventStore()
