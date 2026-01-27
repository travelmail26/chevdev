"""
LLM NOTE:
This module turns a Telegram message into an LLM response and stores
both sides of the conversation in MongoDB via mongo_store.py.

Flow overview:
1) route_message() receives message_object (user_id + user_message + session_info).
2) It loads or starts a Mongo chat session and appends the user message.
3) It calls OpenAI Chat Completions with the stored context + system prompt.
4) It stores the assistant reply and returns it to the Telegram bot.
"""

import logging
import os
import sys
import time
from typing import Any, Dict, List

import requests

try:
    from dotenv import load_dotenv

    # Load .env so local runs get keys without extra setup.
    load_dotenv()
except Exception:
    pass

# Ensure local imports resolve when running from repo root.
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from mongo_store import append_message, ensure_yen_database, get_or_start_conversation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are Yen, a concise, friendly assistant for a non-chef project. "
    "Keep replies short, clear, and actionable."
)


class MessageRouter:
    def __init__(self, openai_api_key: str | None = None):
        # Before example: no API key -> unclear errors; After example: logs missing key early.
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            logger.warning("MessageRouter: OPENAI_API_KEY not set; responses will be fallback text.")
        # Keep GPT-5 model as requested (do not change to 4o).
        self.model = os.getenv("OPENAI_MODEL", "gpt-5-2025-08-07")
        self.system_prompt = os.getenv("YEN_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)
        ensure_yen_database()

    def _call_openai(self, messages: List[Dict[str, Any]]) -> str:
        if not self.openai_api_key:
            return "I can reply once OPENAI_API_KEY is set."

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 256,
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json",
        }
        start = time.monotonic()
        try:
            # Before example: no timing logs; After example: duration_ms logged for tracing.
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.info("openai_call model=%s status=%s duration_ms=%s", self.model, response.status_code, duration_ms)
            if response.status_code != 200:
                return f"Upstream error {response.status_code}: {response.text[:200]}"
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.error("openai_call_failed error=%s", exc)
            return "Sorry, I hit an error while generating a response."

    def route_message(self, message_object: Dict[str, Any]) -> str:
        """Store the user message, call OpenAI, store the reply, and return it."""
        user_id = str(message_object.get("user_id", "unknown"))
        user_message = message_object.get("user_message", "")
        session_info = message_object.get("session_info")

        # Before example: no session -> missing context; After example: ensures a Mongo session exists.
        conversation = get_or_start_conversation(
            user_id,
            session_info=session_info,
            system_prompt=self.system_prompt,
        )
        if not conversation:
            return "Storage unavailable (missing MONGODB_URI or pymongo)."

        chat_session_id = conversation["chat_session_id"]
        append_message(user_id, "user", user_message, chat_session_id=chat_session_id, session_info=session_info)

        messages = list(conversation.get("messages") or [])
        if not messages or messages[0].get("role") != "system":
            # Before example: no system prompt sent; After example: system prompt injected for the model.
            messages.insert(0, {"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_message})

        assistant_reply = self._call_openai(messages)
        append_message(
            user_id,
            "assistant",
            assistant_reply,
            chat_session_id=chat_session_id,
            session_info=session_info,
        )
        return assistant_reply


if __name__ == "__main__":
    router = MessageRouter()
    print("Yen router ready. Type 'quit' to stop.")
    while True:
        user_input = input("You: ")
        if user_input.strip().lower() == "quit":
            break
        response = router.route_message({"user_id": "cli", "user_message": user_input, "session_info": {}})
        print(f"Yen: {response}")
