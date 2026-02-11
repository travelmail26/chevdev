import os
from typing import Any, Dict

import requests


class TelegramRawClient:
    """Small raw client for Bot API methods not exposed in python-telegram-bot yet."""

    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("TELEGRAM_DEV_KEY") or os.getenv("TELEGRAM_KEY")
        if not self.token:
            raise ValueError("Missing TELEGRAM_DEV_KEY/TELEGRAM_KEY")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def call(self, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(f"{self.base_url}/{method}", json=payload, timeout=30)
        try:
            return response.json()
        except Exception:
            return {"ok": False, "status": response.status_code, "raw": response.text[:600]}

    def send_message_draft(self, chat_id: int, text: str) -> Dict[str, Any]:
        # Before example: only editMessageText fallback exists.
        # After example: try native sendMessageDraft first when supported by Telegram account mode.
        payload = {"chat_id": chat_id, "text": text}
        return self.call("sendMessageDraft", payload)
