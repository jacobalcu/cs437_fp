from __future__ import annotations

import asyncio
import contextlib
import fractions
import logging
from typing import Any

import numpy as np

import av
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription, RTCRtpSender
from aiortc.contrib.media import MediaPlayer, MediaRecorder

from .config import CONFIG
from .hardware import CAMERA


LOGGER = logging.getLogger(__name__)


class CameraVideoTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self):
        super().__init__()
        self._fps = CONFIG.hardware.camera_fps
        self._ts = 0
        self._logged = 0

    async def recv(self) -> av.VideoFrame:
        frame_array = await asyncio.to_thread(CAMERA.capture_frame)
        if frame_array.mean() < 1:
            LOGGER.warning("WebRTC captured black frame (mean<1); substituting gray test frame")
            frame_array = np.full_like(frame_array, 64)
        frame = av.VideoFrame.from_ndarray(frame_array, format="rgb24")
        frame.pts = self._ts
        self._ts += 1
        frame.time_base = fractions.Fraction(1, self._fps)
        if self._logged < 3:
            LOGGER.info("WebRTC send frame %s shape=%s mean=%.2f", self._logged, frame_array.shape, float(frame_array.mean()))
            self._logged += 1
        return frame


class WebRTCManager:
    def __init__(self):
        self._pcs: set[RTCPeerConnection] = set()

    async def handle_offer(self, offer: dict[str, Any]) -> dict[str, Any]:
        pc = RTCPeerConnection()
        self._pcs.add(pc)
        player = MediaPlayer(CONFIG.rtc.mic_device) if CONFIG.rtc.mic_device else None
        recorder = MediaRecorder(CONFIG.rtc.audio_device) if CONFIG.rtc.audio_device else None

        @pc.on("connectionstatechange")
        async def _on_state_change():
            LOGGER.info("WebRTC pc state=%s", pc.connectionState)
            if pc.connectionState in {"failed", "closed", "disconnected"}:
                await self._cleanup_pc(pc)

        @pc.on("iceconnectionstatechange")
        async def _on_ice_change():
            LOGGER.info("WebRTC ice state=%s", pc.iceConnectionState)

        rtc_offer = RTCSessionDescription(sdp=offer["sdp"], type=offer["type"])
        await pc.setRemoteDescription(rtc_offer)

        # Video: send track; prefer H264 if available.
        video_track = CameraVideoTrack()
        video_sender = pc.addTrack(video_track)
        try:
            video_codecs = [c for c in RTCRtpSender.getCapabilities("video").codecs if c.mimeType.lower().startswith("video/")]
            h264 = [c for c in video_codecs if c.mimeType.lower() == "video/h264"]
            vp8 = [c for c in video_codecs if c.mimeType.lower() == "video/vp8"]
            preferred = h264 or vp8 or video_codecs
            if preferred:
                video_sender.setCodecPreferences(preferred)
        except Exception:
            pass

        # Audio (optional): mirror send if mic configured; receive audio into recorder if configured.
        if player and player.audio:
            audio_sender = pc.addTrack(player.audio)
            try:
                audio_codecs = [c for c in RTCRtpSender.getCapabilities("audio").codecs if c.mimeType.lower().startswith("audio/")]
                opus = [c for c in audio_codecs if c.mimeType.lower() == "audio/opus"]
                preferred = opus or audio_codecs
                if preferred:
                    audio_sender.setCodecPreferences(preferred)
            except Exception:
                pass

        if recorder:
            @pc.on("track")
            async def _on_track(track):
                if track.kind == "audio":
                    recorder.addTrack(track)
                    await recorder.start()

        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        await self._wait_for_ice_gathering(pc)
        return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type, "iceServers": CONFIG.rtc.ice_servers}

    async def _cleanup_pc(self, pc: RTCPeerConnection) -> None:
        if pc in self._pcs:
            self._pcs.remove(pc)
        await pc.close()

    async def close_all(self) -> None:
        await asyncio.gather(*(pc.close() for pc in list(self._pcs)), return_exceptions=True)
        self._pcs.clear()

    @staticmethod
    async def _wait_for_ice_gathering(pc: RTCPeerConnection) -> None:
        if pc.iceGatheringState == "complete":
            return

        loop = asyncio.get_running_loop()
        done = loop.create_future()

        @pc.on("icegatheringstatechange")
        async def _on_ice_state():
            if pc.iceGatheringState == "complete" and not done.done():
                done.set_result(True)

        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(done, timeout=8)


WEBRTC = WebRTCManager()
