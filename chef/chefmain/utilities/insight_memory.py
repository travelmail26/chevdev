"""Mongo helpers for loading user insight memory."""

from __future__ import annotations

import os
from typing import Any, Dict, List
from datetime import datetime, timezone
import hashlib

try:  # pragma: no cover
    from pymongo import MongoClient
except Exception:  # pragma: no cover
    MongoClient = None  # type: ignore

_client = None


def _get_client():
    global _client
    if MongoClient is None:
        return None
    if _client is not None:
        return _client
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        return None
    _client = MongoClient(uri)
    return _client


def _get_insights_collection():
    client = _get_client()
    if client is None:
        return None
    db_name = os.environ.get(
        "MONGODB_INSIGHTS_DB_NAME",
        os.environ.get("MONGODB_DB_NAME_GENERAL", "chat_general"),
    )
    collection_name = os.environ.get("MONGODB_INSIGHTS_COLLECTION_NAME", "insights_general")
    return client[db_name][collection_name]


def load_user_insights(
    user_id: str,
    *,
    principle_only: bool = False,
    source_mode: str | None = None,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """Return recent user insights with optional filters."""
    collection = _get_insights_collection()
    if collection is None:
        return []

    query: Dict[str, Any] = {"user_id": str(user_id)}
    if principle_only:
        query["principle"] = True
    if source_mode:
        query["source_bot_mode"] = str(source_mode).strip().lower()

    cursor = collection.find(
        query,
        {
            "_id": 1,
            "insight": 1,
            "principle": 1,
            "source_bot_mode": 1,
            "source_chat_session_id": 1,
            "source_last_updated_at": 1,
            "created_on": 1,
        },
    ).sort("source_last_updated_at", -1).limit(max(1, int(limit)))
    return list(cursor)


def add_user_principle_insight(
    *,
    user_id: str,
    insight_text: str,
    source_mode: str = "general",
    source_chat_session_id: str | None = None,
) -> Dict[str, Any] | None:
    """Insert one explicit user-defined principle insight document."""
    collection = _get_insights_collection()
    if collection is None:
        return None

    clean_text = " ".join(str(insight_text or "").strip().split())
    if not clean_text:
        return None

    now = datetime.now(timezone.utc)
    created_on = now.isoformat()
    chat_session_id = str(source_chat_session_id or f"manual_{user_id}_{int(now.timestamp())}")
    digest = hashlib.sha1(f"{user_id}|{clean_text}|{created_on}".encode("utf-8")).hexdigest()[:10]
    doc_id = f"insight_general_manual_{user_id}_{digest}"

    doc = {
        "_id": doc_id,
        "user_id": str(user_id),
        "source_bot_mode": str(source_mode or "general").strip().lower(),
        "created_on": created_on,
        "source_chat_session_id": chat_session_id,
        "source_conversation_hash": f"manual_principle_{digest}",
        "source_last_updated_at": created_on,
        "date": now.date().isoformat(),
        "insight": clean_text,
        "principle": True,
    }
    collection.update_one({"_id": doc_id}, {"$set": doc}, upsert=True)
    return doc
