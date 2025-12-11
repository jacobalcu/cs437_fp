from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from .config import CONFIG

LOGGER = logging.getLogger(__name__)


class HLSStreamService:
    """Feeds camera frames into ffmpeg to maintain an HLS playlist as fallback."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[Optional[Tuple[np.ndarray, int]]] | None = None
        self._task: asyncio.Task[None] | None = None
        self._proc: subprocess.Popen[bytes] | None = None
        self._stdin: Optional[object] = None
        self._enabled = CONFIG.hls.enabled and shutil.which(CONFIG.hls.ffmpeg_path) is not None
        if CONFIG.hls.enabled and not self._enabled:
            LOGGER.warning("ffmpeg binary not found; disabling HLS fallback stream")

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def playlist_path(self) -> Path:
        return CONFIG.hls.playlist_path

    def playlist_ready(self) -> bool:
        return self.playlist_path.exists()

    async def start(self) -> None:
        if not self._enabled or self._task is not None:
            return
        CONFIG.hls.playlist_path.parent.mkdir(parents=True, exist_ok=True)
        self._purge_old_segments()
        self._queue = asyncio.Queue(maxsize=CONFIG.hls.queue_size)
        self._task = asyncio.create_task(self._writer_loop(), name="hls-writer")

    async def stop(self) -> None:
        if self._queue is not None:
            with contextlib.suppress(asyncio.QueueFull):
                await self._queue.put(None)
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._shutdown_process()
        self._queue = None

    def publish_frame(self, frame: np.ndarray, fps: int) -> None:
        if not self._enabled or self._queue is None:
            return
        payload = (np.ascontiguousarray(frame), fps)
        try:
            self._queue.put_nowait(payload)
        except asyncio.QueueFull:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    async def _writer_loop(self) -> None:
        assert self._queue is not None
        while True:
            item = await self._queue.get()
            if item is None:
                break
            frame, fps = item
            if frame is None:
                continue
            height, width, _ = frame.shape
            if self._proc is None or self._proc.poll() is not None:
                self._start_process(width, height, fps)
                if self._proc is None:
                    LOGGER.error("Unable to start ffmpeg process; stopping HLS service")
                    break
            try:
                await asyncio.to_thread(self._write_frame_bytes, frame)
            except (BrokenPipeError, ValueError):
                LOGGER.warning("HLS ffmpeg pipe closed unexpectedly; restarting")
                self._restart_process(width, height, fps)

    def _write_frame_bytes(self, frame: np.ndarray) -> None:
        if self._stdin is None:
            raise BrokenPipeError("stdin unavailable")
        self._stdin.write(frame.tobytes())  # type: ignore[arg-type]
        self._stdin.flush()

    def _start_process(self, width: int, height: int, fps: int) -> None:
        playlist = CONFIG.hls.playlist_path.resolve()
        playlist.parent.mkdir(parents=True, exist_ok=True)
        self._purge_old_segments()
        segment_pattern = playlist.parent / "segment_%03d.ts"
        cmd = [
            CONFIG.hls.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps),
            "-i",
            "-",
            "-c:v",
            CONFIG.hls.video_codec,
            "-preset",
            "veryfast",
            "-tune",
            "zerolatency",
            "-vf",
            "format=yuv420p",
            "-f",
            "hls",
            "-hls_time",
            str(CONFIG.hls.segment_seconds),
            "-hls_list_size",
            str(CONFIG.hls.list_size),
            "-hls_flags",
            "delete_segments+append_list",
            "-hls_segment_filename",
            str(segment_pattern),
            str(playlist),
        ]
        try:
            self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            self._stdin = self._proc.stdin
            LOGGER.info("Started ffmpeg HLS writer pid=%s -> %s", self._proc.pid, playlist)
        except FileNotFoundError:
            LOGGER.error("ffmpeg binary not found at %s", CONFIG.hls.ffmpeg_path)
            self._proc = None
            self._stdin = None

    def _restart_process(self, width: int, height: int, fps: int) -> None:
        self._shutdown_process()
        self._start_process(width, height, fps)

    def _shutdown_process(self) -> None:
        if self._stdin is not None:
            try:
                self._stdin.close()
            except Exception:
                pass
            self._stdin = None
        if self._proc is not None:
            self._proc.terminate()
            with contextlib.suppress(Exception):
                self._proc.wait(timeout=2)
            self._proc = None

    def _purge_old_segments(self) -> None:
        playlist = CONFIG.hls.playlist_path
        parent = playlist.parent
        if playlist.exists():
            playlist.unlink(missing_ok=True)
        if parent.exists():
            for segment in parent.glob("*.ts"):
                segment.unlink(missing_ok=True)


HLS_STREAM = HLSStreamService()
