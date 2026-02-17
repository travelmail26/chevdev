#!/usr/bin/env python3
"""Shared backend adapter for the existing Perplexity clone frontend.

This exposes a minimal API that maps web requests into the existing chefmain
MessageRouter + history storage so Telegram and web share the same session.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from queue import Queue
from threading import Thread

from flask import Flask, Response, jsonify, request, stream_with_context

from message_router import MessageRouter
from utilities.history_messages import get_full_history_message_object, get_user_bot_mode


APP = Flask(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_port() -> int:
    raw = os.getenv("PERPLEXITY_SHARED_BACKEND_PORT", "9002")
    cleaned = re.sub(r"[^0-9]", "", str(raw))
    return int(cleaned or "9002")


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _normalize_canonical_user_id(raw_uid: str | None) -> str:
    uid = str(raw_uid or "").strip()
    if not uid:
        return ""
    # Before example: web used "tg_1275063227" while Telegram used "1275063227", splitting history.
    # After example:  both map to "1275063227" for one shared session.
    if uid.startswith("tg_") and uid[3:].isdigit():
        return uid[3:]
    return uid


def _build_message_object(uid: str, message: str, source: str, bot_mode: str | None = None) -> dict:
    now = time.time()
    mode = (bot_mode or "").strip().lower()
    if not mode:
        mode = get_user_bot_mode(uid)
    if not mode:
        mode = "general"

    return {
        "user_id": str(uid),
        "session_info": {
            "user_id": str(uid),
            "chat_id": str(uid),
            "message_id": int(now * 1000),
            "timestamp": now,
            "timestamp_iso": _now_iso(),
            "username": str(uid),
            "first_name": "Shared",
            "last_name": "Session",
        },
        "bot_mode": mode,
        "source_interface": source,
        "user_message": str(message or ""),
    }


def _extract_session_payload(uid: str, bot_mode: str | None = None) -> dict:
    mode = (bot_mode or "").strip().lower() or get_user_bot_mode(uid) or "general"
    doc = get_full_history_message_object(uid, bot_mode=mode) or {}
    return {
        "canonical_user_id": uid,
        "bot_mode": mode,
        "active_session_id": doc.get("chat_session_id"),
        "message_count": len(doc.get("messages", [])),
        "messages": doc.get("messages", []),
    }


@APP.get("/health")
def health():
    return jsonify({"ok": True, "service": "perplexity_clone_shared_backend"})


@APP.get("/")
def root():
    return jsonify(
        {
            "ok": True,
            "service": "perplexity_clone_shared_backend",
            "chat_path": "/api/chat",
            "session_path_example": "/api/session/<canonical_user_id>",
        }
    )


@APP.get("/api/session/<canonical_user_id>")
def session(canonical_user_id: str):
    uid = _normalize_canonical_user_id(canonical_user_id)
    if not uid:
        return jsonify({"message": "canonical_user_id is required"}), 400
    bot_mode = str(request.args.get("bot_mode", "")).strip().lower()
    return jsonify(_extract_session_payload(uid, bot_mode=bot_mode))


@APP.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    uid = _normalize_canonical_user_id(payload.get("canonical_user_id", ""))
    message = str(payload.get("message", "")).strip()
    source = str(payload.get("source", "web")).strip().lower() or "web"
    bot_mode = str(payload.get("bot_mode", "")).strip().lower()
    stream_enabled = bool(payload.get("stream"))

    if not uid:
        return jsonify({"message": "canonical_user_id is required"}), 400
    if not message:
        return jsonify({"message": "message is required"}), 400
    if source not in {"web", "telegram"}:
        return jsonify({"message": "source must be one of: web, telegram"}), 400

    if not stream_enabled:
        router = MessageRouter()
        message_object = _build_message_object(uid=uid, message=message, source=source, bot_mode=bot_mode)
        assistant_text = router.route_message(message_object=message_object)
        session_payload = _extract_session_payload(uid, bot_mode=message_object.get("bot_mode"))

        return jsonify(
            {
                "canonical_user_id": uid,
                "bot_mode": session_payload.get("bot_mode"),
                "active_session_id": session_payload.get("active_session_id"),
                "assistant_text": assistant_text,
                "thinking": "",
                "sources": [],
                "message_count": session_payload.get("message_count"),
            }
        )

    # Streaming mode: emit SSE content deltas as they are produced by MessageRouter/search_perplexity.
    queue: Queue[tuple[str, dict]] = Queue()

    def _run_stream() -> None:
        try:
            router = MessageRouter()
            message_object = _build_message_object(uid=uid, message=message, source=source, bot_mode=bot_mode)

            def _on_partial(partial_text: str) -> None:
                queue.put(("partial", {"text": str(partial_text or "")}))

            assistant_text = router.route_message(
                message_object=message_object,
                stream=True,
                stream_callback=_on_partial,
            )
            session_payload = _extract_session_payload(uid, bot_mode=message_object.get("bot_mode"))
            queue.put(
                (
                    "done",
                    {
                        "canonical_user_id": uid,
                        "bot_mode": session_payload.get("bot_mode"),
                        "active_session_id": session_payload.get("active_session_id"),
                        "assistant_text": assistant_text,
                        "thinking": "",
                        "sources": [],
                        "message_count": session_payload.get("message_count"),
                    },
                )
            )
        except Exception as exc:
            queue.put(("error", {"message": str(exc)}))
        finally:
            queue.put(("eof", {}))

    Thread(target=_run_stream, daemon=True).start()

    def _generate():
        last_partial = ""
        while True:
            kind, data = queue.get()
            if kind == "partial":
                partial = str(data.get("text", ""))
                delta = partial[len(last_partial):] if partial.startswith(last_partial) else partial
                last_partial = partial
                if delta:
                    yield _sse("content", {"text": delta})
                continue
            if kind == "done":
                full_text = str(data.get("assistant_text", ""))
                remaining = full_text[len(last_partial):] if full_text.startswith(last_partial) else full_text
                if remaining:
                    yield _sse("content", {"text": remaining})
                yield _sse("done", data)
                continue
            if kind == "error":
                yield _sse("error", data)
                continue
            if kind == "eof":
                break

    return Response(
        stream_with_context(_generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    APP.run(host="0.0.0.0", port=_resolve_port(), debug=False)
