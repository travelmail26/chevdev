#!/usr/bin/env python3
"""
build_chat_session_chunks_voyage.py

Create/update chat_session_sentence_chunks_voyage using Voyage embeddings.
This keeps the original OpenAI embeddings untouched by writing to a new collection.
"""

import hashlib
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import voyageai
from pymongo import MongoClient


# -----------------------------
# Configuration (keep it simple)
# -----------------------------
DB_NAME = "chef_chatbot"
SOURCE_COLLECTION = "chat_sessions"
TARGET_COLLECTION = "chat_session_sentence_chunks_voyage"
INDEX_NAME = "chat_session_embeddings_voyage"

EMBEDDING_MODEL = "voyage-4-large"
EMBEDDING_DIM = 1024
def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except Exception:
        return default


EMBED_BATCH_SIZE = _int_env("VOYAGE_BATCH_SIZE", 64)

MAX_CHARS = 1200
MAX_MESSAGES = 200
SESSION_LIMIT = _int_env("VOYAGE_SESSION_LIMIT", 0)  # 0 = process all sessions
CHUNK_LIMIT = _int_env("VOYAGE_CHUNK_LIMIT", 0)  # 0 = no limit


# -----------------------------
# Helper functions
# -----------------------------

def _hash_messages(messages: List[Dict[str, Any]]) -> str:
    hasher = hashlib.sha256()
    for message in messages:
        role = str(message.get("role") or "")
        content = str(message.get("content") or "")
        # Before: role="user", content="Hi" -> After: "user|Hi"
        hasher.update(f"{role}|{content}".encode("utf-8"))
    return hasher.hexdigest()


def _split_into_sentences(text: str) -> List[str]:
    if not text:
        return []
    # Before: "Yes. No?" -> After: ["Yes.", "No?"]
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _chunk_messages(messages: List[Dict[str, Any]]) -> Iterable[Tuple[int, int, int, str]]:
    if MAX_MESSAGES <= 0:
        return
    limited = messages[:MAX_MESSAGES]
    for message_index, message in enumerate(limited):
        role = str(message.get("role") or "").strip()
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        sentences = _split_into_sentences(content)
        for sentence_index, sentence in enumerate(sentences, start=1):
            line = f"{role}: {sentence}".strip()
            if not line:
                continue
            if MAX_CHARS and len(line) > MAX_CHARS:
                # Before: 3000-char sentence -> After: 1200-char truncated sentence.
                line = line[:MAX_CHARS].rstrip() + "..."
            yield message_index, message_index + 1, sentence_index, line


def _ensure_vector_index(collection) -> None:
    existing = []
    try:
        existing = list(collection.list_search_indexes())
    except Exception:
        existing = []
    for idx in existing:
        if idx.get("name") == INDEX_NAME:
            return

    collection.create_search_index(
        {
            "name": INDEX_NAME,
            "type": "vectorSearch",
            "definition": {
                "fields": [
                    {
                        "type": "vector",
                        "path": "embedding",
                        "numDimensions": EMBEDDING_DIM,
                        "similarity": "cosine",
                    }
                ]
            },
        }
    )


def _get_voyage_client():
    api_key = os.environ.get("VOYAGE_API_KEY") or os.environ.get("MONGODB_ATLAS")
    if not api_key:
        raise RuntimeError("Set VOYAGE_API_KEY or MONGODB_ATLAS for Voyage embeddings.")
    os.environ["VOYAGE_API_KEY"] = api_key
    return voyageai.Client()


def _embed_texts(client, texts: List[str]) -> List[List[float]]:
    # Best practice: input_type="document" for stored text.
    result = client.embed(texts, model=EMBEDDING_MODEL, input_type="document")
    return result.embeddings


def _needs_update(
    target_collection,
    session_id: Any,
    source_last_updated_at: Optional[str],
    source_text_hash: str,
) -> bool:
    if not session_id:
        return True
    existing = target_collection.find_one(
        {
            "session_id": session_id,
            "source_last_updated_at": source_last_updated_at,
            "source_text_hash": source_text_hash,
        },
        projection={"_id": 1},
    )
    # Before: matching hash -> After: skip; Before: no match -> After: re-embed.
    return existing is None


# -----------------------------
# Main entry point
# -----------------------------


def main() -> None:
    client = _get_voyage_client()
    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError("Set MONGODB_URI to your MongoDB connection string.")

    mongo = MongoClient(mongo_uri)
    db = mongo[DB_NAME]
    source = db[SOURCE_COLLECTION]

    if TARGET_COLLECTION not in db.list_collection_names():
        db.create_collection(TARGET_COLLECTION)
    target = db[TARGET_COLLECTION]
    _ensure_vector_index(target)

    processed_sessions = 0
    embedded_chunks = 0

    for session in source.find({}):
        session_id = session.get("session_id") or session.get("_id")
        messages = session.get("messages") or []
        source_last_updated_at = session.get("last_updated_at") or session.get("chat_session_created_at")
        source_text_hash = _hash_messages(messages)

        if not _needs_update(target, session_id, source_last_updated_at, source_text_hash):
            continue

        target.delete_many({"session_id": session_id})

        chunk_docs: List[Dict[str, Any]] = []
        for chunk_index, (start_idx, end_idx, sentence_index, text) in enumerate(
            _chunk_messages(messages),
            start=1,
        ):
            if CHUNK_LIMIT and len(chunk_docs) >= CHUNK_LIMIT:
                # Before: unlimited chunks -> After: stop at CHUNK_LIMIT for MVP tests.
                break
            chunk_docs.append(
                {
                    "session_id": session_id,
                    "message_start": start_idx,
                    "message_end": end_idx,
                    "chunk_index": chunk_index,
                    "sentence_index": sentence_index,
                    "text": text,
                    "source_last_updated_at": source_last_updated_at,
                    "source_message_count": len(messages),
                    "source_text_hash": source_text_hash,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        if chunk_docs:
            batch_size = max(EMBED_BATCH_SIZE, 1)
            for start in range(0, len(chunk_docs), batch_size):
                batch = chunk_docs[start : start + batch_size]
                texts = [doc["text"] for doc in batch]
                embeddings = _embed_texts(client, texts)
                for doc, embedding in zip(batch, embeddings):
                    doc["embedding"] = embedding
            target.insert_many(chunk_docs)
            embedded_chunks += len(chunk_docs)

        processed_sessions += 1
        if SESSION_LIMIT and processed_sessions >= SESSION_LIMIT:
            break

    print(f"Processed sessions: {processed_sessions}")
    print(f"Embedded chunks: {embedded_chunks}")


if __name__ == "__main__":
    main()
