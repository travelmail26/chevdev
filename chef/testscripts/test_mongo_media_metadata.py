#!/usr/bin/env python3
"""
Test that media metadata can be written to MongoDB via create_media_metadata.
"""

import datetime
import os
import sys
from pathlib import Path
import signal
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pytest
from pymongo import MongoClient

# Before example: Python cannot import "chefmain".
# After example:  sys.path includes ".../chef" so "chefmain" resolves.
REPO_CHEF_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_CHEF_ROOT))

from chefmain.utilities.mongo_media import create_media_metadata


@pytest.mark.integration
def test_create_media_metadata_inserts_row():
    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        pytest.skip("MONGODB_URI not set; skipping MongoDB metadata test")

    # Before example: mongodb+srv://user:pass@host/db
    # After example:  mongodb+srv://user:pass@host/db?serverSelectionTimeoutMS=10000&connectTimeoutMS=10000
    parsed = urlparse(mongo_uri)
    query = dict(parse_qsl(parsed.query))
    query.setdefault("serverSelectionTimeoutMS", "10000")
    query.setdefault("connectTimeoutMS", "10000")
    test_uri = urlunparse(parsed._replace(query=urlencode(query)))
    original_uri = os.environ.get("MONGODB_URI")
    os.environ["MONGODB_URI"] = test_uri

    # Before example: url="https://example.com/file.jpg"
    # After example:  url="codex-test://media-metadata/2025-01-01T00:00:00Z"
    timestamp = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    url = f"codex-test://media-metadata/{timestamp}"

    def timeout_handler(_signum, _frame):
        raise TimeoutError("Timed out while calling create_media_metadata")

    # Before example: create_media_metadata() hangs silently.
    # After example:  create_media_metadata() either returns or raises a timeout quickly.
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(10)
    try:
        create_media_metadata(url=url, indexed_at=timestamp)
    finally:
        signal.alarm(0)
        if original_uri is not None:
            os.environ["MONGODB_URI"] = original_uri

    # Before example: collection.find_one({"url": url}) -> None
    # After example:  collection.find_one({"url": url}) -> dict
    client = MongoClient(test_uri, serverSelectionTimeoutMS=10000)
    db_name = os.environ.get("MONGODB_DB_NAME", "chef_chatbot")
    collection = client[db_name]["media_metadata"]
    found = collection.find_one({"url": url})

    assert found is not None
