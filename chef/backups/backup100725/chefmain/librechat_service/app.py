"""HTTP server exposing OpenAI-compatible endpoints for LibreChat.

This adapter reuses the existing MessageRouter (telegrams tooling) so a
browser UI like LibreChat can reuse all tools (Perplexity search,
Firestore logging, etc.) without Telegram acting as the transport.

Endpoints:
  * `/health`              – readiness probe
  * `/v1/models`           – advertises a logical model id for LibreChat
  * `/v1/chat/completions` – accepts OpenAI-format chat requests

The service is intentionally self-contained inside this folder so we
avoid touching existing runtime files.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request

import sys

# Ensure the existing project modules resolve exactly the way the Telegram
# runtime expects without editing those files.
ROOT_DIR = Path(__file__).resolve().parents[2]
CHEFMAIN_DIR = Path(__file__).resolve().parents[1]
for path in (CHEFMAIN_DIR, ROOT_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

# Local import from the main runtime without modifying its code.
from chef.chefmain.message_router import MessageRouter

try:  # Optional dependency: only needed when Mongo persistence enabled
    from pymongo.mongo_client import MongoClient
    from pymongo.server_api import ServerApi
except Exception:  # pragma: no cover - allow running without pymongo installed
    MongoClient = None  # type: ignore
    ServerApi = None  # type: ignore

# Firestore logging is optional; we reuse the existing helper when available.
try:
    from chef.utilities.firestore_chef import firestore_add_doc
except Exception as firestore_exc:  # pylint: disable=broad-except
    firestore_add_doc = None  # type: ignore
    logging.getLogger(__name__).warning(
        "Firestore logging disabled for LibreChat adapter: %s", firestore_exc
    )


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MongoConversationStore:
    """Tiny helper to persist LibreChat transcripts into MongoDB."""

    def __init__(self, uri: str, database: str, collection: str = "librechat_conversations") -> None:
        if not MongoClient or not ServerApi:
            raise RuntimeError("pymongo not installed – cannot enable Mongo persistence")
        self._client = MongoClient(uri, server_api=ServerApi("1"))
        self._collection = self._client[database][collection]
        logger.info(
            "Mongo conversation store initialised db=%s collection=%s",
            database,
            collection,
        )

    def save_transcript(self, conversation_id: str, messages: List[Dict[str, Any]], metadata: Dict[str, Any]) -> None:
        now = datetime.now(timezone.utc)
        update_doc = {
            "conversation_id": conversation_id,
            "messages": messages,
            "metadata": metadata,
            "updated_at": now,
        }
        self._collection.update_one(
            {"conversation_id": conversation_id},
            {
                "$set": update_doc,
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )


def resolve_conversation_id(payload: Dict[str, Any]) -> str:
    """Create a consistent conversation id for Mongo/Firestore."""

    metadata = payload.get("metadata") or {}
    for key in ("conversation_id", "conversationId", "session_id", "sessionId"):
        if isinstance(metadata, dict) and metadata.get(key):
            return str(metadata[key])

    if payload.get("user"):
        return str(payload["user"])

    for msg in reversed(payload.get("messages", [])):
        if msg.get("role") == "user" and msg.get("content"):
            return str(uuid.uuid5(uuid.NAMESPACE_OID, msg["content"]))

    return str(uuid.uuid4())


def build_openai_response(model_name: str, content: str) -> Dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }


def normalise_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return shallow copies so MessageRouter can mutate safely."""

    cleaned: List[Dict[str, Any]] = []
    for message in messages:
        if isinstance(message, dict):
            cleaned.append(dict(message))
    return cleaned


def maybe_log_to_firestore(conversation_id: str, messages: List[Dict[str, Any]], response_text: str) -> None:
    if not firestore_add_doc:
        return
    try:
        firestore_add_doc(
            {
                "conversation_id": conversation_id,
                "messages": messages,
                "response": response_text,
                "logged_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Failed to mirror LibreChat transcript to Firestore: %s", exc)


app = Flask(__name__)

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logger.warning("OPENAI_API_KEY not set – MessageRouter calls will fail")

router = MessageRouter(openai_api_key=openai_api_key)

mongo_store: Optional[MongoConversationStore] = None
mongo_uri = os.getenv("MONGODB_URI")
mongo_db = os.getenv("MONGODB_DATABASE", "Cluster0")
if mongo_uri:
    try:
        mongo_store = MongoConversationStore(mongo_uri, mongo_db)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Mongo conversation storage disabled: %s", exc)


@app.get("/health")
def health() -> Any:
    return jsonify({"status": "ok"})


@app.get("/v1/models")
def list_models() -> Any:
    model_name = os.getenv("CHEF_MODEL_NAME", "chef-gpt-router")
    return jsonify(
        {
            "object": "list",
            "data": [
                {
                    "id": model_name,
                    "object": "model",
                    "owned_by": "chef-backend",
                }
            ],
        }
    )


@app.post("/v1/chat/completions")
def chat_completions() -> Any:
    payload = request.get_json(silent=True, force=True)
    if not payload:
        return jsonify({"error": {"message": "Invalid JSON payload"}}), 400

    if payload.get("stream"):
        return jsonify({"error": {"message": "stream=true not supported"}}), 400

    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return jsonify({"error": {"message": "messages[] required"}}), 400

    model_name = payload.get("model") or os.getenv("CHEF_MODEL_NAME", "chef-gpt-router")
    conversation_id = resolve_conversation_id(payload)

    logger.info("LibreChat request conversation_id=%s", conversation_id)

    incoming_messages = normalise_messages(messages)
    router_input = deepcopy(incoming_messages)

    try:
        assistant_reply = router.route_message(messages=router_input)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("MessageRouter failed for LibreChat: %s", exc)
        return jsonify({"error": {"message": f"Router error: {exc}"}}), 500

    response_payload = build_openai_response(model_name, assistant_reply)

    final_history = incoming_messages + [response_payload["choices"][0]["message"]]

    if mongo_store:
        try:
            mongo_store.save_transcript(
                conversation_id,
                final_history,
                {
                    "model": model_name,
                    "last_request": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to persist LibreChat transcript to Mongo: %s", exc)

    maybe_log_to_firestore(conversation_id, final_history, assistant_reply)

    return jsonify(response_payload)


def create_app() -> Flask:
    """Factory for WSGI servers (gunicorn, uvicorn via ASGI adapter)."""

    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
