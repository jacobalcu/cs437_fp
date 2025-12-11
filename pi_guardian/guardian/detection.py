from __future__ import annotations

import threading
from typing import Tuple

import cv2
import numpy as np

from .config import CONFIG, DetectionConfig


class PersonDetector:
    """Simple HOG/SVM-based person detector running on CPU."""

    def __init__(self, cfg: DetectionConfig | None = None):
        self.cfg = cfg or CONFIG.detection
        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        self._lock = threading.Lock()

    def detect(self, frame: np.ndarray) -> tuple[bool, list[Tuple[int, int, int, int]]]:
        with self._lock:
            boxes, weights = self._hog.detectMultiScale(
                frame,
                winStride=self.cfg.hog_win_stride,
                padding=self.cfg.hog_padding,
                scale=1.05,
            )
        filtered_boxes = []
        for (x, y, w, h), weight in zip(boxes, weights):
            if weight >= self.cfg.min_confidence:
                filtered_boxes.append((x, y, w, h))
        return bool(filtered_boxes), filtered_boxes


DETECTOR = PersonDetector()
