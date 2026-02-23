"""Beginner-friendly Codespaces webcam -> Gemini Live relay demo.

Run:
  uvicorn app:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

try:
    from google import genai
    from google.genai import types
except Exception as exc:  # pragma: no cover - optional dependency during setup
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]
    _GENAI_IMPORT_ERROR = exc
else:
    _GENAI_IMPORT_ERROR = None


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("codespace_gemini_browser_demo")

PROJECT_DIR = Path(__file__).resolve().parent
STATIC_DIR = PROJECT_DIR / "static"

app = FastAPI(title="Codespace Gemini Browser Demo")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class GeminiLiveBridge:
    """Tiny wrapper around Gemini Live API for this one websocket client."""

    def __init__(self) -> None:
        self.model = os.environ.get("GEMINI_LIVE_MODEL", "gemini-live-2.5-flash-preview")
        self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.client = None
        self.session = None
        self._session_context_manager = None

    async def connect(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "GEMINI_API_KEY is not set. Running in local echo mode."

        if genai is None:
            return False, f"google-genai import failed: {_GENAI_IMPORT_ERROR}"

        # Before example: create one-off requests per frame (high latency).
        # After example: keep one Live session open and stream frames into it.
        try:
            self.client = genai.Client(api_key=self.api_key)
            config = {"response_modalities": ["TEXT"]}
            self._session_context_manager = self.client.aio.live.connect(
                model=self.model,
                config=config,
            )
            self.session = await self._session_context_manager.__aenter__()
            return True, f"Connected to Gemini Live model={self.model}"
        except Exception as exc:
            LOGGER.exception("gemini_connect_failed")
            return False, f"Gemini connect failed ({exc}). Running in local echo mode."

    async def close(self) -> None:
        if self._session_context_manager is not None:
            await self._session_context_manager.__aexit__(None, None, None)
        self.session = None
        self._session_context_manager = None

    async def send_text(self, user_text: str) -> None:
        if self.session is None:
            return
        await self.session.send_client_content(turns=user_text, turn_complete=True)

    async def send_video_frame(self, jpeg_bytes: bytes) -> None:
        if self.session is None or types is None:
            return
        await self.session.send_realtime_input(
            video=types.Blob(data=jpeg_bytes, mime_type="image/jpeg")
        )

    async def receive_text(self, send_to_browser) -> None:
        """Read Gemini messages and forward readable text to the browser."""
        if self.session is None:
            return

        try:
            async for response in self.session.receive():
                text = _extract_text(response)
                if text:
                    LOGGER.info("gemini_text=%s", text.replace("\n", " "))
                    await send_to_browser({"type": "assistant_text", "text": text})
        except Exception as exc:
            LOGGER.exception("gemini_receive_failed")
            await send_to_browser(
                {"type": "status", "text": f"Gemini receive error: {exc}"}
            )


def _extract_text(response) -> str:
    direct_text = getattr(response, "text", None)
    if direct_text:
        return str(direct_text)

    server_content = getattr(response, "server_content", None)
    model_turn = getattr(server_content, "model_turn", None) if server_content else None
    parts = getattr(model_turn, "parts", None) if model_turn else None
    if not parts:
        return ""

    chunks: list[str] = []
    for part in parts:
        part_text = getattr(part, "text", None)
        if part_text:
            chunks.append(str(part_text))
    return "".join(chunks).strip()


class BrowserSession:
    """Handles one browser websocket connection from start to finish."""

    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        self.bridge = GeminiLiveBridge()
        self.frame_count = 0
        self.receive_task: Optional[asyncio.Task] = None
        self.gemini_connected = False

    async def run(self) -> None:
        await self.websocket.accept()
        LOGGER.info("browser_connected client=%s", self.websocket.client)
        await self._send_json({"type": "status", "text": "Browser connected to backend."})

        connected, status_message = await self.bridge.connect()
        self.gemini_connected = connected
        await self._send_json({"type": "status", "text": status_message})
        LOGGER.info(status_message)

        if self.gemini_connected:
            self.receive_task = asyncio.create_task(self.bridge.receive_text(self._send_json))

        try:
            while True:
                raw_text = await self.websocket.receive_text()
                message = json.loads(raw_text)
                await self._handle_message(message)
        except WebSocketDisconnect:
            LOGGER.info("browser_disconnected")
        finally:
            if self.receive_task:
                self.receive_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self.receive_task
            await self.bridge.close()

    async def _handle_message(self, message: dict) -> None:
        kind = message.get("type")
        if kind == "video_frame":
            await self._handle_video_frame(message)
            return

        if kind == "user_text":
            user_text = str(message.get("text", "")).strip()
            if not user_text:
                return
            LOGGER.info("user_text=%s", user_text.replace("\n", " "))
            await self._send_json({"type": "echo_user", "text": user_text})
            if self.gemini_connected:
                await self.bridge.send_text(user_text)
            else:
                # Before example: no API key -> app appears broken.
                # After example: no API key -> user still sees local feedback.
                await self._send_json(
                    {"type": "assistant_text", "text": f"(local mode) You said: {user_text}"}
                )
            return

        await self._send_json({"type": "status", "text": f"Unknown message type: {kind}"})

    async def _handle_video_frame(self, message: dict) -> None:
        data_url = str(message.get("data", ""))
        if "," in data_url:
            _, base64_data = data_url.split(",", 1)
        else:
            base64_data = data_url

        try:
            frame_bytes = base64.b64decode(base64_data)
        except Exception:
            await self._send_json({"type": "status", "text": "Failed to decode frame."})
            return

        self.frame_count += 1
        if self.frame_count % 10 == 0:
            LOGGER.info("frames_received=%s", self.frame_count)

        if self.gemini_connected:
            await self.bridge.send_video_frame(frame_bytes)

    async def _send_json(self, payload: dict) -> None:
        await self.websocket.send_json(payload)


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    session = BrowserSession(websocket)
    await session.run()
