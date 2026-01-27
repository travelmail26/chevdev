#!/usr/bin/env python3
"""
mongo_worker_lexical.py

External worker for lexical search:
- Reads JSON from stdin
- Runs Mongo $text query (no regex)
- Returns matched sessions with messages
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo import MongoClient
from pymongo.errors import OperationFailure

try:
    from bson import ObjectId
except Exception:  # pragma: no cover - bson may be absent
    ObjectId = None  # type: ignore


DEFAULT_DB_NAME = "chef_chatbot"
DEFAULT_COLLECTION_NAME = "chat_sessions"
DEFAULT_MAX_MESSAGES = 200
DEFAULT_MAX_MESSAGE_CHARS = 1200
# Before: auto (text + Atlas fallback) -> After: text-only by default.
DEFAULT_LEXICAL_MODE = "text"
DEFAULT_ATLAS_INDEX_NAME = "default"
DEFAULT_ATLAS_SEARCH_PATHS = "messages.content"


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")


def make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: make_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [make_json_safe(v) for v in value]
    if ObjectId is not None and isinstance(value, ObjectId):
        # Before: ObjectId("5f8f8c44...") -> After: "5f8f8c44..."
        return str(value)
    if isinstance(value, datetime):
        # Before: datetime(...) -> After: "2025-01-01T12:00:00"
        return value.isoformat()
    return value


def trim_messages(messages: List[Dict[str, Any]], max_messages: int, max_chars: int) -> List[Dict[str, Any]]:
    trimmed: List[Dict[str, Any]] = []
    for idx, message in enumerate(messages[:max_messages]):
        content = str(message.get("content") or "")
        if max_chars and len(content) > max_chars:
            # Before: 5000 chars -> After: 1200 chars + "..."
            content = content[:max_chars].rstrip() + "..."
        trimmed.append(
            {
                "index": idx,
                "role": message.get("role"),
                "content": content,
            }
        )
    return trimmed


def parse_search_paths(raw: str) -> List[str]:
    cleaned = (raw or "").strip()
    if cleaned in {"*", "wildcard"}:
        # Before: wildcard string -> After: "*" sentinel path.
        return ["*"]
    parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    # Before: "messages.content" -> After: ["messages.content"].
    return parts or [DEFAULT_ATLAS_SEARCH_PATHS]


def run_text_search(
    collection,
    lexical_query: str,
    user_id: Optional[str],
    limit: Optional[int],
) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {"$text": {"$search": lexical_query}}
    if user_id:
        query["user_id"] = str(user_id)

    cursor = collection.find(
        query,
        {"score": {"$meta": "textScore"}, "messages": 1, "last_updated_at": 1, "chat_session_created_at": 1},
    ).sort([("score", {"$meta": "textScore"})])

    if limit:
        cursor = cursor.limit(int(limit))

    return list(cursor)


def run_atlas_search(
    collection,
    lexical_query: str,
    user_id: Optional[str],
    limit: Optional[int],
    index_name: str,
    paths: List[str],
) -> List[Dict[str, Any]]:
    path_value: Any = {"wildcard": "*"} if paths == ["*"] else paths
    pipeline: List[Dict[str, Any]] = [
        {
            "$search": {
                "index": index_name,
                # Before: fixed path list -> After: wildcard path option.
                "text": {"query": lexical_query, "path": path_value},
            }
        },
        {
            "$project": {
                "messages": 1,
                "last_updated_at": 1,
                "chat_session_created_at": 1,
                "score": {"$meta": "searchScore"},
            }
        },
        {"$sort": {"score": -1}},
    ]

    if user_id:
        pipeline.insert(1, {"$match": {"user_id": str(user_id)}})

    if limit:
        pipeline.append({"$limit": int(limit)})

    return list(collection.aggregate(pipeline))


def read_payload() -> Dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        raise RuntimeError("Expected JSON payload on stdin.")
    return json.loads(raw)


def main() -> None:
    setup_logging()
    payload = read_payload()

    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError("Missing MONGODB_URI")

    db_name = os.environ.get("MONGODB_DB_NAME", DEFAULT_DB_NAME)
    collection_name = os.environ.get("MONGODB_COLLECTION_NAME", DEFAULT_COLLECTION_NAME)
    max_messages = int(os.environ.get("WORKER_MAX_MESSAGES", DEFAULT_MAX_MESSAGES))
    max_chars = int(os.environ.get("WORKER_MAX_MESSAGE_CHARS", DEFAULT_MAX_MESSAGE_CHARS))
    lexical_mode = os.environ.get("MONGODB_LEXICAL_MODE", DEFAULT_LEXICAL_MODE).lower()
    atlas_index = os.environ.get("MONGODB_ATLAS_SEARCH_INDEX", DEFAULT_ATLAS_INDEX_NAME)
    atlas_paths = parse_search_paths(os.environ.get("MONGODB_ATLAS_SEARCH_PATHS", DEFAULT_ATLAS_SEARCH_PATHS))

    lexical_query = payload.get("lexical_query")
    if not lexical_query:
        raise RuntimeError("lexical_query is required.")

    user_id = payload.get("user_id")
    limit = payload.get("limit")
    window_before = payload.get("window_before")
    window_after = payload.get("window_after")

    client = MongoClient(mongo_uri)
    collection = client[db_name][collection_name]

    docs: List[Dict[str, Any]] = []
    search_backend = "unknown"

    if lexical_mode not in {"auto", "text", "atlas"}:
        raise RuntimeError("Invalid MONGODB_LEXICAL_MODE: %s" % lexical_mode)

    text_error: Optional[Exception] = None
    atlas_error: Optional[Exception] = None
    text_attempted = False
    atlas_attempted = False

    if lexical_mode in {"auto", "text"}:
        text_attempted = True
        try:
            docs = run_text_search(collection, lexical_query, user_id, limit)
            search_backend = "text"
            logging.info("Text search returned %s sessions", len(docs))
        except OperationFailure as exc:
            text_error = exc
            logging.warning("Text search failed: %s", exc)
            if lexical_mode == "text":
                raise RuntimeError("Mongo $text search failed: %s" % exc) from exc

    if not docs and lexical_mode in {"auto", "atlas"}:
        # Before: no fallback -> After: Atlas Search fallback when $text is unavailable.
        atlas_attempted = True
        try:
            docs = run_atlas_search(
                collection,
                lexical_query,
                user_id,
                limit,
                atlas_index,
                atlas_paths,
            )
            search_backend = "atlas"
            logging.info("Atlas search returned %s sessions", len(docs))
        except OperationFailure as exc:
            atlas_error = exc
            logging.warning("Atlas search failed: %s", exc)
            if lexical_mode == "atlas":
                raise RuntimeError("Mongo Atlas $search failed: %s" % exc) from exc

    if not docs:
        if atlas_error:
            raise RuntimeError(
                "Mongo lexical search failed: text_error=%s atlas_error=%s" % (text_error, atlas_error)
            ) from atlas_error
        if text_error and not atlas_attempted:
            raise RuntimeError("Mongo lexical search failed: text_error=%s" % text_error) from text_error
        if text_error and "IndexNotFound" in str(text_error):
            logging.warning(
                "Missing text index. Consider creating a text index on messages.content or configure Atlas Search."
            )
        logging.warning(
            "Mongo lexical search returned 0 sessions (text_error=%s atlas_error=%s)",
            text_error,
            atlas_error,
        )

    logging.info("Lexical search backend=%s sessions=%s", search_backend, len(docs))
    sessions: List[Dict[str, Any]] = []
    for doc in docs:
        messages = doc.get("messages") or []
        sessions.append(
            {
                "_id": make_json_safe(doc.get("_id")),
                "session_id": make_json_safe(doc.get("session_id")),
                "last_updated_at": doc.get("last_updated_at"),
                "chat_session_created_at": doc.get("chat_session_created_at"),
                # Before: full messages -> After: trimmed messages for scanning.
                "messages": trim_messages(messages, max_messages, max_chars),
            }
        )

    result = {
        "sessions": sessions,
        "summary": {
            "sessions": len(sessions),
            "window_before": window_before,
            "window_after": window_after,
            "window_applied": False,
            "limit": limit,
            "lexical_query": lexical_query,
            "collection": collection_name,
            "search_backend": search_backend,
            "atlas_index": atlas_index if search_backend == "atlas" else None,
            "atlas_paths": atlas_paths if search_backend == "atlas" else None,
            "lexical_mode": lexical_mode,
            "text_error": str(text_error) if text_error else None,
            "atlas_error": str(atlas_error) if atlas_error else None,
        },
    }

    sys.stdout.write(json.dumps(make_json_safe(result), ensure_ascii=True))


if __name__ == "__main__":
    main()
