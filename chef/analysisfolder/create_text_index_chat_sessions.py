#!/usr/bin/env python3
"""
Create a MongoDB text index for chat_sessions (messages.content by default).
"""

from __future__ import annotations

import argparse
import logging
import os
from typing import List

from pymongo import MongoClient


DEFAULT_DB_NAME = "chef_chatbot"
DEFAULT_COLLECTION_NAME = "chat_sessions"
DEFAULT_FIELD_PATH = "messages.content"
DEFAULT_INDEX_NAME = "messages_content_text"


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a MongoDB text index for chat_sessions.")
    parser.add_argument("--db-name", default=DEFAULT_DB_NAME)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--field-path", default=DEFAULT_FIELD_PATH)
    parser.add_argument("--index-name", default=DEFAULT_INDEX_NAME)
    parser.add_argument("--wildcard", action="store_true", help="Create a wildcard text index ($**).")
    parser.add_argument("--test-query", default=None, help="Optional $text query to validate the index.")
    return parser.parse_args()


def list_index_names(collection) -> List[str]:
    return [idx["name"] for idx in collection.list_indexes()]


def main() -> None:
    setup_logging()
    args = parse_args()

    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError("Missing MONGODB_URI.")

    client = MongoClient(mongo_uri)
    collection = client[args.db_name][args.collection]

    existing = list_index_names(collection)
    logging.info("Existing indexes: %s", existing)

    if args.index_name in existing:
        # Before: no index -> After: index already exists.
        logging.info("Index already exists: %s", args.index_name)
    else:
        if args.wildcard:
            # Before: field-specific index -> After: wildcard text index.
            keys = [("$**", "text")]
        else:
            # Before: no text index -> After: text index on messages.content (or custom path).
            keys = [(args.field_path, "text")]
        created = collection.create_index(keys, name=args.index_name)
        logging.info("Created index: %s", created)

    if args.test_query:
        query = {"$text": {"$search": args.test_query}}
        hits = list(
            collection.find(query, {"score": {"$meta": "textScore"}})
            .sort([("score", {"$meta": "textScore"})])
            .limit(5)
        )
        logging.info("Test query hits=%s", len(hits))


if __name__ == "__main__":
    main()
