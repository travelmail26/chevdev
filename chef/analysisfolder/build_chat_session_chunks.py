#!/usr/bin/env python3
"""
Create/update chat_session_sentence_chunks with embeddings from chat_sessions.
Very small, single-purpose script for initial backfill and incremental updates.
"""

import argparse
import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from openai import OpenAI
from pymongo import MongoClient


DEFAULT_DB_NAME = "chef_chatbot"
DEFAULT_SOURCE_COLLECTION = "chat_sessions"
DEFAULT_TARGET_COLLECTION = "chat_session_sentence_chunks"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_INDEX_NAME = "chat_session_embeddings"
DEFAULT_MAX_CHARS = 1200
DEFAULT_MAX_MESSAGES = 200
DEFAULT_EMBEDDING_BATCH_SIZE = 64
DEFAULT_MEDIA_COLLECTION = "media_metadata"

MEDIA_PREFIXES = ("[photo_url:", "[video_url:", "[audio_url:")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v")


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build/update chat_session_sentence_chunks embeddings.")
    parser.add_argument("--db-name", default=DEFAULT_DB_NAME)
    parser.add_argument("--source-collection", default=DEFAULT_SOURCE_COLLECTION)
    parser.add_argument("--target-collection", default=DEFAULT_TARGET_COLLECTION)
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--index-name", default=DEFAULT_INDEX_NAME)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--max-messages", type=int, default=DEFAULT_MAX_MESSAGES)
    parser.add_argument("--embedding-batch-size", type=int, default=DEFAULT_EMBEDDING_BATCH_SIZE)
    parser.add_argument("--since", help="ISO datetime to only process recent sessions.")
    parser.add_argument(
        "--media-db-name",
        default=os.environ.get("MONGODB_MEDIA_DB_NAME"),
        help="Override the DB name for media_metadata (defaults to MONGODB_MEDIA_DB_NAME or --db-name).",
    )
    parser.add_argument(
        "--media-collection",
        default=os.environ.get("MONGODB_MEDIA_COLLECTION", DEFAULT_MEDIA_COLLECTION),
        help="MongoDB collection that stores media metadata.",
    )
    parser.add_argument("--media-since", help="ISO datetime to only process recent media docs.")
    parser.add_argument("--force", action="store_true", help="Re-embed all sessions even if unchanged.")
    parser.add_argument(
        "--ensure-index",
        action="store_true",
        help="Create the Atlas vector search index if missing.",
    )
    return parser.parse_args()


def _hash_messages(messages: List[Dict[str, Any]]) -> str:
    hasher = hashlib.sha256()
    for message in messages:
        role = str(message.get("role") or "")
        content = str(message.get("content") or "")
        # Before: role="user", content="Hi" -> After: "user|Hi"
        hasher.update(f"{role}|{content}".encode("utf-8"))
    return hasher.hexdigest()


def _hash_media_fields(url: str, user_description: Optional[str], ai_description: Optional[str]) -> str:
    hasher = hashlib.sha256()
    # Before: url="...jpg", user=None, ai=None -> After: hash over "" inputs (stable).
    # After example: url + user + ai -> deterministic hash for change detection.
    hasher.update(str(url or "").encode("utf-8"))
    hasher.update(str(user_description or "").encode("utf-8"))
    hasher.update(str(ai_description or "").encode("utf-8"))
    return hasher.hexdigest()


def _is_media_stub(content: str) -> bool:
    """Return True when the content looks like a media URL stub."""
    # Before: "[photo_url:...]" -> True; After: "Here is my photo" -> False.
    return any(content.startswith(prefix) for prefix in MEDIA_PREFIXES)


def _is_image_url(url: str) -> bool:
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    return path.endswith(IMAGE_EXTENSIONS)


def _is_video_url(url: str) -> bool:
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    return path.endswith(VIDEO_EXTENSIONS)


def _media_type_for_url(url: str) -> str:
    # Before: ".jpg" -> "image"; After: ".mp4" -> "video"; unknown -> "unknown".
    if _is_image_url(url):
        return "image"
    if _is_video_url(url):
        return "video"
    return "unknown"


def _build_media_text(user_description: Optional[str], ai_description: Optional[str]) -> Optional[str]:
    parts: List[str] = []
    if isinstance(user_description, str) and user_description.strip():
        parts.append(f"user_description: {user_description.strip()}")
    if isinstance(ai_description, str) and ai_description.strip():
        parts.append(f"ai_description: {ai_description.strip()}")
    if not parts:
        return None
    # Before: only user description -> single line; After: user+ai -> two labeled lines.
    return "\n".join(parts)


def _find_media_stub_index(messages: List[Dict[str, Any]], url: str) -> Optional[int]:
    for index, message in enumerate(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        trimmed = content.strip()
        if not trimmed:
            continue
        if url not in trimmed:
            continue
        if not _is_media_stub(trimmed):
            continue
        return index
    return None


def _find_media_session(chat_collection, url: str) -> Tuple[Optional[Any], Optional[int], int]:
    if not url:
        return None, None, 0
    escaped = re.escape(url)
    query = {"messages": {"$elemMatch": {"content": {"$regex": escaped}}}}
    cursor = chat_collection.find(
        query,
        {"messages": 1, "last_updated_at": 1, "chat_session_created_at": 1, "session_id": 1},
    ).sort("last_updated_at", -1).limit(5)
    for session in cursor:
        messages = session.get("messages") or []
        if not isinstance(messages, list):
            continue
        stub_index = _find_media_stub_index(messages, url)
        if stub_index is None:
            continue
        session_id = session.get("session_id") or session.get("_id")
        return session_id, stub_index, len(messages)
    return None, None, 0


def _split_into_sentences(text: str) -> List[str]:
    if not text:
        return []
    # Before: "Hi there" -> After: ["Hi there"]; Before: "Yes. No?" -> After: ["Yes.", "No?"].
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    cleaned = [part.strip() for part in parts if part.strip()]
    return cleaned


def _chunk_messages(
    messages: List[Dict[str, Any]],
    max_chars: int,
    max_messages: int,
) -> Iterable[Tuple[int, int, int, str]]:
    # Before: multi-turn windows -> After: sentence chunks per message, no windowing needed.
    if max_messages <= 0:
        return

    limited = messages[:max_messages]
    for message_index, message in enumerate(limited):
        role = str(message.get("role") or "").strip()
        content = str(message.get("content") or "").strip()
        if not content:
            continue

        sentences = _split_into_sentences(content)
        if not sentences:
            continue

        for sentence_index, sentence in enumerate(sentences, start=1):
            line = f"{role}: {sentence}".strip()
            if not line:
                continue
            if max_chars and len(line) > max_chars:
                # Before: 3000-char sentence -> After: 1200-char truncated sentence.
                line = line[:max_chars].rstrip() + "..."
            # Before: message_index=2 -> After: start=2 end=3 for sentence chunks.
            yield message_index, message_index + 1, sentence_index, line


def _parse_since(since_value: Optional[str]) -> Optional[str]:
    if not since_value:
        return None
    parsed = datetime.fromisoformat(since_value.replace("Z", "")).replace(tzinfo=timezone.utc)
    # Before: "2025-01-03" -> After: "2025-01-03T00:00:00+00:00"
    return parsed.isoformat()


def _needs_update(
    target_collection,
    session_id: Any,
    source_last_updated_at: Optional[str],
    source_text_hash: str,
    force: bool,
) -> bool:
    if force:
        return True
    if not session_id:
        return True
    existing = target_collection.find_one(
        {
            "session_id": session_id,
            "source_last_updated_at": source_last_updated_at,
            "source_text_hash": source_text_hash,
            "chunk_type": {"$ne": "media"},
        },
        projection={"_id": 1},
    )
    # Before: matching hash -> After: skip; Before: no match -> After: re-embed.
    return existing is None


def _media_needs_update(
    target_collection,
    media_id: Any,
    source_last_updated_at: Optional[str],
    source_text_hash: str,
    force: bool,
) -> bool:
    if force:
        return True
    if not media_id:
        return True
    existing = target_collection.find_one(
        {
            "chunk_type": "media",
            "media_id": media_id,
            "source_last_updated_at": source_last_updated_at,
            "source_text_hash": source_text_hash,
        },
        projection={"_id": 1},
    )
    # Before: same media hash -> After: skip; Before: new caption text -> After: re-embed.
    return existing is None


def _embed_text(client: OpenAI, model: str, text: str) -> List[float]:
    response = client.embeddings.create(model=model, input=text)
    return response.data[0].embedding


def _embed_texts(client: OpenAI, model: str, texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    # Before: 64 sentences -> 64 API calls; After: 64 sentences -> 1 batched call.
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


def _ensure_vector_index(collection, index_name: str) -> None:
    existing = []
    try:
        existing = list(collection.list_search_indexes())
    except Exception:
        existing = []
    for idx in existing:
        if idx.get("name") == index_name:
            return

    # Before: missing search index -> After: create vector index on embedding field.
    collection.create_search_index(
        {
            "name": index_name,
            "type": "vectorSearch",
            "definition": {
                "fields": [
                    {
                        "type": "vector",
                        "path": "embedding",
                        "numDimensions": 1536,
                        "similarity": "cosine",
                    }
                ]
            },
        }
    )


def _get_media_collection(mongo: MongoClient, db_name: str, media_db_name: Optional[str], media_collection: str):
    target_db = media_db_name or db_name
    return mongo[target_db][media_collection]


def main() -> None:
    setup_logging()
    args = parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    mongo_uri = os.environ.get("MONGODB_URI")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY to call OpenAI embeddings.")
    if not mongo_uri:
        raise RuntimeError("Set MONGODB_URI to your MongoDB connection string.")

    client = OpenAI(api_key=api_key)
    mongo = MongoClient(mongo_uri)
    db = mongo[args.db_name]
    source = db[args.source_collection]
    if args.target_collection not in db.list_collection_names():
        # Before: missing collection -> After: create empty target collection.
        db.create_collection(args.target_collection)
    target = db[args.target_collection]
    if args.ensure_index:
        _ensure_vector_index(target, args.index_name)

    since_iso = _parse_since(args.since)
    query: Dict[str, Any] = {}
    if since_iso:
        # Before: full scan -> After: only sessions updated since timestamp.
        query = {
            "$or": [
                {"last_updated_at": {"$gte": since_iso}},
                {"chat_session_created_at": {"$gte": since_iso}},
            ]
        }

    processed_sessions = 0
    embedded_chunks = 0
    processed_media = 0
    embedded_media = 0

    for session in source.find(query):
        session_id = session.get("session_id") or session.get("_id")
        messages = session.get("messages") or []
        source_last_updated_at = session.get("last_updated_at") or session.get("chat_session_created_at")
        source_text_hash = _hash_messages(messages)

        if not _needs_update(target, session_id, source_last_updated_at, source_text_hash, args.force):
            continue

        # Before: stale chunks in target -> After: delete and rebuild fresh (exclude media).
        target.delete_many({"session_id": session_id, "chunk_type": {"$ne": "media"}})

        chunk_docs: List[Dict[str, Any]] = []
        for chunk_index, (start_idx, end_idx, sentence_index, text) in enumerate(
            _chunk_messages(
                messages,
                args.max_chars,
                args.max_messages,
            ),
            start=1,
        ):
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
            batch_size = max(args.embedding_batch_size, 1)
            # Before: 128 sentences -> 128 calls; After: 128 sentences -> 2 calls at batch_size=64.
            for start in range(0, len(chunk_docs), batch_size):
                batch = chunk_docs[start : start + batch_size]
                texts = [doc["text"] for doc in batch]
                embeddings = _embed_texts(client, args.embedding_model, texts)
                for doc, embedding in zip(batch, embeddings):
                    doc["embedding"] = embedding
            target.insert_many(chunk_docs)
            embedded_chunks += len(chunk_docs)
        processed_sessions += 1

    media_collection = _get_media_collection(mongo, args.db_name, args.media_db_name, args.media_collection)
    media_since_value = args.media_since or args.since
    media_since_iso = _parse_since(media_since_value) if media_since_value else None

    media_filters: List[Dict[str, Any]] = [
        {"url": {"$exists": True, "$ne": ""}},
        {
            "$or": [
                {"user_description": {"$exists": True, "$ne": ""}},
                {"ai_description": {"$exists": True, "$ne": ""}},
            ]
        },
    ]
    if media_since_iso:
        # Before: media scan across all time -> After: only recent media docs since timestamp.
        media_filters.append(
            {
                "$or": [
                    {"ai_summary_at": {"$gte": media_since_iso}},
                    {"indexed_at": {"$gte": media_since_iso}},
                ]
            }
        )
    media_query = {"$and": media_filters}

    for media_doc in media_collection.find(media_query):
        url = media_doc.get("url")
        if not isinstance(url, str) or not url:
            continue
        user_description = media_doc.get("user_description")
        ai_description = media_doc.get("ai_description")
        text = _build_media_text(user_description, ai_description)
        if not text:
            continue

        source_last_updated_at = media_doc.get("ai_summary_at") or media_doc.get("indexed_at")
        source_text_hash = _hash_media_fields(url, user_description, ai_description)
        media_id = media_doc.get("_id")

        if not _media_needs_update(target, media_id, source_last_updated_at, source_text_hash, args.force):
            continue

        target.delete_many({"chunk_type": "media", "media_id": media_id})

        session_id, stub_index, message_count = _find_media_session(source, url)
        message_start = None
        message_end = None
        if stub_index is not None and message_count:
            # Before: no range -> After: stub index becomes the hit range for session slicing.
            message_start = stub_index
            message_end = min(stub_index + 1, message_count)

        embedding = _embed_text(client, args.embedding_model, text)
        target.insert_one(
            {
                "chunk_type": "media",
                "chunk_index": 1,
                "media_id": media_id,
                "media_url": url,
                "media_type": _media_type_for_url(url),
                "user_description": user_description,
                "ai_description": ai_description,
                "session_id": session_id,
                "message_start": message_start,
                "message_end": message_end,
                "text": text,
                "embedding": embedding,
                "source_last_updated_at": source_last_updated_at,
                "source_text_hash": source_text_hash,
                "media_indexed_at": media_doc.get("indexed_at"),
                "ai_summary_at": media_doc.get("ai_summary_at"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        embedded_media += 1
        processed_media += 1

    logging.info("Processed sessions: %s", processed_sessions)
    logging.info("Embedded chunks: %s", embedded_chunks)
    logging.info("Processed media docs: %s", processed_media)
    logging.info("Embedded media chunks: %s", embedded_media)


if __name__ == "__main__":
    main()


# NOTE: Legacy multi-turn chunking (disabled).
# This is kept for reference only; sentence-level chunks are now used.
# def _chunk_messages(
#     messages: List[Dict[str, Any]],
#     max_chars: int,
#     max_messages: int,
#     turn_window: int,
#     turn_overlap: int,
# ) -> Iterable[Tuple[int, int, str]]:
#     if turn_window <= 0:
#         return
#     if turn_overlap >= turn_window:
#         raise ValueError("turn_overlap must be smaller than turn_window")
#
#     limited = messages[:max_messages]
#     stride = max(turn_window - turn_overlap, 1)
#
#     for start_idx in range(0, len(limited), stride):
#         end_idx = min(start_idx + turn_window, len(limited))
#         window = limited[start_idx:end_idx]
#         lines: List[str] = []
#         for message in window:
#             role = str(message.get("role") or "").strip()
#             content = str(message.get("content") or "").strip()
#             line = f"{role}: {content}".strip()
#             if not line:
#                 continue
#             if max_chars and len(line) > max_chars:
#                 # Before: 3000-char message -> After: 1200-char truncated line.
#                 line = line[:max_chars].rstrip() + "..."
#             lines.append(line)
#
#         if not lines:
#             continue
#
#         chunk_text = "\n".join(lines)
#         if max_chars and len(chunk_text) > max_chars:
#             # Before: 2000-char chunk -> After: 1200-char truncated chunk.
#             chunk_text = chunk_text[:max_chars].rstrip() + "..."
#
#         # Before: 6 turns [0..5], overlap 2 -> After: next chunk starts at 4.
#         yield start_idx, end_idx, chunk_text
