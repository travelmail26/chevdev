from __future__ import annotations

import json
from pathlib import Path

import mongomock

from chef.testscripts.mongo_chat_storage.config import MongoSettings
from chef.testscripts.mongo_chat_storage.history_ingestor import ingest_directory
from chef.testscripts.mongo_chat_storage.repository import MongoChatRepository
from chef.testscripts.mongo_chat_storage import schemas


def build_repo() -> MongoChatRepository:
    client = mongomock.MongoClient()
    collection = client["test_db"]["chat_sessions"]
    settings = MongoSettings(
        uri="mongodb://localhost:27017",
        database="test_db",
        collection="chat_sessions",
    )
    return MongoChatRepository(collection=collection, settings=settings, ensure_indexes=False)


def test_ingest_directory(tmp_path: Path) -> None:
    repo = build_repo()
    session = schemas.build_session_from_conversation(
        user_id="log_user",
        conversation=[{"role": "user", "content": "Testing eggs"}],
    )
    file_path = tmp_path / "log_user_history.json"
    file_path.write_text(json.dumps(session))

    processed = ingest_directory(tmp_path, repo, dry_run=False, verbose=True)

    assert processed == 1
    sessions = repo.get_sessions_for_user("log_user")
    assert len(sessions) == 1
    assert sessions[0]["messages"][0]["content"] == "Testing eggs"


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    repo = build_repo()
    session = schemas.build_session_from_conversation(
        user_id="dry_user",
        conversation=[{"role": "user", "content": "Dry run message"}],
    )
    (tmp_path / "dry_user_history.json").write_text(json.dumps(session))

    processed = ingest_directory(tmp_path, repo, dry_run=True)
    assert processed == 1
    assert repo.count_sessions() == 0
