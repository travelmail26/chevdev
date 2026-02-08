"""
LLM NOTE:
This module is the only MongoDB touch-point for the Yen bot.
Flow overview (human + LLM friendly):
1) ensure_yen_database() creates the top-level DB "yen" + collection "chat_sessions".
2) start_conversation() opens a new chat_session_id with an optional system prompt.
3) append_message() adds messages to the session and updates last_updated_at.
4) get_latest_conversation() fetches the most recent session for a user.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from pymongo import MongoClient, ReturnDocument
except Exception:
    MongoClient = None
    ReturnDocument = None

DEFAULT_DB_NAME = "yen"
DEFAULT_COLLECTION_NAME = "chat_sessions"

_mongo_collection = None


def _utc_now_iso() -> str:
    # Before example: timestamp was naive; After example: "2025-01-01T12:00:00+00:00" (UTC ISO).
    return datetime.now(timezone.utc).isoformat()


def _get_db_name() -> str:
    # Before example: hard-coded DB; After example: env override wins for testing.
    return os.getenv("YEN_MONGODB_DB_NAME", DEFAULT_DB_NAME)


def _get_collection_name() -> str:
    # Before example: hard-coded collection; After example: env override wins for testing.
    return os.getenv("YEN_MONGODB_COLLECTION_NAME", DEFAULT_COLLECTION_NAME)


def _get_collection():
    """Return a cached Mongo collection or None when storage is unavailable."""
    global _mongo_collection
    if _mongo_collection is not None:
        return _mongo_collection

    uri = os.getenv("MONGODB_URI")
    if not uri:
        logging.warning("mongo_store: MONGODB_URI not set; Mongo storage disabled.")
        return None
    if MongoClient is None:
        logging.warning("mongo_store: pymongo not available; Mongo storage disabled.")
        return None

    # Before example: client created every call; After example: cached collection reuse.
    client = MongoClient(uri)
    _mongo_collection = client[_get_db_name()][_get_collection_name()]
    return _mongo_collection


def ensure_yen_database() -> bool:
    """Create the 'yen' database + chat_sessions collection in Cluster0.

    In MongoDB, the DB/collection appear on first write, so we do a
    quick insert/delete bootstrap to force creation.
    """
    collection = _get_collection()
    if collection is None:
        return False

    now = _utc_now_iso()
    # Before example: DB stayed invisible in Atlas; After example: bootstrap insert creates it.
    bootstrap_id = collection.insert_one({"bootstrap": True, "created_at": now}).inserted_id
    collection.delete_one({"_id": bootstrap_id})

    # Before example: slow user lookups; After example: index supports last_updated queries.
    collection.create_index([("user_id", 1), ("last_updated_at", -1)])
    logging.info("mongo_store: ensured database=%s collection=%s", _get_db_name(), _get_collection_name())
    return True


def start_conversation(
    user_id: str,
    session_info: Optional[Dict[str, Any]] = None,
    system_prompt: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Create a new conversation document for this user."""
    collection = _get_collection()
    if collection is None:
        return None

    now = _utc_now_iso()
    chat_session_id = str(uuid.uuid4())
    doc: Dict[str, Any] = {
        "user_id": str(user_id),
        "chat_session_id": chat_session_id,
        "messages": [],
        "created_at": now,
        "last_updated_at": now,
    }
    if session_info:
        doc["session_info"] = session_info
    if system_prompt:
        # Before example: no system prompt -> generic replies; After example: persona is stored first.
        doc["messages"].append({"role": "system", "content": system_prompt, "timestamp": now})

    collection.insert_one(doc)
    logging.info("mongo_store: new_session user_id=%s chat_session_id=%s", user_id, chat_session_id)
    return doc


def get_latest_conversation(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch the most recent conversation document for a user."""
    collection = _get_collection()
    if collection is None:
        return None
    return collection.find_one({"user_id": str(user_id)}, sort=[("last_updated_at", -1)])


def ensure_system_prompt(
    user_id: str,
    chat_session_id: str,
    system_prompt: str,
) -> None:
    """Insert a system prompt as the first message if one is missing."""
    collection = _get_collection()
    if collection is None:
        return

    conversation = collection.find_one({"user_id": str(user_id), "chat_session_id": chat_session_id})
    if not conversation:
        return
    messages = conversation.get("messages") or []
    if messages and messages[0].get("role") == "system":
        return

    # Before example: prompt missing -> OpenAI lacks persona; After example: prompt inserted at index 0.
    collection.update_one(
        {"user_id": str(user_id), "chat_session_id": chat_session_id},
        {
            "$push": {
                "messages": {
                    "$each": [{"role": "system", "content": system_prompt, "timestamp": _utc_now_iso()}],
                    "$position": 0,
                }
            },
            "$set": {"last_updated_at": _utc_now_iso()},
        },
    )


def get_or_start_conversation(
    user_id: str,
    session_info: Optional[Dict[str, Any]] = None,
    system_prompt: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return an active conversation or start a new one if missing."""
    conversation = get_latest_conversation(user_id)
    if conversation:
        if system_prompt:
            ensure_system_prompt(user_id, conversation["chat_session_id"], system_prompt)
        return conversation
    return start_conversation(user_id, session_info=session_info, system_prompt=system_prompt)


def append_message(
    user_id: str,
    role: str,
    content: str,
    chat_session_id: Optional[str] = None,
    session_info: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Append a message to an existing conversation."""
    collection = _get_collection()
    if collection is None:
        return None

    now = _utc_now_iso()
    message = {"role": role, "content": content, "timestamp": now}

    query = {"user_id": str(user_id)}
    if chat_session_id:
        query["chat_session_id"] = chat_session_id

    update = {"$push": {"messages": message}, "$set": {"last_updated_at": now}}
    if session_info:
        # Before example: session_info stale; After example: last session_info is refreshed.
        update["$set"]["session_info"] = session_info

    if ReturnDocument:
        return collection.find_one_and_update(
            query,
            update,
            return_document=ReturnDocument.AFTER,
        )

    collection.update_one(query, update)
    return collection.find_one(query)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Before example: running this file did nothing; After example: it creates the DB/collection.
    ok = ensure_yen_database()
    print("yen mongo init ok" if ok else "yen mongo init skipped (missing env or pymongo)")
