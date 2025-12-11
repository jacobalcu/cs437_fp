from __future__ import annotations

import sys
import time

import numpy as np

try:
    import cv2
except Exception:
    cv2 = None

try:
    from picamera2 import Picamera2
except Exception:
    Picamera2 = None


def test_picamera2(frames: int = 5, save_first: bool = True) -> None:
    if Picamera2 is None:
        print("Picamera2 not available")
        return
    cam = Picamera2()
    cam.configure(cam.create_still_configuration(main={"size": (1280, 720), "format": "RGB888"}))
    cam.start()
    time.sleep(0.5)
    for i in range(frames):
        frame = cam.capture_array()
        mean_val = float(np.mean(frame))
        print(f"picamera2 frame {i}: shape={frame.shape} mean={mean_val:.2f}")
        if i == 0 and save_first and cv2 is not None:
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            cv2.imwrite("test_picamera2_frame0.jpg", bgr)
            print("saved test_picamera2_frame0.jpg")
        time.sleep(0.1)
    cam.stop()


def test_opencv(device: int = 0, frames: int = 5, save_first: bool = True) -> None:
    if cv2 is None:
        print("OpenCV not available")
        return
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        print(f"OpenCV could not open device {device}")
        return
    for i in range(frames):
        ok, frame = cap.read()
        if not ok:
            print(f"OpenCV frame {i}: read failed")
            break
        mean_val = float(np.mean(frame))
        print(f"OpenCV frame {i}: shape={frame.shape} mean={mean_val:.2f}")
        if i == 0 and save_first:
            cv2.imwrite("test_opencv_frame0.jpg", frame)
            print("saved test_opencv_frame0.jpg")
        time.sleep(0.1)
    cap.release()


def main() -> None:
    print("Testing Picamera2...")
    test_picamera2()
    print("\nTesting OpenCV device 0...")
    test_opencv(0)


if __name__ == "__main__":
    main()
