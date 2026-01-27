#!/usr/bin/env python3
"""
mongo_worker_embedding.py

A simple worker script that:
1. Reads a query from stdin (as JSON)
2. Embeds the query
3. Runs a MongoDB vector search over chat embeddings
4. Fetches matching sessions and writes each to a temp folder
5. Returns the temp folder path as JSON to stdout

Usage:
    echo '{"query": "fish"}' | python mongo_worker_embedding.py

Environment variables needed:
    MONGODB_URI - Your MongoDB connection string
    OPENAI_API_KEY - Your OpenAI API key
"""

import json
import os
import sys
import tempfile
from datetime import datetime

from openai import OpenAI
from pymongo import MongoClient


# -----------------------------
# Configuration (keep it simple)
# -----------------------------
DB_NAME = "chef_chatbot"
# Before: vector search over chat_session_chunks; After: search sentence-level chunks.
CHUNKS_COLLECTION_NAME = "chat_session_sentence_chunks"
SESSIONS_COLLECTION_NAME = "chat_sessions"
VECTOR_INDEX_NAME = "chat_session_embeddings"
EMBEDDING_PATH = "embedding"
SESSION_ID_FIELD = "session_id"
EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_LIMIT = 40
NUM_CANDIDATES = 200

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
    if hasattr(value, "__str__") and type(value).__name__ == "ObjectId":
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


def embed_query(client, query):
    """
    Turn query text into an embedding vector.
    Example before/after:
      "fish" -> [0.0102, -0.0077, ...]
    """
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=query)
    return response.data[0].embedding


def vector_search(collection, query_vector, limit):
    """
    Run a $vectorSearch on the chunks collection.
    """
    pipeline = [
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": EMBEDDING_PATH,
                "queryVector": query_vector,
                "numCandidates": NUM_CANDIDATES,
                "limit": limit
            }
        },
        {
            "$project": {
                "_id": 0,
                "session_id": f"${SESSION_ID_FIELD}",
                "score": {"$meta": "vectorSearchScore"}
            }
        }
    ]
    return list(collection.aggregate(pipeline))


def write_sessions_to_dir(sessions):
    """
    Write each session to its own JSON file in a temp folder.
    """
    sessions_dir = tempfile.mkdtemp(prefix="recipebot_sessions_embed_")

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
    limit = payload.get("limit") or VECTOR_LIMIT
    try:
        limit = int(limit)
    except Exception:
        limit = VECTOR_LIMIT
    if not query:
        print(json.dumps({"error": "Missing 'query' field in input"}))
        sys.exit(1)

    if not os.environ.get("MONGODB_URI"):
        print(json.dumps({"error": "Missing MONGODB_URI environment variable"}))
        sys.exit(1)
    if not os.environ.get("OPENAI_API_KEY"):
        print(json.dumps({"error": "Missing OPENAI_API_KEY environment variable"}))
        sys.exit(1)

    print(f"[mongo_worker_embedding] Vector search for: {query}", file=sys.stderr)

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    mongo = MongoClient(os.environ["MONGODB_URI"])
    chunks_collection = mongo[DB_NAME][CHUNKS_COLLECTION_NAME]
    sessions_collection = mongo[DB_NAME][SESSIONS_COLLECTION_NAME]

    try:
        query_vector = embed_query(client, query)
        results = vector_search(chunks_collection, query_vector, limit)
    except Exception as e:
        print(json.dumps({"error": f"Embedding search failed: {e}"}))
        sys.exit(1)

    session_ids = []
    seen = set()
    for hit in results:
        session_id = hit.get("session_id")
        if not session_id or session_id in seen:
            continue
        seen.add(session_id)
        session_ids.append(session_id)

    sessions = []
    if session_ids:
        cursor = sessions_collection.find({
            "$or": [
                {"_id": {"$in": session_ids}},
                {"chat_session_id": {"$in": session_ids}},
                {"session_id": {"$in": session_ids}},
            ]
        })
        for doc in cursor:
            sessions.append({
                "session_id": str(doc.get("session_id") or doc.get("chat_session_id") or doc.get("_id")),
                "last_updated_at": doc.get("last_updated_at"),
                "messages": trim_messages(doc.get("messages") or [])
            })

    print(f"[mongo_worker_embedding] Found {len(sessions)} sessions", file=sys.stderr)

    sessions_dir = write_sessions_to_dir(sessions)

    result = {
        "sessions_dir": sessions_dir,
        "query": query,
        "count": len(sessions)
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
