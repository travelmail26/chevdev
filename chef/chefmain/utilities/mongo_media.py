"""Helpers for storing downloaded media files in MongoDB GridFS."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Dict, Optional
from urllib.parse import urlparse

try:  # pragma: no cover - defer pymongo import errors until runtime
    from pymongo import MongoClient
    import gridfs
except Exception as exc:  # pragma: no cover
    MongoClient = None  # type: ignore
    gridfs = None  # type: ignore
    logging.getLogger(__name__).warning("pymongo is unavailable: %s", exc)

DEFAULT_DB_NAME = "chef_chatbot"
DEFAULT_GRIDFS_COLLECTION = "chat_media"

_client: Optional[MongoClient] = None
_gridfs_bucket: Optional[gridfs.GridFS] = None  # type: ignore


def _get_gridfs_bucket() -> Optional[gridfs.GridFS]:  # type: ignore
    """Return a cached GridFS bucket or None if requirements are missing."""
    global _client, _gridfs_bucket

    if gridfs is None or MongoClient is None:
        return None

    if _gridfs_bucket is not None:
        return _gridfs_bucket

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        logging.warning("MONGODB_URI not set; skipping media upload to MongoDB")
        return None

    client = MongoClient(uri)
    db_name = os.environ.get("MONGODB_DB_NAME", DEFAULT_DB_NAME)
    bucket_name = os.environ.get("MONGODB_GRIDFS_COLLECTION", DEFAULT_GRIDFS_COLLECTION)

    db = client[db_name]
    bucket = gridfs.GridFS(db, collection=bucket_name)

    _client = client
    _gridfs_bucket = bucket
    return _gridfs_bucket


def store_media_file(local_path: str, session_info: Dict, media_type: str) -> Optional[str]:
    """Upload ``local_path`` to GridFS and return the stored file id as string."""

    bucket = _get_gridfs_bucket()
    if bucket is None:
        return None

    try:
        with open(local_path, "rb") as media_file:
            metadata = {
                "media_type": media_type,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "source_path": local_path,
                "user_id": session_info.get("user_id"),
                "chat_id": session_info.get("chat_id"),
            }
            file_id = bucket.put(
                media_file,
                filename=os.path.basename(local_path),
                metadata=metadata,
            )
    except Exception as exc:
        logging.warning("Failed to store media in GridFS: %s", exc)
        return None

    return str(file_id)


def create_media_metadata(url: str, indexed_at: str) -> None:
    """Create metadata entry for media URL in MongoDB."""
    global _client
    if MongoClient is None:
        logging.warning("MongoDB client unavailable; cannot create media metadata")
        return

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        logging.warning("MONGODB_URI not set; skipping media metadata creation")
        return

    try:
        # Before example: new MongoClient() per call -> repeated TLS/DNS handshake.
        # After example: reuse cached client -> faster inserts on Cloud Run.
        if _client is None:
            _client = MongoClient(uri)
        client = _client
        db_name = os.environ.get("MONGODB_DB_NAME", DEFAULT_DB_NAME)
        db = client[db_name]
        collection = db["media_metadata"]
        collection.insert_one({"url": url, "indexed_at": indexed_at})
        _spawn_vision_listener(url)
        logging.info("Media metadata created for URL: %s", url)
    except Exception as exc:
        logging.warning("Failed to create media metadata: %s", exc)


def _spawn_vision_listener(url: str) -> None:
    """Launch the vision listener as a separate process (non-blocking)."""
    # Before example: insert_one() finishes and the bot waits for vision work inline.
    # After example: insert_one() returns immediately and the vision script runs separately.
    # Before example: /workspaces/chevdev/chef/testscripts/... fails in Cloud Run.
    # After example: /app/chef/testscripts/... resolves from this file at runtime.
    chef_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    # Before example: videos sent to image-only listener -> FAILED_PRECONDITION or empty output.
    # After example: video URLs route to Gemini video summarizer; images keep OpenAI listener.
    is_video = _is_video_url(url)
    script_name = "mongo_gemini_video_summary.py" if is_video else "mongo_firebase_vision_listener.py"
    if script_name == "mongo_gemini_video_summary.py":
        script_path = os.path.join(chef_root, "chefmain", "utilities", script_name)
    else:
        script_path = os.path.join(chef_root, "testscripts", script_name)
    if not os.path.exists(script_path):
        logging.warning("Vision listener script not found at %s; skipping spawn.", script_path)
        return

    try:
        # Before example: no background process. After example: Popen starts a new process and returns fast.
        subprocess.Popen(
            [sys.executable, script_path],
            env={**os.environ, "VISION_TRIGGER_URL": url},
        )
        logging.info("Spawned %s for URL: %s", script_name, url)
    except Exception as exc:
        logging.warning("Failed to spawn vision listener: %s", exc)


def _is_video_url(url: str) -> bool:
    """Best-effort check for common video URL extensions."""
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    return path.endswith((".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"))
