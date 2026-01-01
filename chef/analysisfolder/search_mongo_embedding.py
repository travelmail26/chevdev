#!/usr/bin/env python3
"""Run a vector search query against stored MongoDB chat embeddings."""

import argparse
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from openai import OpenAI
from pymongo import MongoClient

try:
    from bson import ObjectId
except Exception:  # pragma: no cover - bson may be absent in some environments
    ObjectId = None  # type: ignore


DEFAULT_DB_NAME = "chef_chatbot"
DEFAULT_COLLECTION_NAME = "chat_sessions"
DEFAULT_INDEX_NAME = "chat_session_embeddings"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_LIMIT = 5
DEFAULT_EMBEDDING_PATH = "embedding"
DEFAULT_TEXT_FIELD = "text"
DEFAULT_SESSION_ID_FIELD = "session_id"
DEFAULT_MESSAGE_START_FIELD = "message_start"
DEFAULT_MESSAGE_END_FIELD = "message_end"


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a vector search over chat embeddings.")
    parser.add_argument("--query", required=True, help="Query text to search for.")
    parser.add_argument("--db-name", default=DEFAULT_DB_NAME)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--index-name", default=DEFAULT_INDEX_NAME)
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--dimensions", type=int, default=None)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--embedding-path", default=DEFAULT_EMBEDDING_PATH)
    parser.add_argument("--text-field", default=DEFAULT_TEXT_FIELD)
    parser.add_argument("--session-id-field", default=DEFAULT_SESSION_ID_FIELD)
    parser.add_argument("--message-start-field", default=DEFAULT_MESSAGE_START_FIELD)
    parser.add_argument("--message-end-field", default=DEFAULT_MESSAGE_END_FIELD)
    return parser.parse_args()


def make_json_safe(value: Any) -> Any:
    """Convert MongoDB types into JSON-safe primitives."""
    if isinstance(value, dict):
        return {k: make_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [make_json_safe(item) for item in value]
    if ObjectId is not None and isinstance(value, ObjectId):
        # Before: ObjectId("5f8f8c44...") -> After: "5f8f8c44..."
        return str(value)
    if isinstance(value, datetime):
        # Before: datetime(2025, 1, 1, 12, 0) -> After: "2025-01-01T12:00:00"
        return value.isoformat()
    return value


def embed_query(
    client: OpenAI,
    query: str,
    model: str,
    dimensions: Optional[int],
) -> List[float]:
    """Embed a query string into a vector."""
    payload: Dict[str, Any] = {"model": model, "input": query}
    if dimensions is not None:
        payload["dimensions"] = dimensions
    # Before: "last pizza convo" -> After: [0.0102, -0.0077, ...] (vector)
    response = client.embeddings.create(**payload)
    return response.data[0].embedding


def run_vector_search(
    collection,
    index_name: str,
    embedding_path: str,
    query_vector: List[float],
    limit: int,
    text_field: str,
    session_id_field: str,
    message_start_field: str,
    message_end_field: str,
) -> List[Dict[str, Any]]:
    """Run a MongoDB $vectorSearch query and return projected results."""
    num_candidates = max(limit * 20, 100)
    pipeline = [
        {
            "$vectorSearch": {
                "index": index_name,
                "path": embedding_path,
                "queryVector": query_vector,
                "numCandidates": num_candidates,
                "limit": limit,
            }
        },
        {
            "$project": {
                "_id": 1,
                "text": f"${text_field}",
                "session_id": f"${session_id_field}",
                "message_start": f"${message_start_field}",
                "message_end": f"${message_end_field}",
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    # Before: raw query text -> After: ranked MongoDB vector hits with scores.
    return list(collection.aggregate(pipeline))


def main() -> None:
    setup_logging()
    args = parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY to call OpenAI embeddings.")
    if not os.environ.get("MONGODB_URI"):
        raise RuntimeError("Set MONGODB_URI to your MongoDB connection string.")

    client = OpenAI(api_key=api_key)
    collection = MongoClient(os.environ["MONGODB_URI"])[args.db_name][args.collection_name]

    logging.info("Running vector query: %s", args.query)
    query_vector = embed_query(client, args.query, args.embedding_model, args.dimensions)
    results = run_vector_search(
        collection,
        args.index_name,
        args.embedding_path,
        query_vector,
        args.limit,
        args.text_field,
        args.session_id_field,
        args.message_start_field,
        args.message_end_field,
    )
    logging.info("Vector search returned %s hits", len(results))

    for rank, result in enumerate(results, start=1):
        snippet = (result.get("text") or "").replace("\n", " ")[:240]
        logging.info(
            "Result %s | score=%.4f | session=%s | m%s-m%s | %s",
            rank,
            result.get("score", 0.0),
            make_json_safe(result.get("session_id")),
            result.get("message_start"),
            result.get("message_end"),
            snippet,
        )


if __name__ == "__main__":
    main()
