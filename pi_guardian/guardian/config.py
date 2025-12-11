from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os


@dataclass(slots=True)
class HardwareConfig:
    ultrasonic_trigger_pin: int | None = 23
    ultrasonic_echo_pin: int | None = 24
    privacy_led_pin: int | None = None
    flood_light_pin: int | None = None
    camera_index: int = 0
    camera_resolution: tuple[int, int] = (1280, 720)
    camera_fps: int = 20
    idle_distance_cm: float = 180.0
    trigger_distance_cm: float = 120.0
    confirm_distance_cm: float = 80.0


@dataclass(slots=True)
class DetectionConfig:
    confirmation_frames: int = 4
    min_confidence: float = 0.4
    hog_win_stride: tuple[int, int] = (8, 8)
    hog_padding: tuple[int, int] = (8, 8)


@dataclass(slots=True)
class BufferConfig:
    pre_event_seconds: int = 10
    post_event_seconds: int = 12
    max_disk_gb: int = 25
    media_root: Path = Path("storage/media")
    metadata_db: Path = Path("storage/events.db")


@dataclass(slots=True)
class WebRTCConfig:
    ice_servers: list[dict] = field(
        default_factory=lambda: [
            {"urls": ["stun:stun.l.google.com:19302"]},
        ]
    )
    audio_device: str | None = None
    mic_device: str | None = None


@dataclass(slots=True)
class NotificationConfig:
    apns_topic: str = "com.example.GuardianMobile"
    apns_device_tokens: list[str] = field(default_factory=list)


@dataclass(slots=True)
class HLSConfig:
    enabled: bool = True
    playlist_path: Path = Path("storage/media/hls/playlist.m3u8")
    segment_seconds: int = 1
    list_size: int = 3
    queue_size: int = 6
    ffmpeg_path: str = "ffmpeg"
    video_codec: str = "libx264"


@dataclass(slots=True)
class GuardianConfig:
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    buffer: BufferConfig = field(default_factory=BufferConfig)
    rtc: WebRTCConfig = field(default_factory=WebRTCConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    hls: HLSConfig = field(default_factory=HLSConfig)
    storage_key: bytes = field(default_factory=lambda: os.environ.get("GUARDIAN_STORAGE_KEY", "dev-key" * 4).encode())
    out_of_home: bool = False

    def ensure_dirs(self) -> None:
        self.buffer.media_root.mkdir(parents=True, exist_ok=True)
        self.buffer.metadata_db.parent.mkdir(parents=True, exist_ok=True)
        self.hls.playlist_path.parent.mkdir(parents=True, exist_ok=True)


CONFIG = GuardianConfig()
CONFIG.ensure_dirs()
