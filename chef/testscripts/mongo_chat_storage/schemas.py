"""Schema helpers for Mongo chat storage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from chef.utilities.history_messages import add_chat_session_keys

Message = Dict[str, Any]
SessionDocument = Dict[str, Any]


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_message(message: Message) -> Message:
    """Ensure message dict has required keys and serializable values."""

    normalized: Message = {
        "role": message.get("role", "assistant"),
        "content": message.get("content", ""),
    }
    if "timestamp" in message and message["timestamp"]:
        normalized["timestamp"] = _coerce_timestamp(message["timestamp"])
    else:
        normalized.setdefault("timestamp", _utc_iso_now())
    for key in ("tool_name", "metadata"):
        if key in message and message[key] is not None:
            normalized[key] = message[key]
    return normalized


def _coerce_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    if isinstance(value, str):
        return value
    return _utc_iso_now()


def normalize_session(document: SessionDocument) -> SessionDocument:
    """Return a Mongo-ready session document based on existing history dicts."""

    source_messages = list(document.get("messages", []))

    if "chat_session_id" not in document:
        seeded = add_chat_session_keys(document)
        seeded["messages"] = source_messages or seeded.get("messages", [])
        document = seeded

    session_id = document["chat_session_id"]
    user_id = str(
        document.get("user_id")
        or document.get("session_info", {}).get("user_id")
        or "unknown"
    )

    normalized: SessionDocument = {
        "_id": session_id,
        "chat_session_id": session_id,
        "chat_session_created_at": document.get(
            "chat_session_created_at", _utc_iso_now()
        ),
        "user_id": user_id,
        "messages": [normalize_message(msg) for msg in document.get("messages", [])],
        "session_info": document.get("session_info", {}),
    }

    # Preserve arbitrary metadata while avoiding duplicates
    for key, value in document.items():
        if key in normalized:
            continue
        normalized[key] = value

    normalized.setdefault("last_updated_at", _utc_iso_now())
    return normalized


def build_session_from_conversation(
    user_id: str,
    conversation: Iterable[Message],
    session_prefix: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> SessionDocument:
    """Create a session document from a raw conversation iterable."""

    base = {
        "user_id": user_id,
        "session_info": {
            "user_id": user_id,
            "source": "mongo_chat_storage.manual_runner",
        },
        "messages": list(conversation),
    }
    document = normalize_session(base)
    if session_prefix:
        document["chat_session_id"] = f"{session_prefix}_{document['chat_session_id']}"
        document["_id"] = document["chat_session_id"]
    if metadata:
        document.setdefault("metadata", {}).update(metadata)
    return document


__all__ = [
    "Message",
    "SessionDocument",
    "normalize_message",
    "normalize_session",
    "build_session_from_conversation",
]
