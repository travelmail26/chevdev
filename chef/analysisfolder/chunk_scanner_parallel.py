#!/usr/bin/env python3
"""
chunk_scanner_parallel.py

Parallel dictionary builder:
- Takes candidates JSON from Mongo lexical search
- Splits into chunks by character budget
- Calls OpenAI in parallel to extract events via attention
- Merges to a single dictionary JSON
"""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from pydantic import BaseModel, Field


MAX_MESSAGE_CHARS = 1200


class Evidence(BaseModel):
    session_id: str = Field(..., description="Chat session identifier.")
    message_index: Optional[int] = Field(None, description="Index within session if known.")
    excerpt: str = Field(..., description="Short excerpt supporting the event.")


class CookEvent(BaseModel):
    date_iso: Optional[str] = Field(None, description="ISO datetime if known.")
    focus_terms: List[str] = Field(default_factory=list, description="Key entities, e.g. onions.")
    temperature: Optional[str] = Field(None, description="Raw temperature or heat descriptor.")
    method: Optional[str] = Field(None, description="Cooking method if stated.")
    outcome: Optional[str] = Field(None, description="Outcome if stated.")
    evidence: Evidence
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extractor confidence.")


class ChunkExtraction(BaseModel):
    events: List[CookEvent] = Field(default_factory=list)


@dataclass
class ExtractConfig:
    model: str
    max_retries: int = 4


def utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def backoff_sleep(attempt: int) -> None:
    # Before: no backoff -> After: small exponential backoff with jitter.
    base = min(8.0, (2.0 ** attempt))
    time.sleep(base + random.random())


def safe_load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def flatten_candidates(candidates: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Expected candidates format:
      {
        "sessions": [
           {
             "session_id": "...",
             "last_updated_at": "...",
             "chat_session_created_at": "...",
             "messages": [
                 {"index": 12, "role": "user|assistant", "content": "..."},
                 ...
             ]
           },
           ...
        ],
        "summary": {...}
      }
    """
    rows: List[Dict[str, Any]] = []
    for session in candidates.get("sessions", []) or []:
        session_id = session.get("session_id") or session.get("_id") or "unknown_session"
        session_date = session.get("last_updated_at") or session.get("chat_session_created_at")
        for message in (session.get("messages") or []):
            content = message.get("content") or ""
            if not content:
                continue
            rows.append(
                {
                    "session_id": str(session_id),
                    "session_date": session_date,
                    "message_index": message.get("index"),
                    "role": message.get("role"),
                    "content": content,
                }
            )
    return rows


def chunk_rows_by_session(rows: List[Dict[str, Any]], chunk_char_limit: int) -> List[List[Dict[str, Any]]]:
    """
    Packs rows into chunks by session_id, then by character budget.
    This keeps each chunk within a single conversation.
    """
    chunks: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    used = 0
    current_session = None

    for row in rows:
        session_id = row.get("session_id")
        line = f"[{row['session_id']}|{row.get('session_date')}|{row.get('message_index')}|{row.get('role')}]: {row['content']}\n"
        cost = len(line)

        if current_session is None:
            current_session = session_id

        if session_id != current_session:
            # Before: mixed sessions in a chunk -> After: chunks stay within one session.
            if current:
                chunks.append(current)
            current = []
            used = 0
            current_session = session_id

        if current and used + cost > chunk_char_limit:
            chunks.append(current)
            current = []
            used = 0

        current.append(row)
        used += cost

    if current:
        chunks.append(current)

    return chunks


def render_chunk_text(chunk: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for row in chunk:
        excerpt = row["content"]
        if len(excerpt) > MAX_MESSAGE_CHARS:
            # Before: 5000 chars -> After: 1200 chars + "..."
            excerpt = excerpt[:MAX_MESSAGE_CHARS].rstrip() + "..."
        lines.append(
            f"[{row['session_id']}|{row.get('session_date')}|{row.get('message_index')}|{row.get('role')}]: {excerpt}"
        )
    return "\n".join(lines)


def extract_events_from_chunk(
    client: OpenAI,
    cfg: ExtractConfig,
    question: str,
    chunk_text: str,
) -> ChunkExtraction:
    """
    Structured outputs to enforce schema.
    """
    instructions = f"""
You extract cooking-history EVENTS from chat snippets.

You MUST:
- Read the snippets
- Extract any event relevant to the user question
- Prefer numeric temperatures when present; otherwise use qualitative heat
- Include evidence with session_id + message_index + excerpt
- confidence:
   0.9+ if explicit numeric temperature tied to the focus item
   0.6-0.8 if plausible but incomplete
   <0.6 if weak; still include for exhaustive recall

User question:
{question}
"""

    for attempt in range(cfg.max_retries + 1):
        try:
            resp = client.responses.parse(
                model=cfg.model,
                instructions=instructions,
                input=chunk_text,
                text_format=ChunkExtraction,
            )
            parsed = resp.output_parsed
            if parsed is None:
                return ChunkExtraction(events=[])
            return parsed
        except Exception:
            if attempt >= cfg.max_retries:
                raise
            backoff_sleep(attempt)

    return ChunkExtraction(events=[])


def merge_events(all_events: List[CookEvent]) -> List[Dict[str, Any]]:
    """
    Deduplicate with a conservative key:
    (session_id, message_index, temperature, method, outcome)
    """
    seen = set()
    merged: List[Dict[str, Any]] = []
    for event in all_events:
        key = (
            event.evidence.session_id,
            event.evidence.message_index,
            (event.temperature or "").strip().lower(),
            (event.method or "").strip().lower(),
            (event.outcome or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(event.model_dump())
    return merged


def build_recipe_dictionary_parallel(
    candidates_path: Path,
    question: str,
    out_dir: Path,
    model: str,
    max_workers: int,
    chunk_char_limit: int,
) -> Tuple[Path, Dict[str, Any]]:
    """
    Main entrypoint called by recipe_bot.py.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates = safe_load_json(candidates_path)
    rows = flatten_candidates(candidates)
    # Before: natural order -> After: grouped by session_id then message_index.
    rows.sort(key=lambda row: (row.get("session_id") or "", row.get("message_index") or 0))
    chunks = chunk_rows_by_session(rows, chunk_char_limit=chunk_char_limit)
    # Optional debug limiter: set CHUNK_LIMIT=N to scan only the first N chunks.
    chunk_limit_env = os.getenv("CHUNK_LIMIT")
    if chunk_limit_env:
        try:
            limit = int(chunk_limit_env)
            chunks = chunks[:limit]
        except ValueError:
            pass

    client = OpenAI()
    cfg = ExtractConfig(model=model)
    worker_count = min(max_workers, max(1, len(chunks)))

    all_events: List[CookEvent] = []
    errors: List[str] = []

    start = time.time()
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = []
        for chunk in chunks:
            chunk_text = render_chunk_text(chunk)
            futures.append(pool.submit(extract_events_from_chunk, client, cfg, question, chunk_text))

        for fut in as_completed(futures):
            try:
                extracted = fut.result()
                all_events.extend(extracted.events)
            except Exception as exc:
                errors.append(repr(exc))

    merged = merge_events(all_events)
    dictionary = {
        "schema": "recipe_dictionary.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "source_candidates_path": str(candidates_path),
        "events": merged,
        "stats": {
            "rows_scanned": len(rows),
            "chunks": len(chunks),
            "events_raw": len(all_events),
            "events_deduped": len(merged),
            "errors": len(errors),
            "elapsed_s": round(time.time() - start, 2),
            "max_workers": max_workers,
            "chunk_char_limit": chunk_char_limit,
            "model": model,
        },
        "errors": errors[:50],
    }

    out_path = out_dir / f"dictionary_{utc_now_compact()}.json"
    # Before: unordered dict -> After: JSON artifact on disk.
    out_path.write_text(json.dumps(dictionary, ensure_ascii=True, indent=2), encoding="utf-8")

    return out_path, dictionary["stats"]
