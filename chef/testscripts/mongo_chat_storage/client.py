"""MongoDB client helpers."""

from __future__ import annotations

import logging
import os
from typing import Optional

try:
    from pymongo.mongo_client import MongoClient
    from pymongo.server_api import ServerApi
except Exception as exc:  # pragma: no cover - import guard
    raise RuntimeError(
        "pymongo is required for mongo_chat_storage. Install with `python -m pip install \"pymongo[srv]\"`."
    ) from exc

from .config import MongoSettings, load_settings

logger = logging.getLogger(__name__)

_CLIENT: Optional[MongoClient] = None
_SETTINGS: Optional[MongoSettings] = None


def get_mongo_client(settings: Optional[MongoSettings] = None) -> MongoClient:
    """Return a cached MongoClient, creating one if needed."""

    global _CLIENT, _SETTINGS
    if _CLIENT and (not settings or settings == _SETTINGS):
        return _CLIENT

    _SETTINGS = settings or load_settings()
    connect_kwargs = {"server_api": ServerApi("1")}
    if os.environ.get("MONGODB_TLS_INSECURE", "0").lower() in {"1", "true", "yes"}:
        # Before: CHEF_MONGO_TLS_INSECURE toggled this behavior. After: use MONGODB_TLS_INSECURE=1 for local tests.
        connect_kwargs["tlsAllowInvalidCertificates"] = True
        logger.warning("TLS certificate verification disabled for MongoDB connection")

    logger.debug("Connecting to MongoDB cluster %s", _SETTINGS.uri.split("@")[-1])
    _CLIENT = MongoClient(_SETTINGS.uri, **connect_kwargs)
    return _CLIENT


def get_collection(settings: Optional[MongoSettings] = None):
    """Return the configured MongoDB collection object."""

    settings = settings or load_settings()
    client = get_mongo_client(settings)
    return client[settings.database][settings.collection]


def ping_database(settings: Optional[MongoSettings] = None) -> bool:
    """Validate the connection by issuing a ping command."""

    try:
        collection = get_collection(settings)
        collection.database.client.admin.command("ping")
        return True
    except Exception as exc:  # pragma: no cover - network failure is runtime only
        logger.error("MongoDB ping failed: %s", exc)
        return False


__all__ = ["get_mongo_client", "get_collection", "ping_database"]
