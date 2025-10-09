"""Repository for storing chat sessions in MongoDB."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from pymongo.collection import Collection

from . import schemas
from .client import get_collection
from .config import MongoSettings, load_settings

logger = logging.getLogger(__name__)


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MongoChatRepository:
    """Thin MongoDB wrapper for chat session documents."""

    def __init__(
        self,
        collection: Optional[Collection] = None,
        settings: Optional[MongoSettings] = None,
        ensure_indexes: bool = True,
    ) -> None:
        self.settings = settings or load_settings()
        self.collection = collection or get_collection(self.settings)
        if ensure_indexes:
            self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        try:
            self.collection.create_index("user_id")
            self.collection.create_index("chat_session_created_at")
        except Exception as exc:  # pragma: no cover - depends on server availability
            logger.warning("Failed to ensure MongoDB indexes: %s", exc)

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------
    def upsert_session(self, document: schemas.SessionDocument) -> str:
        normalized = schemas.normalize_session(document)
        normalized["last_updated_at"] = _utc_iso_now()

        payload = {key: value for key, value in normalized.items() if key != "_id"}

        result = self.collection.update_one(
            {"_id": normalized["_id"]},
            {"$set": payload},
            upsert=True,
        )
        logger.debug(
            "Upserted session %s (matched=%s, modified=%s)",
            normalized["_id"],
            result.matched_count,
            result.modified_count,
        )
        return normalized["_id"]

    def append_messages(
        self,
        chat_session_id: str,
        messages: Iterable[schemas.Message],
    ) -> None:
        batch = [schemas.normalize_message(msg) for msg in messages]
        if not batch:
            return
        result = self.collection.update_one(
            {"_id": chat_session_id},
            {
                "$push": {"messages": {"$each": batch}},
                "$set": {"last_updated_at": _utc_iso_now()},
            },
        )
        if result.matched_count == 0:
            raise KeyError(f"Chat session {chat_session_id} not found for append.")
        logger.debug("Appended %s messages to %s", len(batch), chat_session_id)

    def get_session(self, chat_session_id: str) -> Optional[schemas.SessionDocument]:
        document = self.collection.find_one({"_id": chat_session_id})
        if not document:
            return None
        document.pop("_id", None)
        return document

    def get_sessions_for_user(self, user_id: str) -> List[schemas.SessionDocument]:
        cursor = self.collection.find({"user_id": str(user_id)}).sort(
            "chat_session_created_at"
        )
        sessions = []
        for doc in cursor:
            doc.pop("_id", None)
            sessions.append(doc)
        return sessions

    def delete_session(self, chat_session_id: str) -> int:
        result = self.collection.delete_one({"_id": chat_session_id})
        return result.deleted_count

    def count_sessions(self) -> int:
        return int(self.collection.estimated_document_count())


__all__ = ["MongoChatRepository"]
