#!/usr/bin/env python3
"""
mongo_worker.py

A simple worker script that:
1. Reads a search query from stdin (as JSON)
2. Runs a MongoDB text search
3. Writes each matching conversation to a temp folder
4. Returns the temp folder path as JSON to stdout

Usage:
    echo '{"query": "onion -soup"}' | python mongo_worker.py

Environment variables needed:
    MONGODB_URI - Your MongoDB connection string
"""

import json
import sys
import os
import tempfile
from datetime import datetime
from pymongo import MongoClient


# -----------------------------
# Configuration (keep it simple)
# -----------------------------
DB_NAME = "chef_chatbot"
COLLECTION_NAME = "chat_sessions"
MAX_MESSAGES_PER_CONVERSATION = 200
MAX_CHARS_PER_MESSAGE = 1200


# -----------------------------
# Helper functions
# -----------------------------

def make_json_friendly(value):
    """
    MongoDB returns ObjectId and datetime objects.
    This converts them to strings so we can output JSON.
    """
    if isinstance(value, dict):
        return {k: make_json_friendly(v) for k, v in value.items()}
    if isinstance(value, list):
        return [make_json_friendly(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, '__str__') and type(value).__name__ == 'ObjectId':
        return str(value)
    return value


def trim_messages(messages):
    """
    Keep only the first N messages, and truncate long content.
    This prevents token explosions when we send to the LLM.
    """
    trimmed = []
    for i, msg in enumerate(messages[:MAX_MESSAGES_PER_CONVERSATION]):
        content = str(msg.get("content") or "")
        if len(content) > MAX_CHARS_PER_MESSAGE:
            content = content[:MAX_CHARS_PER_MESSAGE] + "..."
        trimmed.append({
            "index": i,
            "role": msg.get("role"),
            "content": content
        })
    return trimmed


def search_mongo(query_text):
    """
    Run a simple $text search on the messages.content field.
    Returns a list of matching conversation sessions.
    """
    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError("Missing MONGODB_URI environment variable")

    client = MongoClient(mongo_uri)
    collection = client[DB_NAME][COLLECTION_NAME]

    # MongoDB $text search - requires a text index on messages.content
    cursor = collection.find(
        {"$text": {"$search": query_text}},
        {"score": {"$meta": "textScore"}}
    ).sort([("score", {"$meta": "textScore"})])

    sessions = []
    for doc in cursor:
        sessions.append({
            "session_id": str(doc.get("session_id") or doc.get("_id")),
            "last_updated_at": doc.get("last_updated_at"),
            "messages": trim_messages(doc.get("messages") or [])
        })

    return sessions


def write_sessions_to_dir(sessions):
    """
    Write each session to its own JSON file in a temp folder.
    """
    sessions_dir = tempfile.mkdtemp(prefix="recipebot_sessions_")

    for i, session in enumerate(sessions):
        session_id = str(session.get("session_id", "unknown"))
        safe_id = session_id.replace("/", "_").replace("\\", "_")
        filename = f"session_{i:04d}_{safe_id}.json"
        path = os.path.join(sessions_dir, filename)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(make_json_friendly(session), handle)

    return sessions_dir


# -----------------------------
# Main entry point
# -----------------------------

def main():
    # Read JSON from stdin
    raw_input = sys.stdin.read()
    if not raw_input.strip():
        print(json.dumps({"error": "No input provided. Expected JSON with 'query' field."}))
        sys.exit(1)

    try:
        payload = json.loads(raw_input)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    query = payload.get("query")
    if not query:
        print(json.dumps({"error": "Missing 'query' field in input"}))
        sys.exit(1)

    # Run the search
    print(f"[mongo_worker] Searching for: {query}", file=sys.stderr)
    
    try:
        sessions = search_mongo(query)
    except Exception as e:
        print(json.dumps({"error": f"MongoDB search failed: {e}"}))
        sys.exit(1)

    print(f"[mongo_worker] Found {len(sessions)} conversations", file=sys.stderr)

    sessions_dir = write_sessions_to_dir(sessions)

    # Before: return the full sessions JSON payload.
    # After: return a temp folder path so the LLM doesn't see the full data.
    result = {
        "sessions_dir": sessions_dir,
        "query": query,
        "count": len(sessions)
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
