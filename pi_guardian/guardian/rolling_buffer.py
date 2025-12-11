from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque
import threading
import time
import uuid

import cv2
import numpy as np

from .config import CONFIG, BufferConfig


@dataclass(slots=True)
class FrameRecord:
    ts: float
    frame: np.ndarray


class RollingVideoBuffer:
    """Keeps a rolling window of frames for pre/post event recording."""

    def __init__(self, cfg: BufferConfig | None = None):
        self.cfg = cfg or CONFIG.buffer
        self._fps_hint = 24
        self.capacity = int((self.cfg.pre_event_seconds + self.cfg.post_event_seconds) * self._fps_hint)
        self.buffer: Deque[FrameRecord] = deque(maxlen=self.capacity)
        self._lock = threading.Lock()

    def add_frame(self, frame: np.ndarray, fps: int) -> None:
        with self._lock:
            self._fps_hint = fps or self._fps_hint
            self.buffer.append(FrameRecord(ts=time.time(), frame=frame.copy()))

    def snapshot(self) -> list[FrameRecord]:
        with self._lock:
            return list(self.buffer)

    def promote_to_clip(self, label: str) -> Path:
        frames = self.snapshot()
        if not frames:
            raise RuntimeError("No frames to export")
        clip_id = uuid.uuid4().hex
        out_path = self.cfg.media_root / f"{clip_id}_{label}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        height, width, _ = frames[0].frame.shape
        writer = cv2.VideoWriter(str(out_path), fourcc, self._fps_hint, (width, height))
        try:
            for rec in frames:
                # frames stored as RGB; VideoWriter expects BGR
                writer.write(cv2.cvtColor(rec.frame, cv2.COLOR_RGB2BGR))
        finally:
            writer.release()
        return out_path


BUFFER = RollingVideoBuffer()
