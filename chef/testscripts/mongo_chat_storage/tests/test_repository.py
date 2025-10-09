from __future__ import annotations

import mongomock
import pytest

from chef.testscripts.mongo_chat_storage.config import MongoSettings
from chef.testscripts.mongo_chat_storage.repository import MongoChatRepository
from chef.testscripts.mongo_chat_storage import schemas


@pytest.fixture()
def mongo_repo() -> MongoChatRepository:
    client = mongomock.MongoClient()
    collection = client["test_db"]["chat_sessions"]
    settings = MongoSettings(
        uri="mongodb://localhost:27017",
        database="test_db",
        collection="chat_sessions",
    )
    return MongoChatRepository(collection=collection, settings=settings, ensure_indexes=False)


def test_upsert_and_fetch_session(mongo_repo: MongoChatRepository) -> None:
    session = schemas.build_session_from_conversation(
        user_id="user123",
        conversation=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ],
    )

    session_id = mongo_repo.upsert_session(session)
    stored = mongo_repo.get_session(session_id)

    assert stored is not None
    assert stored["user_id"] == "user123"
    assert len(stored["messages"]) == 2

    mongo_repo.append_messages(session_id, [{"role": "user", "content": "How to cook eggs?"}])
    updated = mongo_repo.get_session(session_id)
    assert len(updated["messages"]) == 3


def test_get_sessions_for_user(mongo_repo: MongoChatRepository) -> None:
    for suffix in range(2):
        session = schemas.build_session_from_conversation(
            user_id="user-bulk",
            conversation=[{"role": "user", "content": f"msg {suffix}"}],
        )
        mongo_repo.upsert_session(session)

    sessions = mongo_repo.get_sessions_for_user("user-bulk")
    assert len(sessions) == 2
    assert {doc["messages"][0]["content"] for doc in sessions} == {"msg 0", "msg 1"}


def test_append_unknown_session_raises(mongo_repo: MongoChatRepository) -> None:
    with pytest.raises(KeyError):
        mongo_repo.append_messages("missing", [{"role": "user", "content": "hi"}])
