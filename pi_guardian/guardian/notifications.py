from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import httpx

from .config import CONFIG, NotificationConfig


class Notifier:
    """Placeholder APNs integration via a lightweight HTTP relay."""

    def __init__(self, cfg: NotificationConfig | None = None):
        self.cfg = cfg or CONFIG.notifications
        self._client = httpx.AsyncClient(timeout=5.0)

    async def push_snapshot(self, image_path: Path, title: str, body: str) -> None:
        if not self.cfg.apns_device_tokens:
            return
        payload = {
            "topic": self.cfg.apns_topic,
            "tokens": self.cfg.apns_device_tokens,
            "alert": {"title": title, "body": body},
            "mutable-content": 1,
        }
        files = {"snapshot": image_path.read_bytes()} if image_path.exists() else None
        await self._client.post("http://localhost:9000/apns", data={"payload": json.dumps(payload)}, files=files)

    async def close(self) -> None:
        await self._client.aclose()


NOTIFIER = Notifier()
