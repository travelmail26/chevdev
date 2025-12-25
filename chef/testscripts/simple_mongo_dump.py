"""Save chat sessions to MongoDB in the simplest possible way.

The module exposes a single helper, :func:`save_chat_session_to_mongo`, which
MessageRouter (or any other caller) can run after each turn. The helper reads
whatever the on-disk history currently looks like, makes sure it has the session
keys we expect, and replaces the corresponding document in MongoDB.

Example document written on each call::

    {
      "_id": "user123_20240720T180000Z",
      "chat_session_id": "user123_20240720T180000Z",
      "chat_session_created_at": "2024-07-20T18:00:00Z",
      "user_id": "user123",
      "messages": [
        {"role": "system", "content": "You are ChefBot"},
        {"role": "user", "content": "What can I cook tonight?"},
        {"role": "assistant", "content": "How about pasta with veggies?"}
      ],
      "last_updated_at": "2024-07-20T18:02:06.200000+00:00"
    }
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from pymongo import MongoClient

# Ensure imports work both in repo root and inside containers.
# Example before/after: no sys.path update -> "No module named 'chef'"; with update -> import succeeds.
_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

try:
    from chef.utilities.history_messages import (
        add_chat_session_keys,
        get_full_history_message_object,
    )
except ModuleNotFoundError:
    # Fallback if "chef" is not a package; import from local utilities instead.
    from utilities.history_messages import (  # type: ignore
        add_chat_session_keys,
        get_full_history_message_object,
    )

DEFAULT_DB_NAME = "chef_chatbot"
DEFAULT_COLLECTION_NAME = "chat_sessions"


def _get_mongo_collection():
    """Return the Mongo collection configured via environment variables."""

    uri = os.environ.get("MONGODB_URI")
    # Before: os.environ["CHEF_MONGO_URI"] was required. After: set MONGODB_URI="mongodb+srv://example/chef".
    if not uri:
        raise RuntimeError(
            "MONGODB_URI is not set. Provide a mongodb+srv:// connection string."
        )

    client = MongoClient(uri)
    database_name = os.environ.get("MONGODB_DB_NAME", DEFAULT_DB_NAME)
    collection_name = os.environ.get("MONGODB_COLLECTION_NAME", DEFAULT_COLLECTION_NAME)
    return client[database_name][collection_name]


def _build_session_snapshot(user_id: str) -> Dict[str, Any]:
    """Load the history file and make sure the snapshot has all required fields."""

    # Example content pulled by the next line (already written by message_router):
    #   {
    #     "user_id": "test_user_123",
    #     "chat_session_id": "test_user_123_04092025_154731_787889",
    #     "chat_session_created_at": "2025-09-04T15:47:31.787932+00:00",
    #     "messages": [
    #       {"role": "system", "content": ""},
    #       {"role": "user", "content": "what ingredients do I need?"},
    #       {"role": "assistant", "content": "Here is a recipe suggestion..."}
    #     ]
    #   }
    history = get_full_history_message_object(user_id)

    if not history:
        # When no history exists, seed a new session so we get chat_session_id etc.
        #   history becomes:
        #   {
        #     "user_id": "demo",
        #     "chat_session_id": "demo_20072024_211512_123456",
        #     "chat_session_created_at": "2024-07-20T21:15:12.123456+00:00",
        #     "messages": [{"role": "system", "content": ""}]
        #   }
        history = add_chat_session_keys({"user_id": user_id})

    # Guard against old files that might not have a list under "messages" yet.
    if "messages" not in history or not isinstance(history["messages"], list):
        # After this line:
        #   history["messages"] == []
        history["messages"] = []

    # Some older snapshots might have lost their session id; regenerate if needed.
    session_id = history.get("chat_session_id")
    if not session_id:
        # The helper fills in chat_session_id and chat_session_created_at again.
        history = add_chat_session_keys({"user_id": user_id})
        session_id = history["chat_session_id"]

    # Mongo uses "_id" as the primary key, so we mirror chat_session_id into _id.
    history["_id"] = session_id
    # Keep the user id explicit even if it was missing from the file.
    history["user_id"] = user_id
    # Timestamp shows when we last refreshed the snapshot.
    history["last_updated_at"] = datetime.now(timezone.utc).isoformat()

    # At this point we have a document that looks similar to the example in the
    # module docstring. Returning it lets the caller push everything to Mongo.
    return history


def save_chat_session_to_mongo(user_id: str) -> str:
    """Overwrite the stored session for ``user_id`` with the latest history snapshot."""

    # 1) Build the in-memory snapshot. This already contains every message turn.
    session_snapshot = _build_session_snapshot(user_id)

    # 2) Connect to the configured Mongo collection.
    collection = _get_mongo_collection()

    # 3) Replace the existing document (or create it) so Mongo always has the
    #    full session. The selector uses "_id" so each session stays isolated.
    #    After this call the document in Mongo matches ``session_snapshot``.
    collection.update_one(
        {"_id": session_snapshot["_id"]},
        {"$set": session_snapshot},
        upsert=True,
    )

    # 4) Hand back the session id so callers can log or display it if they want.
    return session_snapshot["_id"]


__all__ = ["save_chat_session_to_mongo"]
