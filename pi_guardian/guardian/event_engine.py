from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .config import CONFIG
from .detection import DETECTOR
from .hardware import CAMERA, LEDS, SENSOR
from .hls import HLS_STREAM
from .notifications import NOTIFIER
from .rolling_buffer import BUFFER
from .storage import STORE


class EventEngine:
    def __init__(self):
        self._tasks: set[asyncio.Task[Any]] = set()
        self._shutdown = asyncio.Event()
        self._armed_until = 0.0
        self._confirm_counter = 0
        self._last_boxes: list[tuple[int, int, int, int]] = []
        self.out_of_home = CONFIG.out_of_home
        self._fps = CONFIG.hardware.camera_fps

    async def start(self) -> None:
        CAMERA.start()
        await HLS_STREAM.start()
        self._tasks.add(asyncio.create_task(self._frame_loop(), name="frame-loop"))
        self._tasks.add(asyncio.create_task(self._sensor_loop(), name="sensor-loop"))

    async def stop(self) -> None:
        self._shutdown.set()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await HLS_STREAM.stop()
        CAMERA.stop()
        await NOTIFIER.close()

    async def _frame_loop(self) -> None:
        frame_period = 1 / CONFIG.hardware.camera_fps
        while not self._shutdown.is_set():
            frame = await asyncio.to_thread(CAMERA.capture_frame)
            BUFFER.add_frame(frame, CONFIG.hardware.camera_fps)
            HLS_STREAM.publish_frame(frame, CONFIG.hardware.camera_fps)
            if self.out_of_home and time.time() < self._armed_until:
                await self._run_detection(frame)
            await asyncio.sleep(frame_period * 0.2)

    async def _sensor_loop(self) -> None:
        async for distance in SENSOR.readings():
            if self._shutdown.is_set():
                break
            if not self.out_of_home:
                continue
            if distance < CONFIG.hardware.trigger_distance_cm:
                self._armed_until = time.time() + CONFIG.buffer.post_event_seconds
            await asyncio.sleep(0.1)

    async def _run_detection(self, frame: np.ndarray) -> None:
        detected, boxes = await asyncio.to_thread(DETECTOR.detect, frame)
        if detected:
            self._confirm_counter += 1
            self._last_boxes = boxes
        else:
            self._confirm_counter = 0
        if self._confirm_counter >= CONFIG.detection.confirmation_frames:
            self._confirm_counter = 0
            await self._promote_event(frame)

    async def _promote_event(self, frame: np.ndarray) -> None:
        clip_path = BUFFER.promote_to_clip("person")
        clip_id = Path(clip_path).stem.split("_")[0]
        thumb_path = clip_path.with_suffix(".jpg")
        cv2.imwrite(str(thumb_path), frame)
        STORE.add_event(clip_id, clip_path, duration=CONFIG.buffer.pre_event_seconds + CONFIG.buffer.post_event_seconds, label="person", metadata={"boxes": self._last_boxes})
        await NOTIFIER.push_snapshot(thumb_path, "Visitor detected", "Tap to open live feed")

    def set_out_of_home(self, state: bool) -> None:
        self.out_of_home = state
        CONFIG.out_of_home = state
        LEDS.set_privacy(state)

    def toggle_light(self, state: bool) -> None:
        LEDS.set_flood(state)

    def set_privacy_led(self, state: bool) -> None:
        LEDS.set_privacy(state)


ENGINE = EventEngine()
