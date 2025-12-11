from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import AsyncIterator, Optional

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore

try:
    from picamera2 import Picamera2
except Exception:  # pragma: no cover
    Picamera2 = None  # type: ignore

try:
    from gpiozero import LED, DistanceSensor
except Exception:  # pragma: no cover - dev hosts without GPIO
    LED = None  # type: ignore
    DistanceSensor = None  # type: ignore

from .config import CONFIG, HardwareConfig


LOGGER = logging.getLogger(__name__)


class UltrasonicWatcher:
    """Async iterator yielding distance (cm) using gpiozero DistanceSensor."""

    def __init__(self, cfg: HardwareConfig | None = None):
        self.cfg = cfg or CONFIG.hardware
        self.sensor: Optional[DistanceSensor] = None
        if DistanceSensor is not None and self.cfg.ultrasonic_echo_pin is not None:
            try:
                self.sensor = DistanceSensor(
                    echo=self.cfg.ultrasonic_echo_pin,
                    trigger=self.cfg.ultrasonic_trigger_pin,
                    max_distance=max(1.0, self.cfg.idle_distance_cm / 100.0),
                )
            except Exception as exc:  # pragma: no cover - hardware only
                LOGGER.warning("Ultrasonic sensor unavailable: %s", exc)
                self.sensor = None

    def _read_distance_cm(self) -> float:
        if self.sensor is None:
            return float("inf")
        try:
            return float(self.sensor.distance * 100)
        except Exception:
            return float("inf")

    async def readings(self, interval: float = 0.2) -> AsyncIterator[float]:
        while True:
            yield await asyncio.to_thread(self._read_distance_cm)
            await asyncio.sleep(interval)


class IndicatorLeds:
    def __init__(self, cfg: HardwareConfig | None = None):
        self.cfg = cfg or CONFIG.hardware
        self.privacy_led = self._safe_led(self.cfg.privacy_led_pin)
        self.flood_light = self._safe_led(self.cfg.flood_light_pin)

    def _safe_led(self, pin: int | None):
        if LED is None or pin is None:
            return None
        try:
            return LED(pin)
        except Exception as exc:  # pragma: no cover - requires hardware
            LOGGER.warning("LED on pin %s unavailable: %s", pin, exc)
            return None

    def set_privacy(self, on: bool) -> None:
        if self.privacy_led:
            self.privacy_led.value = 1 if on else 0

    def set_flood(self, on: bool) -> None:
        if self.flood_light:
            self.flood_light.value = 1 if on else 0


class CameraPipeline:
    """Capture frames using Picamera2 with OpenCV VideoCapture fallback."""

    def __init__(self, cfg: HardwareConfig | None = None):
        self.cfg = cfg or CONFIG.hardware
        self.picam: Optional[Picamera2] = None
        self.started = False
        self._logged_black = False
        if Picamera2 is not None:
            try:
                self.picam = Picamera2()
            except Exception as exc:  # pragma: no cover
                LOGGER.warning("Unable to initialize Picamera2: %s", exc)
                self.picam = None

        if self.picam is None:
            raise RuntimeError("No camera backend available (Picamera2 missing)")

    def start(self) -> None:
        if self.started:
            return
        if self.picam is not None:
            fps = self.cfg.camera_fps
            res = self.cfg.camera_resolution
            video_cfg = self.picam.create_video_configuration(
                main={"size": res, "format": "RGB888"},
                controls={"FrameDurationLimits": (int(1e6 / fps), int(1e6 / fps))},
            )
            self.picam.configure(video_cfg)
            self.picam.start()
            # warm up a couple of frames
            for _ in range(3):
                with contextlib.suppress(Exception):
                    self.picam.capture_array()
            self.started = True

    def stop(self) -> None:
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
        if self.picam and self.started:
            self.picam.stop()
        self.started = False

    def capture_frame(self) -> np.ndarray:
        if not self.started:
            self.start()
        if self.picam is not None:
            frame = self.picam.capture_array()
            if np.mean(frame) < 1 and not self._logged_black:
                self._logged_black = True
                LOGGER.warning("Picamera2 capture appears black (mean<1); check sensor/lighting/lens cap")
            return frame
        raise RuntimeError("Camera capture unavailable")

    def record_h264(self, seconds: float, output_path: str) -> None:
        if not self.started:
            self.start()
        fps = self.cfg.camera_fps
        if self.cap is not None and cv2 is not None:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = None
            start = time.time()
            try:
                while time.time() - start < seconds:
                    frame = self.capture_frame()
                    if writer is None:
                        height, width, _ = frame.shape
                        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
                    writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            finally:
                if writer is not None:
                    writer.release()
            return
        if self.picam is None:
            raise RuntimeError("No recording backend available")
        with contextlib.ExitStack() as stack:
            encoder = self.picam.start_recording(encoder="main")
            try:
                stack.enter_context(encoder)
            except Exception:
                pass
            time.sleep(seconds)
            self.picam.stop_recording()


CAMERA = CameraPipeline()
LEDS = IndicatorLeds()
SENSOR = UltrasonicWatcher()
