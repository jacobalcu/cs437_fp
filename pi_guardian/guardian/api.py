from __future__ import annotations

import asyncio
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .config import CONFIG
from .event_engine import ENGINE
from .rolling_buffer import BUFFER
from .hls import HLS_STREAM
from .storage import STORE
from .webrtc import WEBRTC

START_TS = time.time()


class ModeRequest(BaseModel):
    out_of_home: bool = Field(..., description="True when the porch should trigger events")


class LightRequest(BaseModel):
    on: bool


class ManualRecordRequest(BaseModel):
    label: str = "manual"


class PushTokenRequest(BaseModel):
    token: str


class WebRTCOffer(BaseModel):
    sdp: str
    type: str


def build_app() -> FastAPI:
    app = FastAPI(title="Guardian Edge API", version="0.1.0", default_response_class=JSONResponse)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def _startup() -> None:
        await ENGINE.start()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await ENGINE.stop()
        await WEBRTC.close_all()

    @app.get("/api/health")
    async def get_health() -> dict[str, float | str]:
        return {"uptime_s": time.time() - START_TS, "out_of_home": ENGINE.out_of_home, "version": app.version}

    @app.get("/api/system/state")
    async def get_state() -> dict[str, object]:
        return {
            "out_of_home": ENGINE.out_of_home,
            "ice_servers": CONFIG.rtc.ice_servers,
            "storage_root": str(CONFIG.buffer.media_root),
        }

    @app.post("/api/system/mode")
    async def set_mode(payload: ModeRequest) -> dict[str, bool]:
        ENGINE.set_out_of_home(payload.out_of_home)
        return {"out_of_home": ENGINE.out_of_home}

    @app.post("/api/control/light")
    async def set_light(payload: LightRequest) -> dict[str, bool]:
        ENGINE.toggle_light(payload.on)
        return {"light": payload.on}

    @app.post("/api/control/privacy")
    async def set_privacy(payload: LightRequest) -> dict[str, bool]:
        ENGINE.set_privacy_led(payload.on)
        return {"privacy_led": payload.on}

    @app.post("/api/events/manual-record")
    async def manual_record(payload: ManualRecordRequest):
        clip_path = BUFFER.promote_to_clip(payload.label)
        clip_id = Path(clip_path).stem.split("_")[0]
        # Approximate duration using configured pre/post window
        STORE.add_event(
            clip_id,
            clip_path,
            duration=CONFIG.buffer.pre_event_seconds + CONFIG.buffer.post_event_seconds,
            label=payload.label,
        )
        return {"clip": clip_path.name, "id": clip_id}

    @app.get("/api/events/recordings")
    async def list_recordings() -> list[dict[str, object]]:
        items = STORE.list_events()
        for item in items:
            item["download_url"] = f"/api/events/recordings/{item['id']}"
        return items

    @app.get("/api/events/recordings/{clip_id}")
    async def download_clip(clip_id: str, request: Request):
        matches = [e for e in STORE.list_events() if e["id"] == clip_id]
        if not matches:
            raise HTTPException(status_code=404, detail="Clip not found")
        clip_path = Path(matches[0]["clip_path"])
        if not clip_path.exists():
            raise HTTPException(status_code=410, detail="Clip missing")

        file_size = clip_path.stat().st_size
        range_header = request.headers.get("range")
        if range_header:
            # Parse Range: bytes=start-end
            units, _, range_spec = range_header.partition("=")
            if units.strip() != "bytes":
                raise HTTPException(status_code=416, detail="Unsupported range unit")
            start_str, _, end_str = range_spec.partition("-")
            try:
                start = int(start_str) if start_str else 0
                end = int(end_str) if end_str else file_size - 1
            except ValueError:
                raise HTTPException(status_code=416, detail="Invalid range")
            end = min(end, file_size - 1)
            if start >= file_size or start < 0:
                raise HTTPException(status_code=416, detail="Range not satisfiable")

            chunk_size = 1024 * 1024

            def iter_file() -> iter[bytes]:
                with clip_path.open("rb") as f:
                    f.seek(start)
                    remaining = end - start + 1
                    while remaining > 0:
                        chunk = f.read(min(chunk_size, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk

            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(end - start + 1),
            }
            return StreamingResponse(iter_file(), status_code=206, media_type="video/mp4", headers=headers)

        return FileResponse(clip_path, media_type="video/mp4")

    @app.post("/api/events/live/webrtc-offer")
    async def webrtc_offer(payload: WebRTCOffer):
        answer = await WEBRTC.handle_offer(payload.model_dump())
        return answer

    @app.get("/api/events/live/hls/{filename}")
    async def hls_files(filename: str):
        if not HLS_STREAM.enabled:
            raise HTTPException(status_code=503, detail="HLS disabled or ffmpeg missing on Pi")
        file_path = CONFIG.buffer.media_root / "hls" / filename
        if not file_path.exists():
            if filename == "playlist.m3u8":
                raise HTTPException(status_code=202, detail="HLS playlist not ready; warming up")
            raise HTTPException(status_code=404, detail="HLS asset missing")
        return FileResponse(file_path)

    @app.post("/api/push/register")
    async def register_push(payload: PushTokenRequest):
        if payload.token not in CONFIG.notifications.apns_device_tokens:
            CONFIG.notifications.apns_device_tokens.append(payload.token)
        return {"registered": True}

    return app
