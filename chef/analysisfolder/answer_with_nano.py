#!/usr/bin/env python3
"""
Answer a question by pulling relevant MongoDB chat chunks with embeddings.
Uses OpenAI Responses API tool calling to fetch chunks, then answers.
"""

import argparse
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI
from pymongo import MongoClient

try:
    from bson import ObjectId
except Exception:  # pragma: no cover - bson may be absent in some environments
    ObjectId = None  # type: ignore


DEFAULT_DB_NAME = "chef_chatbot"
DEFAULT_COLLECTION_NAME = "chat_session_chunks"
DEFAULT_INDEX_NAME = "chat_session_embeddings"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_ANALYSIS_MODEL = "gpt-5-nano-2025-08-07"
DEFAULT_LIMIT = 50
DEFAULT_EMBEDDING_PATH = "embedding"
DEFAULT_TEXT_FIELD = "text"
DEFAULT_SESSION_ID_FIELD = "session_id"
DEFAULT_MESSAGE_START_FIELD = "message_start"
DEFAULT_MESSAGE_END_FIELD = "message_end"
DEFAULT_MAX_CHUNK_CHARS = 1200
DEFAULT_MAX_MESSAGE_CHARS = 500
DEFAULT_MAX_MESSAGES_PER_SESSION = 40

SYSTEM_PROMPT_TEMPLATE = (
    "You are a helpful assistant for a database of user conversations about food and cooking.\n"
    "Today's date (UTC) is {today_date}.\n"
    "Always call one tool before answering. Use only the tool output to answer.\n"
    "If the tool returns no results, say you could not find anything.\n\n"
    "Answer format:\n"
    "- Provide short bullet points.\n"
    "- Each bullet MUST include a citation with session_id and date, like:\n"
    "  [session_id=ABC123 | last_updated_at=2025-01-03T12:00:00Z | messages=4-10]\n"
    "- If you summarize actions, include who did what and when.\n\n"
    "Tool usage rules:\n"
    "- Use search_mongo_embeddings for semantic questions like \"what did the user say about X?\"\n"
    "- Use fetch_conversations_by_date_range for time-based questions like \"last 3 days\" or \"2 days ago\".\n"
    "\n"
    "Tool output guidance:\n"
    "- Embedding results include the hit metadata plus full session documents for those hits.\n"
    "- Treat those sessions as the authoritative context for your answer.\n\n"
    "Examples:\n"
    "- \"Summarize conversations from the last 3 days\" -> fetch_conversations_by_date_range(days_back=3)\n"
    "- \"What did the user ask about eggs?\" -> search_mongo_embeddings(query=\"pasta\")"
)


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Answer a question using MongoDB vector search and OpenAI tool calling."
    )
    parser.add_argument("--query", help="Question to answer. If omitted, starts an interactive prompt.")
    parser.add_argument("--db-name", default=DEFAULT_DB_NAME)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--index-name", default=DEFAULT_INDEX_NAME)
    parser.add_argument("--analysis-model", default=DEFAULT_ANALYSIS_MODEL)
    parser.add_argument("--tool-model", default=DEFAULT_ANALYSIS_MODEL)
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--dimensions", type=int, default=None)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--embedding-path", default=DEFAULT_EMBEDDING_PATH)
    parser.add_argument("--text-field", default=DEFAULT_TEXT_FIELD)
    parser.add_argument("--session-id-field", default=DEFAULT_SESSION_ID_FIELD)
    parser.add_argument("--message-start-field", default=DEFAULT_MESSAGE_START_FIELD)
    parser.add_argument("--message-end-field", default=DEFAULT_MESSAGE_END_FIELD)
    parser.add_argument("--max-chunk-chars", type=int, default=DEFAULT_MAX_CHUNK_CHARS)
    parser.add_argument("--max-message-chars", type=int, default=DEFAULT_MAX_MESSAGE_CHARS)
    parser.add_argument("--max-messages-per-session", type=int, default=DEFAULT_MAX_MESSAGES_PER_SESSION)
    return parser.parse_args()


def get_collection(mongo_uri: str, db_name: str, collection_name: str):
    client = MongoClient(mongo_uri)
    return client[db_name][collection_name]


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


def build_system_prompt() -> str:
    today_date = datetime.now(timezone.utc).date().isoformat()
    return SYSTEM_PROMPT_TEMPLATE.format(today_date=today_date)


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
    # Before: "bake salmon" -> After: [0.0123, -0.0456, ...] (vector)
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
                "chunk_type": "$chunk_type",
                "media_id": "$media_id",
                "media_url": "$media_url",
                "media_type": "$media_type",
                "user_description": "$user_description",
                "ai_description": "$ai_description",
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    # Before: raw query text -> After: ranked MongoDB vector hits with scores.
    return list(collection.aggregate(pipeline))


def build_context(results: List[Dict[str, Any]], max_chunk_chars: int) -> str:
    lines: List[str] = []
    for rank, result in enumerate(results, start=1):
        text = (result.get("text") or "").strip()
        if max_chunk_chars and len(text) > max_chunk_chars:
            # Before: 3,000-char chunk -> After: first 1,200 chars + "..."
            text = text[:max_chunk_chars].rstrip() + "..."
        if text:
            lines.append(f"[Chunk {rank}]\n{text}")
    return "\n\n".join(lines)


def _parse_date_input(value: str) -> datetime:
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1]
    # Before: "2025-01-03" -> After: 2025-01-03T00:00:00+00:00
    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _resolve_day_range(
    days_back: Optional[int],
    days_ago: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
) -> Tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)

    if start_date or end_date:
        start_dt = _parse_date_input(start_date) if start_date else now - timedelta(days=1)
        end_dt = _parse_date_input(end_date) if end_date else now
        # Before: 2025-01-03 -> After: 2025-01-03T23:59:59 for full-day coverage.
        end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=0)
        return start_dt, end_dt

    if days_ago is not None:
        target_day = (now - timedelta(days=days_ago)).date()
        start_dt = datetime.combine(target_day, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = start_dt + timedelta(days=1) - timedelta(seconds=1)
        return start_dt, end_dt

    if days_back is not None:
        start_dt = now - timedelta(days=days_back)
        return start_dt, now

    raise ValueError("Provide days_back, days_ago, or start_date/end_date.")


def _trim_messages(messages: List[Dict[str, Any]], max_messages: int, max_chars: int) -> List[Dict[str, Any]]:
    trimmed: List[Dict[str, Any]] = []
    for message in messages[:max_messages]:
        content = str(message.get("content") or "")
        if max_chars and len(content) > max_chars:
            # Before: 2000-char message -> After: first 500 chars + "..."
            content = content[:max_chars].rstrip() + "..."
        trimmed.append({"role": message.get("role"), "content": content})
    return trimmed


def _slice_messages(
    messages: List[Dict[str, Any]],
    message_start: Optional[int],
    message_end: Optional[int],
    max_messages: int,
    max_chars: int,
) -> List[Dict[str, Any]]:
    if message_start is None or message_end is None:
        return _trim_messages(messages, max_messages, max_chars)
    # Before: full session -> After: only the hit range for focused summaries.
    sliced = messages[message_start:message_end]
    return _trim_messages(sliced, max_messages, max_chars)


def _fetch_session_doc(collection, session_id: Any) -> Optional[Dict[str, Any]]:
    if session_id is None:
        return None
    doc = collection.find_one({"_id": session_id})
    if doc:
        return doc
    # Before: only _id lookup -> After: fallback to session_id field.
    return collection.find_one({"session_id": session_id})


def fetch_conversations_by_date_range(
    collection,
    days_back: Optional[int],
    days_ago: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
    limit: int,
    max_messages_per_session: int,
    max_message_chars: int,
) -> Dict[str, Any]:
    start_dt, end_dt = _resolve_day_range(days_back, days_ago, start_date, end_date)
    start_iso = start_dt.isoformat()
    end_iso = end_dt.isoformat()

    time_filter = {"$gte": start_iso, "$lte": end_iso}
    query = {
        "$or": [
            {"last_updated_at": time_filter},
            {"chat_session_created_at": time_filter},
        ]
    }
    cursor = collection.find(query).sort("last_updated_at", -1).limit(limit)

    sessions: List[Dict[str, Any]] = []
    for doc in cursor:
        messages = doc.get("messages") or []
        sessions.append(
            {
                "_id": make_json_safe(doc.get("_id")),
                "last_updated_at": doc.get("last_updated_at"),
                "chat_session_created_at": doc.get("chat_session_created_at"),
                "messages": _trim_messages(messages, max_messages_per_session, max_message_chars),
            }
        )

    return {
        "range": {"start": start_iso, "end": end_iso},
        "count": len(sessions),
        "sessions": sessions,
    }



def search_mongo_embeddings(
    query: str,
    limit: int,
    client: OpenAI,
    collection,
    embedding_model: str,
    dimensions: Optional[int],
    index_name: str,
    embedding_path: str,
    text_field: str,
    session_id_field: str,
    message_start_field: str,
    message_end_field: str,
) -> List[Dict[str, Any]]:
    query_vector = embed_query(client, query, embedding_model, dimensions)
    results = run_vector_search(
        collection,
        index_name,
        embedding_path,
        query_vector,
        limit,
        text_field,
        session_id_field,
        message_start_field,
        message_end_field,
    )
    return results


def build_embedding_context_payload(
    hits: List[Dict[str, Any]],
    collection,
    max_messages_per_session: int,
    max_message_chars: int,
) -> Dict[str, Any]:
    sessions: List[Dict[str, Any]] = []
    for hit in hits:
        session_id = hit.get("session_id")
        session_doc = _fetch_session_doc(collection, session_id)
        if not session_doc:
            continue
        messages = session_doc.get("messages") or []
        sessions.append(
            {
                "_id": make_json_safe(session_doc.get("_id")),
                "session_id": make_json_safe(session_doc.get("session_id")),
                "last_updated_at": session_doc.get("last_updated_at"),
                "chat_session_created_at": session_doc.get("chat_session_created_at"),
                "message_start": hit.get("message_start"),
                "message_end": hit.get("message_end"),
                "messages": _slice_messages(
                    messages,
                    hit.get("message_start"),
                    hit.get("message_end"),
                    max_messages_per_session,
                    max_message_chars,
                ),
            }
        )

    return {
        "hits": make_json_safe(hits),
        "sessions": sessions,
        "sessions_count": len(sessions),
    }


def build_tool_schemas() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": "search_mongo_embeddings",
            "description": "Search MongoDB chat session embeddings for relevant chunks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "User question to search for."},
                    "limit": {"type": "integer", "description": "Optional max results (default set by the script)."},
                },
                "required": ["query"],
            },
        },
        {
            "type": "function",
            "name": "fetch_conversations_by_date_range",
            "description": "Fetch conversations within a date range based on UTC dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_back": {"type": "integer", "description": "Example: 3 for last 3 days."},
                    "days_ago": {"type": "integer", "description": "Example: 2 for conversations from 2 days ago."},
                    "start_date": {
                        "type": "string",
                        "description": "ISO date/datetime (e.g., 2025-01-03 or 2025-01-03T00:00:00Z).",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "ISO date/datetime (e.g., 2025-01-05 or 2025-01-05T23:59:59Z).",
                    },
                    "limit": {"type": "integer", "description": "Optional max sessions to return."},
                },
                "required": [],
            },
        },
    ]


def request_tool_call(
    client: OpenAI,
    model: str,
    question: str,
    tool_schemas: List[Dict[str, Any]],
) -> Tuple[Optional[str], Optional[str], Optional[str], str]:
    response_id = None
    tool_call_id = None
    tool_name = None
    args_buffer = ""

    stream = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": question},
        ],
        tools=tool_schemas,
        tool_choice="required",
        stream=True,
        text={"verbosity": "low"},
    )

    for event in stream:
        if event.type == "response.created":
            response_id = event.response.id
        elif event.type == "response.output_item.added" and event.item.type == "function_call":
            tool_call_id = event.item.call_id
            tool_name = event.item.name
        elif event.type == "response.function_call_arguments.delta":
            args_buffer += event.delta
        elif event.type == "response.function_call_arguments.done":
            args_buffer = event.arguments
        elif event.type == "response.done":
            break

    return response_id, tool_call_id, tool_name, args_buffer


def extract_output_text(response: Any) -> str:
    if hasattr(response, "output_text") and response.output_text:
        return response.output_text

    if hasattr(response, "output"):
        chunks: List[str] = []
        for item in response.output:
            if getattr(item, "type", None) != "message":
                continue
            content = getattr(item, "content", None)
            chunks.append(_flatten_content(content))
        return "".join(chunks).strip()

    return ""


def _flatten_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text") or part.get("content") or ""))
            else:
                parts.append(str(getattr(part, "text", "") or getattr(part, "content", "")))
        return "".join(parts)
    return str(content)


def answer_question(
    question: str,
    client: OpenAI,
    collection,
    args: argparse.Namespace,
) -> str:
    tool_schemas = build_tool_schemas()
    response_id, tool_call_id, tool_name, args_buffer = request_tool_call(
        client,
        args.tool_model,
        question,
        tool_schemas,
    )

    if not tool_call_id or tool_name not in {"search_mongo_embeddings", "fetch_conversations_by_date_range"}:
        raise RuntimeError("Tool call missing or unexpected; cannot continue.")

    try:
        tool_args = json.loads(args_buffer) if args_buffer else {}
    except json.JSONDecodeError:
        tool_args = {}

    payload: Dict[str, Any]
    if tool_name == "fetch_conversations_by_date_range":
        payload = fetch_conversations_by_date_range(
            collection,
            tool_args.get("days_back"),
            tool_args.get("days_ago"),
            tool_args.get("start_date"),
            tool_args.get("end_date"),
            tool_args.get("limit") or args.limit,
            args.max_messages_per_session,
            args.max_message_chars,
        )
    else:
        query_text = tool_args.get("query") or question
        limit = tool_args.get("limit") or args.limit

        results = search_mongo_embeddings(
            query_text,
            limit,
            client,
            collection,
            args.embedding_model,
            args.dimensions,
            args.index_name,
            args.embedding_path,
            args.text_field,
            args.session_id_field,
            args.message_start_field,
            args.message_end_field,
        )

        payload = {
            "query": query_text,
            "context": build_context(results, args.max_chunk_chars),
            **build_embedding_context_payload(
                results,
                collection,
                args.max_messages_per_session,
                args.max_message_chars,
            ),
        }

    # Before: single-shot response -> After: stream tokens to the terminal as they arrive.
    final_text = ""
    final_stream = client.responses.create(
        model=args.analysis_model,
        input=[
            {"role": "user", "content": question},
            {
                "type": "function_call_output",
                "call_id": tool_call_id,
                "output": json.dumps(payload),
            },
        ],
        previous_response_id=response_id,
        stream=True,
        text={"verbosity": "low"},
    )
    for event in final_stream:
        if event.type == "response.output_text.delta":
            print(event.delta, end="", flush=True)
            final_text += event.delta
        elif event.type == "response.done":
            break

    return final_text.strip()


def run_repl(client: OpenAI, collection, args: argparse.Namespace) -> None:
    print("Type 'quit' to exit.")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"quit", "exit"}:
            break
        if not user_input:
            continue
        print("\nAssistant: ", end="", flush=True)
        _ = answer_question(user_input, client, collection, args)
        print("\n")


def main() -> None:
    setup_logging()
    args = parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY to call OpenAI.")
    if not os.environ.get("MONGODB_URI"):
        raise RuntimeError("Set MONGODB_URI to your MongoDB connection string.")

    client = OpenAI(api_key=api_key)
    if not hasattr(client, "responses"):
        raise RuntimeError("OpenAI SDK too old for Responses API. Upgrade: pip install -U openai")

    collection = get_collection(
        os.environ["MONGODB_URI"],
        args.db_name,
        args.collection_name,
    )

    if args.query:
        print("\n--- Answer ---\n")
        _ = answer_question(args.query, client, collection, args)
        print("\n")
        return

    run_repl(client, collection, args)


if __name__ == "__main__":
    main()
