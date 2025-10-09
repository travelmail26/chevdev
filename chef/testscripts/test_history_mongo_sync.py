"""Scenario test verifying chat history sync to Mongo snapshots."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from chef.utilities import history_messages
from chef.testscripts import simple_mongo_dump


class _FakeCollection:
    def __init__(self, store):
        self._store = store

    def update_one(self, selector, update, upsert=False):
        self._store[update["$set"]["_id"]] = update["$set"]


class _FakeDatabase:
    def __init__(self, store):
        self._store = store

    def __getitem__(self, collection_name):
        return _FakeCollection(self._store)


class _FakeMongoClient:
    def __init__(self, uri, store):
        self._store = store

    def __getitem__(self, database_name):
        return _FakeDatabase(self._store)


@pytest.fixture
def mongo_store(monkeypatch):
    store = {}

    def fake_mongo_client(uri):
        # Before: tests would reach a live Mongo instance. After: everything stays in-memory.
        return _FakeMongoClient(uri, store)

    monkeypatch.setattr(simple_mongo_dump, "MongoClient", fake_mongo_client)
    monkeypatch.setenv("MONGODB_URI", "mongodb://fake")
    # Before: tests patched CHEF_MONGO_* vars. After: use MONGODB_URI/DB_NAME/COLLECTION_NAME for parity.
    monkeypatch.setenv("MONGODB_DB_NAME", "chef_chatbot_test")
    monkeypatch.setenv("MONGODB_COLLECTION_NAME", "chat_sessions")
    return store


@pytest.fixture
def temp_history_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(history_messages, "LOGS_DIR", tmpdir, raising=False)
        os.makedirs(history_messages.LOGS_DIR, exist_ok=True)
        yield tmpdir


def _append_turns(user_id, turns):
    message_object = {"user_id": user_id}
    for role, content in turns:
        history_messages.message_history_process(message_object, {"role": role, "content": content})


def test_conversations_create_separate_sessions(mongo_store, temp_history_dir):
    _append_turns(
        "user-eggs",
        [
            ("user", "Any tips for cooking eggs?"),
            ("assistant", "Start with a slow scramble for creamy eggs."),
        ],
    )
    _append_turns(
        "user-tomatoes",
        [
            ("user", "What should I do with fresh tomatoes?"),
            ("assistant", "Roast them with olive oil and herbs."),
        ],
    )

    assert len(mongo_store) == 2

    eggs_doc = next(doc for doc in mongo_store.values() if doc["user_id"] == "user-eggs")
    tomatoes_doc = next(doc for doc in mongo_store.values() if doc["user_id"] == "user-tomatoes")

    eggs_messages = [m["content"] for m in eggs_doc["messages"] if m.get("role") != "system"]
    tomatoes_messages = [m["content"] for m in tomatoes_doc["messages"] if m.get("role") != "system"]

    assert eggs_messages == [
        "Any tips for cooking eggs?",
        "Start with a slow scramble for creamy eggs.",
    ]
    assert tomatoes_messages == [
        "What should I do with fresh tomatoes?",
        "Roast them with olive oil and herbs.",
    ]

    assert eggs_doc["_id"] != tomatoes_doc["_id"]
