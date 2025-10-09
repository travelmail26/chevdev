"""Helpers for storing downloaded media files in MongoDB GridFS."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Dict, Optional

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
