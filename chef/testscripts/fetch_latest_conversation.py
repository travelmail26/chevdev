"""Quick helper to inspect the most recent chat session stored in MongoDB."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Optional

from pymongo import MongoClient

DEFAULT_DB_NAME = "chef_chatbot"
DEFAULT_COLLECTION_NAME = "chat_sessions"


def _connect_to_collection():
    """Return the Mongo collection defined via standard environment variables."""

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        # Before: scripts required CHEF_MONGO_URI. After: read the unified MONGODB_URI already used by the bot.
        raise RuntimeError("Set MONGODB_URI to your MongoDB connection string.")

    client = MongoClient(uri)
    database = os.environ.get("MONGODB_DB_NAME", DEFAULT_DB_NAME)
    collection = os.environ.get("MONGODB_COLLECTION_NAME", DEFAULT_COLLECTION_NAME)
    return client[database][collection]


def fetch_latest_conversation() -> Optional[Dict[str, Any]]:
    """Return the most recently updated chat session document."""

    collection = _connect_to_collection()
    # Before: manual filtering was needed. After: rely on Mongo's sort to grab the freshest session.
    return collection.find_one(sort=[("last_updated_at", -1)])


def summarize_latest_user_message(conversation: Dict[str, Any]) -> str:
    """Pull the latest user-authored message from the conversation."""

    messages = conversation.get("messages") or []
    # Before: callers walked the list themselves. After: keep this detail in one helper.
    user_messages = [msg for msg in messages if msg.get("role") == "user"]
    if not user_messages:
        return "No user messages recorded in this session yet."

    # The final user message typically represents the latest report/request in the chat.
    latest_user_message = user_messages[-1].get("content") or "(empty message)"
    return latest_user_message


def _format_timestamp(value: Any) -> str:
    """Human-friendly timestamp formatter that tolerates missing data."""

    if not value:
        return "unknown"
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def main() -> None:
    try:
        conversation = fetch_latest_conversation()
    except Exception as exc:  # pragma: no cover - CLI convenience
        print(f"Could not fetch latest conversation: {exc}")
        return

    if not conversation:
        print("No conversations found in MongoDB.")
        return

    session_id = conversation.get("chat_session_id") or conversation.get("_id")
    updated_at = _format_timestamp(conversation.get("last_updated_at"))
    user_summary = summarize_latest_user_message(conversation)

    print("Latest conversation snapshot:")
    print(f"  session_id: {session_id}")
    print(f"  last_updated_at: {updated_at}")
    print(f"  latest_user_message: {user_summary}")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
