#!/usr/bin/env python3
"""
mongo_worker_embedding_voyage.py

Vector search worker using Voyage embeddings against
chat_session_sentence_chunks_voyage.
"""

import json
import os
import sys
import tempfile
from datetime import datetime

import voyageai
from pymongo import MongoClient


# -----------------------------
# Configuration (keep it simple)
# -----------------------------
DB_NAME = "chef_chatbot"
CHUNKS_COLLECTION_NAME = "chat_session_sentence_chunks_voyage"
SESSIONS_COLLECTION_NAME = "chat_sessions"
VECTOR_INDEX_NAME = "chat_session_embeddings_voyage"
EMBEDDING_PATH = "embedding"
EMBEDDING_MODEL = "voyage-4-large"
VECTOR_LIMIT = 40
NUM_CANDIDATES = 200

MAX_MESSAGES_PER_CONVERSATION = 200
MAX_CHARS_PER_MESSAGE = 1200


# -----------------------------
# Helper functions
# -----------------------------

def make_json_friendly(value):
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
    trimmed = []
    for i, msg in enumerate(messages[:MAX_MESSAGES_PER_CONVERSATION]):
        content = str(msg.get("content") or "")
        if len(content) > MAX_CHARS_PER_MESSAGE:
            content = content[:MAX_CHARS_PER_MESSAGE] + "..."
        trimmed.append({
            "index": i,
            "role": msg.get("role"),
            "content": content,
        })
    return trimmed


def _get_voyage_client():
    api_key = os.environ.get("VOYAGE_API_KEY") or os.environ.get("MONGODB_ATLAS")
    if not api_key:
        raise RuntimeError("Set VOYAGE_API_KEY or MONGODB_ATLAS for Voyage embeddings.")
    os.environ["VOYAGE_API_KEY"] = api_key
    return voyageai.Client()


def embed_query(client, query):
    # Best practice: input_type="query" for search queries.
    result = client.embed([query], model=EMBEDDING_MODEL, input_type="query")
    return result.embeddings[0]


def vector_search(collection, query_vector, limit):
    pipeline = [
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": EMBEDDING_PATH,
                "queryVector": query_vector,
                "numCandidates": NUM_CANDIDATES,
                "limit": limit,
            }
        },
        {
            "$project": {
                "_id": 0,
                "session_id": "$session_id",
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    return list(collection.aggregate(pipeline))


def write_sessions_to_dir(sessions):
    sessions_dir = tempfile.mkdtemp(prefix="recipebot_sessions_voyage_")

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

    print(f"[mongo_worker_embedding_voyage] Vector search for: {query}", file=sys.stderr)

    try:
        client = _get_voyage_client()
    except Exception as e:
        print(json.dumps({"error": f"Voyage client error: {e}"}))
        sys.exit(1)

    mongo = MongoClient(os.environ["MONGODB_URI"])
    chunks_collection = mongo[DB_NAME][CHUNKS_COLLECTION_NAME]
    sessions_collection = mongo[DB_NAME][SESSIONS_COLLECTION_NAME]

    try:
        query_vector = embed_query(client, query)
        results = vector_search(chunks_collection, query_vector, limit)
    except Exception as e:
        print(json.dumps({"error": f"Voyage embedding search failed: {e}"}))
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
                "messages": trim_messages(doc.get("messages") or []),
            })

    print(f"[mongo_worker_embedding_voyage] Found {len(sessions)} sessions", file=sys.stderr)

    sessions_dir = write_sessions_to_dir(sessions)

    result = {
        "sessions_dir": sessions_dir,
        "query": query,
        "count": len(sessions),
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
