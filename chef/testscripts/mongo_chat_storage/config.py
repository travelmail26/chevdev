"""Configuration helpers for MongoDB-backed chat storage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
from typing import Optional

_DEFAULT_DB_NAME = "chef_chatbot"
_DEFAULT_COLLECTION_NAME = "chat_sessions"
_MONGODB_FILE = Path(__file__).resolve().parent.parent / "mangodb.txt"


@dataclass(frozen=True)
class MongoSettings:
    """Runtime settings for MongoDB connections."""

    uri: str
    database: str = _DEFAULT_DB_NAME
    collection: str = _DEFAULT_COLLECTION_NAME


class MissingMongoURI(RuntimeError):
    """Raised when no MongoDB connection string could be located."""


def _load_uri_from_text(text: str) -> Optional[str]:
    """Extract the first MongoDB connection string from a blob of text."""

    pattern = re.compile(r"mongodb(?:\+srv)?://[^\s\"']+")
    match = pattern.search(text)
    if match:
        return match.group(0)
    return None


def _load_uri_from_file(file_path: Path = _MONGODB_FILE) -> Optional[str]:
    if not file_path.exists():
        return None
    try:
        return _load_uri_from_text(file_path.read_text())
    except OSError:
        return None


def load_settings(env: Optional[os._Environ[str]] = None) -> MongoSettings:
    """Load MongoDB connection settings from the environment or fallback file."""

    env = env or os.environ

    uri = env.get("MONGODB_URI") or _load_uri_from_file()
    # Before: CHEF_MONGO_URI was read. After: expect MONGODB_URI="mongodb+srv://example/chef" for tests.
    if not uri:
        raise MissingMongoURI(
            "MongoDB URI not found. Set MONGODB_URI or update chef/testscripts/mangodb.txt."
        )

    database = env.get("MONGODB_DB_NAME", _DEFAULT_DB_NAME)
    collection = env.get("MONGODB_COLLECTION_NAME", _DEFAULT_COLLECTION_NAME)

    return MongoSettings(uri=uri, database=database, collection=collection)


__all__ = ["MongoSettings", "MissingMongoURI", "load_settings"]
