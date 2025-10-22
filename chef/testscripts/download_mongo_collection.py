"""Download every document from the configured MongoDB collection."""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from bson import json_util
from pymongo import MongoClient

DEFAULT_DB_NAME = "chef_chatbot"
DEFAULT_COLLECTION_NAME = "chat_sessions"
DEFAULT_OUTPUT_DIR = Path("mongo_exports")


def parse_args() -> argparse.Namespace:
    """Parse CLI options for the export helper."""

    parser = argparse.ArgumentParser(
        description="Download all documents from the configured MongoDB collection."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the JSON dump. Defaults to ./mongo_exports/<timestamp>.json",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional hard cap on the number of documents to export.",
    )
    return parser.parse_args()


def resolve_collection() -> Any:
    """Create a Mongo collection handle using environment variables."""

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise RuntimeError(
            "MONGODB_URI is not set. Provide a mongodb+srv:// connection string."
        )

    database_name = os.environ.get("MONGODB_DB_NAME", DEFAULT_DB_NAME)
    collection_name = os.environ.get("MONGODB_COLLECTION_NAME", DEFAULT_COLLECTION_NAME)
    client = MongoClient(uri)
    return client[database_name][collection_name]


def coerce_for_json(document: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Mongo-specific types into JSON serializable values."""

    # Before: document["_id"] == ObjectId("5f8f8c44...");
    # After: document["_id"] == "5f8f8c44..." so json.dump succeeds.
    serializable = json.loads(json_util.dumps(document))
    return serializable


def fetch_documents(collection: Any, limit: int | None = None) -> List[Dict[str, Any]]:
    """Fetch documents from MongoDB, respecting an optional limit."""

    cursor: Iterable[Dict[str, Any]] = collection.find({})
    if limit is not None:
        cursor = cursor.limit(limit)

    return [coerce_for_json(doc) for doc in cursor]


def resolve_output_path(explicit_path: Path | None) -> Path:
    """Determine where the JSON export will be saved."""

    if explicit_path:
        return explicit_path

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_OUTPUT_DIR / f"mongo_collection_{timestamp}.json"


def write_documents(documents: List[Dict[str, Any]], destination: Path) -> None:
    """Persist the downloaded documents to disk as JSON."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(documents, handle, indent=2)
    logging.info("Saved %s documents to %s", len(documents), destination)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

    args = parse_args()
    collection = resolve_collection()
    documents = fetch_documents(collection, limit=args.limit)

    if not documents:
        logging.warning("The collection is empty; no documents were written.")

    output_path = resolve_output_path(args.output)
    write_documents(documents, output_path)


if __name__ == "__main__":
    main()
