"""media_caption_reconciler
=================================
Orchestrates media caption reconciliation *through* OpenAI's tool-calling
interface. The script itself only exposes a couple of narrow tools; the model
inspects conversation history, decides which captions to apply, and then uses the
same tools to persist updates.

Why this design?
----------------
The user asked for an agentic approach where "OpenAI should call tools" and
"use the API's intelligence to go through commands". Therefore, this module:

- Defines tiny, well-documented tool functions (`list_pending_media`,
  `save_media_caption`).
- Lets OpenAI decide when to call each tool and what caption to save.
- Provides thorough docstrings and inline before/after examples so another LLM
  can understand expectations without inspecting the wider codebase.

Usage snapshot::

    # Before running, export credentials (Mongo + OpenAI).
    export OPENAI_API_KEY=...  # already used by chefmain/message_router.py
    export MONGODB_URI=...
    export MONGODB_DB_NAME=...
    export MONGODB_COLLECTION_NAME=...

    # Dry run (not executed here per instructions):
    PYTHONDONTWRITEBYTECODE=1 python chef/testscripts/media_caption_reconciler.py

High-level agent loop (delegated to OpenAI)
------------------------------------------
1. Model receives the system prompt below and the user's directive
   ("Reconcile up to N media items").
2. Model calls ``list_pending_media`` to inspect Firebase URLs paired with any
   nearby user descriptions.
3. For each unresolved item, the model either:
   - Uses the provided human description, or
   - Synthesises a short caption, or
   - Decides to leave a ``NEEDS_USER_DESCRIPTION`` note.
4. The model persists its choice via ``save_media_caption``.
5. The loop continues until OpenAI replies without tool calls, at which point
   the script returns the final assistant message (typically a short summary).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, Iterator, List, Optional, Sequence

import requests
from pymongo import MongoClient

# Media message prefixes we recognise. Example before: "[photo_url: ...]".
# Example after: the suffix "_url" is enough for the agent to process the entry.
MEDIA_PREFIXES: Sequence[str] = ("[photo_url:", "[video_url:", "[audio_url:")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-5-2025-08-07"  # Matches chefmain/message_router.py


@dataclass
class MediaCandidate:
    """Container for a single media message awaiting description.

    Attributes
    ----------
    session_id:
        Mongo document ``_id`` to update later.
    message_index:
        Position of the media stub within ``messages``.
    url:
        Public Firebase storage URL extracted from the user message.
    user_description:
        Optional free-form text supplied by the user in the following turn.
    """

    session_id: str
    message_index: int
    url: str
    user_description: Optional[str]


class MongoMediaStore:
    """Tiny helper to interact with the Mongo collection backing chat history."""

    def __init__(self, client: MongoClient, db_name: str, collection_name: str) -> None:
        self.client = client
        self.collection = client[db_name][collection_name]

    @classmethod
    def from_env(cls) -> "MongoMediaStore":
        """Instantiate the store using environment variables already required by chefmain."""

        return cls(
            MongoClient(os.environ["MONGODB_URI"]),
            os.environ.get("MONGODB_DB_NAME", "chef_chatbot"),
            os.environ.get("MONGODB_COLLECTION_NAME", "chat_sessions"),
        )

    def iter_sessions(self) -> Iterable[dict]:
        """Stream chat sessions lazily to keep memory usage predictable."""

        return self.collection.find({}, {"messages": 1})

    def list_pending_media(self, limit: int = 5) -> List[Dict[str, object]]:
        """Collect up to ``limit`` media entries that still need captions."""

        items: List[Dict[str, object]] = []
        for session in self.iter_sessions():
            for candidate in iter_media_candidates(session):
                items.append(
                    {
                        "session_id": candidate.session_id,
                        "message_index": candidate.message_index,
                        "media_url": candidate.url,
                        "user_description": candidate.user_description,
                        "needs_caption": candidate.user_description is None,
                    }
                )
                if len(items) >= limit:
                    return items
        return items

    def save_caption(self, session_id: str, message_index: int, caption: str, source: str) -> None:
        """Insert ``[media_description: ...]`` right after the media message."""

        # Example before: messages[message_index] == "[photo_url: ...]".
        # Example after: messages[message_index + 1] == "[media_description: ...]".
        payload = {
            "$push": {
                "messages": {
                    "$each": [
                        {
                            "role": "assistant",
                            "content": f"[media_description: {caption}]",
                            "metadata": {"source": source},
                        }
                    ],
                    "$position": message_index + 1,
                }
            }
        }
        self.collection.update_one({"_id": session_id}, payload)


STORE: Optional[MongoMediaStore] = None


def get_store() -> MongoMediaStore:
    """Return the global store, instantiating it from the environment on demand."""

    global STORE
    if STORE is None:
        STORE = MongoMediaStore.from_env()
    return STORE


def is_media_stub(content: str) -> bool:
    """Return True if the text looks like a media placeholder."""

    return any(content.startswith(prefix) for prefix in MEDIA_PREFIXES)


def extract_media_url(content: str) -> str:
    """Pull the raw URL out of ``[photo_url: https://...]`` style stubs."""

    # Example before: "[photo_url: https://example.com/pic.jpg]"
    # Example after:  "https://example.com/pic.jpg"
    return content.split(":", 1)[1].strip().strip("[] ")


def iter_media_candidates(session: dict) -> Iterator[MediaCandidate]:
    """Yield media candidates alongside any accompanying user description."""

    messages: List[dict] = session.get("messages", [])
    for index, message in enumerate(messages):
        if message.get("role") != "user":
            continue

        content = (message.get("content") or "").strip()
        if not content or not is_media_stub(content):
            continue

        followup = _find_followup_text(messages, start=index + 1)
        yield MediaCandidate(
            session_id=str(session.get("_id")),
            message_index=index,
            url=extract_media_url(content),
            user_description=followup,
        )


def _find_followup_text(messages: Sequence[dict], start: int) -> Optional[str]:
    """Return the next user text (if any) that is not another media stub."""

    for message in messages[start:]:
        if message.get("role") != "user":
            continue

        content = (message.get("content") or "").strip()
        if not content:
            continue

        if is_media_stub(content):
            # Example before: media -> media (no description yet).
            # Example after: we bail out so the agent can fabricate or request help.
            return None

        return content

    return None


# ---------------------------------------------------------------------------
# Tool functions exposed to OpenAI
# ---------------------------------------------------------------------------

def list_pending_media(limit: int = 5) -> Dict[str, object]:
    """Tool: return up to ``limit`` pending media entries for the agent to review."""

    store = get_store()
    items = store.list_pending_media(limit=limit)
    return {
        "items": items,
        "notes": (
            "Example before: only [photo_url: ...]. Example after: the agent saves "
            "[media_description: ...] for each item it processes."
        ),
    }


def save_media_caption(
    session_id: str,
    message_index: int,
    caption: str,
    source: str = "assistant",
) -> Dict[str, object]:
    """Tool: persist the caption immediately after the media stub."""

    store = get_store()
    store.save_caption(session_id=session_id, message_index=message_index, caption=caption, source=source)
    return {
        "status": "saved",
        "session_id": session_id,
        "message_index": message_index,
    }


TOOL_MAP = {
    "list_pending_media": list_pending_media,
    "save_media_caption": save_media_caption,
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_pending_media",
            "description": (
                "Return recent media uploads that still need descriptions. "
                "Call this before attempting to save captions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of entries to fetch (default 5).",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_media_caption",
            "description": (
                "Persist a caption immediately after the media stub. Use this after you "
                "decide on the best available description (human-provided or AI-generated)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "message_index": {"type": "integer"},
                    "caption": {"type": "string"},
                    "source": {
                        "type": "string",
                        "description": "free-form tag noting where the caption came from",
                        "default": "assistant",
                    },
                },
                "required": ["session_id", "message_index", "caption"],
            },
        },
    },
]

SYSTEM_INSTRUCTION = (
    "You reconcile media uploads for a cooking assistant. Use the provided tools to "
    "inspect pending items, prefer user-written descriptions when they exist, and "
    "write concise factual captions otherwise. If you truly lack context, save a "
    "caption of 'NEEDS_USER_DESCRIPTION'. Summarise your work when you finish."
)


def run_agent(initial_request: Optional[str] = None, *, temperature: float = 1.0) -> Dict[str, object]:
    """Drive the OpenAI tool loop and return the final assistant message payload."""

    if initial_request is None:
        initial_request = "Please reconcile up to 5 media entries."

    api_key = os.environ["OPENAI_API_KEY"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": initial_request},
    ]

    while True:
        payload = {
            "model": OPENAI_MODEL,
            "temperature": temperature,
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto",
            "parallel_tool_calls": False,
        }
        response = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        messages.append(message)

        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return message

        for tool_call in tool_calls:
            name = tool_call["function"]["name"]
            arguments = json.loads(tool_call["function"].get("arguments") or "{}")
            if name not in TOOL_MAP:
                result = {"error": f"Unknown tool: {name}"}
            else:
                result = TOOL_MAP[name](**arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(result),
                }
            )


def main() -> None:
    """CLI entrypoint (kept tiny so another LLM can swap in their own runner)."""

    logging.basicConfig(level=logging.INFO)
    final_message = run_agent()
    logging.info("Agent finished: %s", final_message.get("content"))


if __name__ == "__main__":
    main()
