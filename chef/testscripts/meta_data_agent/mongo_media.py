#!/usr/bin/env python3
"""Simple helpers for storing media metadata in MongoDB."""

import os
from datetime import datetime, timezone
from pymongo import MongoClient

# Connect to MongoDB using environment variable
uri = os.environ.get("MONGODB_URI")
if not uri:
    raise RuntimeError("MONGODB_URI is not set.")
client = MongoClient(uri)

db_name = os.environ.get("MONGODB_DB_NAME", "chef_chatbot")
db = client[db_name]
media_collection = db["media_metadata"]


def store_media_description(url, description, indexed_at=None):
    """Store media URL with description in MongoDB."""
    if indexed_at is None:
        indexed_at = datetime.now(timezone.utc).isoformat()

    doc = {
        "url": url,
        "description": description,
        "indexed_at": indexed_at
    }

    media_collection.insert_one(doc)
    return doc
