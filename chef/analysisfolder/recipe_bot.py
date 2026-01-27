#!/usr/bin/env python3
"""
recipe_bot.py

Very simple sequence:
1) mongo_text_search (direct Mongo $text on messages.content)
2) build_dictionary_parallel (exhaustive extraction)
3) compute_exhaustive_with_ci (final list)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI
from pymongo import MongoClient

from chunk_scanner_parallel import build_recipe_dictionary_parallel


# ----------------------------
# Settings (keep simple)
# ----------------------------
MODEL = os.environ.get("BOT_MODEL", "gpt-5-2025-08-07")
EXTRACT_MODEL = os.environ.get("EXTRACT_MODEL", "gpt-5-nano-2025-08-07")
CI_MODEL = os.environ.get("CI_MODEL", "gpt-5-2025-08-07")

OUT_DIR = Path("chef/analysisfolder/bot_runs")
DB_NAME = os.environ.get("MONGODB_DB_NAME", "chef_chatbot")
COLLECTION_NAME = os.environ.get("MONGODB_COLLECTION_NAME", "chat_sessions")

DEFAULT_QUESTION = os.environ.get(
    "BOT_QUESTION",
    "List all the different temperatures that a user has cooked onions. "
    "List them with date, temp, and outcome if available.",
)

# Message trimming (keep small to avoid token spikes)
MAX_MESSAGES = 200
MAX_MESSAGE_CHARS = 1200


# ----------------------------
# Bot instructions (simple)
# ----------------------------
BOT_INSTRUCTIONS = r"""
You are RecipeRecordBot. Your job is to answer cooking-history questions with MAXIMUM COMPLETENESS.

Non-negotiable workflow (ALWAYS follow in order):
1) Call mongo_text_search with include_terms/exclude_terms (do not guess; retrieve).
2) Call build_dictionary_parallel on the retrieved results to create an exhaustive dictionary (use nano extractor).
3) Call compute_exhaustive_with_ci to run Python over the dictionary and produce an exhaustive answer (use CI_MODEL constant).
4) Return the final answer using ONLY the compute tool output (no extra inventions).

Why this order:
- First: retrieve ALL candidate sessions from Mongo with $text.
- Second: extract events exhaustively from those sessions.
- Third: compute the final list from the extracted dictionary.

Critical rules:
- Do NOT answer directly from memory.
- Do NOT do programmatic searching yourself; retrieval is via mongo_text_search tool.
- Call each tool exactly once (no repeats, no parallel calls).

Lexical query rules:
- The mongo worker uses Mongo $text search only (messages.content text index).
- Use include_terms/exclude_terms lists of simple keywords or short phrases.
- Do NOT add synonyms or extra terms. Only include what the user asked for.
- Do NOT use boolean operators like OR/AND; they are treated as literal tokens.
- Do NOT use regex patterns or regex syntax.
- Prefer ASCII tokens; avoid symbols like degree signs.
- Keep the query concise (roughly <= 12 terms plus a few quoted phrases).
- First tool call MUST be mongo_text_search.
- Use the built-in models only: extraction must be gpt-5-nano-2025-08-07; code interpreter must use CI_MODEL (do not request gpt-4).

Example:
User: "List all temperatures where onions were caramelized; exclude soup"
Step A: mongo_text_search(
  include_terms=["onion", "caramelized", "temperature"],
  exclude_terms=["soup"]
)
Step B: build_dictionary_parallel(...)
Step C: compute_exhaustive_with_ci(...)
"""


# ----------------------------
# Tools
# ----------------------------
TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "name": "mongo_text_search",
        "description": "Direct Mongo $text search on messages.content.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "include_terms": {"type": "array", "items": {"type": "string"}},
                "exclude_terms": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["include_terms", "exclude_terms"],
        },
    },
    {
        "type": "function",
        "name": "build_dictionary_parallel",
        "description": "Chunk + extract events from all candidates.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "candidates_path": {"type": "string"},
                "question": {"type": "string"},
            },
            "required": ["candidates_path", "question"],
        },
    },
    {
        "type": "function",
        "name": "compute_exhaustive_with_ci",
        "description": "Use Code Interpreter to compute final answer from dictionary JSON.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "dictionary_path": {"type": "string"},
                "question": {"type": "string"},
                "page_size": {"type": "integer"},
            },
            "required": ["dictionary_path", "question", "page_size"],
        },
    },
]


# ----------------------------
# Helpers
# ----------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def normalize_terms(terms: List[str]) -> List[str]:
    cleaned: List[str] = []
    for raw in terms:
        term = (raw or "").strip()
        if not term:
            continue
        # Before: onion soup -> After: "onion soup".
        if " " in term and not (term.startswith("\"") and term.endswith("\"")):
            term = f"\"{term}\""
        cleaned.append(term)
    return cleaned


def build_text_query(include_terms: List[str], exclude_terms: List[str]) -> str:
    include_terms = normalize_terms(include_terms)
    exclude_terms = normalize_terms(exclude_terms)
    if not include_terms:
        return ""
    parts = include_terms + [f"-{term}" for term in exclude_terms]
    return " ".join(parts).strip()


def trim_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    trimmed: List[Dict[str, Any]] = []
    for idx, message in enumerate(messages[:MAX_MESSAGES]):
        content = str(message.get("content") or "")
        if MAX_MESSAGE_CHARS and len(content) > MAX_MESSAGE_CHARS:
            # Before: 5000 chars -> After: 1200 chars + "...".
            content = content[:MAX_MESSAGE_CHARS].rstrip() + "..."
        trimmed.append({"index": idx, "role": message.get("role"), "content": content})
    return trimmed


# ----------------------------
# Tool implementations
# ----------------------------

def tool_mongo_text_search(args: Dict[str, Any]) -> Dict[str, Any]:
    include_terms = args.get("include_terms") or []
    exclude_terms = args.get("exclude_terms") or []

    query_text = build_text_query(include_terms, exclude_terms)
    if not query_text:
        raise RuntimeError("include_terms must not be empty.")

    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError("Missing MONGODB_URI.")

    client = MongoClient(mongo_uri)
    collection = client[DB_NAME][COLLECTION_NAME]

    query = {"$text": {"$search": query_text}}
    cursor = collection.find(
        query,
        {
            "score": {"$meta": "textScore"},
            "session_id": 1,
            "last_updated_at": 1,
            "chat_session_created_at": 1,
            "messages": 1,
        },
    ).sort([("score", {"$meta": "textScore"})])

    sessions: List[Dict[str, Any]] = []
    for doc in cursor:
        sessions.append(
            {
                "session_id": doc.get("session_id") or str(doc.get("_id")),
                "last_updated_at": doc.get("last_updated_at"),
                "chat_session_created_at": doc.get("chat_session_created_at"),
                "messages": trim_messages(doc.get("messages") or []),
            }
        )

    result = {
        "sessions": sessions,
        "summary": {
            "query_text": query_text,
            "include_terms": include_terms,
            "exclude_terms": exclude_terms,
            "sessions": len(sessions),
            "collection": COLLECTION_NAME,
        },
    }

    out_path = OUT_DIR / f"candidates_{utc_now_compact()}.json"
    out_path.write_text(json.dumps(result, default=str, ensure_ascii=True, indent=2), encoding="utf-8")
    return {"candidates_path": str(out_path), "summary": result["summary"]}


def tool_build_dictionary_parallel(args: Dict[str, Any]) -> Dict[str, Any]:
    candidates_path = Path(args["candidates_path"])
    if not candidates_path.exists():
        raise FileNotFoundError(f"candidates_path not found: {candidates_path}")

    dictionary_path, stats = build_recipe_dictionary_parallel(
        candidates_path=candidates_path,
        question=args["question"],
        out_dir=OUT_DIR,
        model=EXTRACT_MODEL,
        max_workers=8,
        chunk_char_limit=50000,  # aim for 1 chunk per session (no splitting)
    )

    return {"dictionary_path": str(dictionary_path), "stats": stats}


def tool_compute_exhaustive_with_ci(args: Dict[str, Any]) -> Dict[str, Any]:
    dictionary_path = Path(args["dictionary_path"])
    if not dictionary_path.exists():
        raise FileNotFoundError(f"dictionary_path not found: {dictionary_path}")

    question = args["question"]
    page_size = int(args.get("page_size", 200))

    instructions = f"""
You are a data analyst. Use the python tool (Code Interpreter) to answer the user's question
exhaustively from the dictionary JSON in the prompt.

MANDATORY:
- If DICTIONARY_JSON is present, write it to dictionary.json first.
- Load dictionary.json
- Build a fully exhaustive table of matching events (do not stop early)
- Deduplicate robustly (use evidence keys)
- Normalize temperatures when possible
- Output:
    1) TOTAL_ROWS=<n>
    2) RESULTS_FILE=results.csv
    3) First {page_size} lines as: date | temp | outcome | evidence

User question:
{question}
"""

    dictionary_text = dictionary_path.read_text(encoding="utf-8")

    client = OpenAI()
    resp = client.responses.create(
        model=CI_MODEL,
        tools=[{"type": "code_interpreter", "container": {"type": "auto"}}],
        tool_choice="required",
        include=["code_interpreter_call.outputs"],
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": instructions + "\n\nDICTIONARY_JSON:\n" + dictionary_text,
                    }
                ],
            }
        ],
    )

    return {"answer_text": (resp.output_text or "").strip()}


# ----------------------------
# Bot runner (simple, fixed sequence)
# ----------------------------

def expect_tool_call(response, expected_name: str) -> Any:
    tool_calls = [item for item in response.output if getattr(item, "type", None) == "function_call"]
    if len(tool_calls) != 1 or tool_calls[0].name != expected_name:
        raise RuntimeError(f"Expected tool call: {expected_name}")
    return tool_calls[0]


def run_bot(question: str) -> str:
    client = OpenAI()
    input_list: List[Dict[str, Any]] = [{"role": "user", "content": question}]

    # Step 1: mongo_text_search
    response = client.responses.create(
        model=MODEL,
        instructions=BOT_INSTRUCTIONS,
        tools=TOOLS,
        input=input_list,
        parallel_tool_calls=False,
    )
    call = expect_tool_call(response, "mongo_text_search")
    args = json.loads(call.arguments or "{}")
    print("TOOL_CALL mongo_text_search args=" + json.dumps(args, ensure_ascii=True), flush=True)
    tool_result = tool_mongo_text_search(args)
    print("TOOL_RESULT mongo_text_search=" + json.dumps(tool_result.get("summary"), default=str, ensure_ascii=True), flush=True)

    input_list += response.output
    input_list.append(
        {"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(tool_result)}
    )

    # Step 2: build_dictionary_parallel
    response = client.responses.create(
        model=MODEL,
        instructions=BOT_INSTRUCTIONS,
        tools=TOOLS,
        input=input_list,
        parallel_tool_calls=False,
    )
    call = expect_tool_call(response, "build_dictionary_parallel")
    args = json.loads(call.arguments or "{}")
    print("TOOL_CALL build_dictionary_parallel args=" + json.dumps(args, ensure_ascii=True), flush=True)
    tool_result = tool_build_dictionary_parallel(args)
    print("TOOL_RESULT build_dictionary_parallel=" + json.dumps(tool_result.get("stats"), default=str, ensure_ascii=True), flush=True)

    input_list += response.output
    input_list.append(
        {"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(tool_result)}
    )

    # Step 3: compute_exhaustive_with_ci
    response = client.responses.create(
        model=MODEL,
        instructions=BOT_INSTRUCTIONS,
        tools=TOOLS,
        input=input_list,
        parallel_tool_calls=False,
    )
    call = expect_tool_call(response, "compute_exhaustive_with_ci")
    args = json.loads(call.arguments or "{}")
    print("TOOL_CALL compute_exhaustive_with_ci args=" + json.dumps(args, ensure_ascii=True), flush=True)
    tool_result = tool_compute_exhaustive_with_ci(args)
    print("TOOL_RESULT compute_exhaustive_with_ci=returned_text", flush=True)
    return tool_result.get("answer_text", "")


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY.")
    answer = run_bot(DEFAULT_QUESTION)
    print(answer)


if __name__ == "__main__":
    main()
