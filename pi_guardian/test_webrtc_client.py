"""Simple receive-only WebRTC smoke test against the Guardian backend.

Run on your laptop (with the Pi reachable):
  python3 test_webrtc_client.py --url http://192.168.50.137:9001

It prints the first video frame dimensions and optionally saves it to PNG if
`imageio` is installed. This verifies that the server returns an answer with
ICE candidates and that media flows.
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Optional

import requests
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRecorder

try:
    import imageio.v3 as iio  # type: ignore
except Exception:  # pragma: no cover
    iio = None


async def wait_for_ice_complete(pc: RTCPeerConnection, timeout: float = 3.0) -> None:
    if pc.iceGatheringState == "complete":
        return

    loop = asyncio.get_event_loop()
    done = loop.create_future()

    @pc.on("icegatheringstatechange")
    async def _on_state_change() -> None:
        if pc.iceGatheringState == "complete" and not done.done():
            done.set_result(True)

    try:
        await asyncio.wait_for(done, timeout=timeout)
    except asyncio.TimeoutError:
        pass


async def grab_first_frame(track, output_png: Optional[str]) -> None:
    frame = await track.recv()
    arr = frame.to_ndarray(format="rgb24")
    print(f"Received frame: {arr.shape[1]}x{arr.shape[0]} (RGB)")
    if output_png and iio is not None:
        iio.imwrite(output_png, arr)
        print(f"Saved first frame to {output_png}")
    elif output_png:
        print("imageio not installed; skipping PNG save")


FIRST_FRAME_TIMEOUT = 20


async def main(url: str, save_png: Optional[str], dump: bool) -> None:
    pc = RTCPeerConnection()

    # Receive-only transceivers
    pc.addTransceiver("video", direction="recvonly")
    pc.addTransceiver("audio", direction="recvonly")

    # Prefer H264 if available to match server capability.
    try:
        from aiortc import RTCRtpSender  # import locally to keep optional

        video_codecs = [
            c
            for c in RTCRtpSender.getCapabilities("video").codecs
            if c.mimeType.lower().startswith("video/")
        ]
        h264 = [c for c in video_codecs if c.mimeType.lower() == "video/h264"]
        vp8 = [c for c in video_codecs if c.mimeType.lower() == "video/vp8"]
        preferred = h264 or vp8 or video_codecs
        for transceiver in pc.getTransceivers():
            if transceiver.kind == "video" and preferred:
                transceiver.setCodecPreferences(preferred)
    except Exception:
        # Codec tuning is best-effort only
        pass

    # --- FIRST: prepare first-frame coordination + event handlers ---

    first_frame_done = asyncio.Event()

    async def _handle_video(track):
        # grab_first_frame() comes from the same file you already have
        await grab_first_frame(track, save_png)
        first_frame_done.set()

    @pc.on("iceconnectionstatechange")
    def on_ice_state_change():
        print("ICE state:", pc.iceConnectionState)

    @pc.on("connectionstatechange")
    def on_conn_state_change():
        print("Peer connection state:", pc.connectionState)

    @pc.on("track")
    def on_track(track):
        print("Got track:", track.kind)
        if track.kind == "video":
            asyncio.create_task(_handle_video(track))
        elif track.kind == "audio":
            # optional: just sink audio to /dev/null
            from aiortc.contrib.media import MediaRecorder

            recorder = MediaRecorder("/dev/null")
            recorder.addTrack(track)
            asyncio.create_task(recorder.start())

    # --- THEN: create offer, send to server, apply answer ---

    # Prepare offer
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    await wait_for_ice_complete(pc)

    # Send to backend
    payload = {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    if dump:
        Path("offer.sdp").write_text(pc.localDescription.sdp)

    resp = requests.post(f"{url}/api/events/live/webrtc-offer", json=payload, timeout=10)
    if not resp.ok:
        print("Server error status:", resp.status_code)
        print("Body:", resp.text)
        await pc.close()
        return

    answer = resp.json()
    print("Answer keys:", list(answer.keys()))
    ice_servers = answer.get("iceServers")
    print("ICE servers from server:", ice_servers)

    if dump:
        Path("answer.json").write_text(json.dumps(answer, indent=2))

    # IMPORTANT: handlers are already attached at this point.
    await pc.setRemoteDescription(
        RTCSessionDescription(answer["sdp"], answer.get("type", "answer"))
    )

    if dump:
        Path("answer.sdp").write_text(answer["sdp"])

    # Wait for first frame
    try:
        await asyncio.wait_for(first_frame_done.wait(), timeout=FIRST_FRAME_TIMEOUT)
    except asyncio.TimeoutError:
        print(f"No video frame received within {FIRST_FRAME_TIMEOUT}s")

    # Close the connection cleanly
    await pc.close()



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Guardian WebRTC receive-only client")
    parser.add_argument("--url", default="http://192.168.50.137:9001", help="Base URL of Guardian backend")
    parser.add_argument("--png", default=None, help="Optional path to save first frame as PNG (requires imageio)")
    parser.add_argument("--dump", action="store_true", help="Dump offer/answer SDP to offer.sdp/answer.sdp")
    args = parser.parse_args()

    asyncio.run(main(args.url.rstrip("/"), args.png, args.dump))
