#!/usr/bin/env python3
"""Telegram bridge bot for session-switch lab.

Routes Telegram messages into the shared lab backend so the same user can
switch between Telegram app and web UI seamlessly.
"""

from __future__ import annotations

import json
import os
from urllib import parse

import requests
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


BACKEND_URL = os.getenv("LAB_SHARED_BACKEND_URL", "http://127.0.0.1:9002").rstrip("/")
WEB_PUBLIC_URL = os.getenv("LAB_WEB_PUBLIC_URL", "http://127.0.0.1:9001").rstrip("/")


def _resolve_token() -> str:
    token = os.getenv("TELEGRAM_DEV_KEY") or os.getenv("TELEGRAM_KEY")
    if not token:
        raise RuntimeError("Missing TELEGRAM_DEV_KEY/TELEGRAM_KEY for telegram bridge bot")
    return token


def _canonical_user_id(update: Update) -> str:
    user_id = update.effective_user.id if update and update.effective_user else "unknown"
    return f"tg_{user_id}"


def _web_link_for_user(canonical_user_id: str) -> str:
    params = parse.urlencode({"uid": canonical_user_id})
    return f"{WEB_PUBLIC_URL}/?{params}"


def _split_for_telegram(text: str, chunk_size: int = 3900) -> list[str]:
    content = str(text or "")
    if len(content) <= chunk_size:
        return [content]
    parts: list[str] = []
    while content:
        parts.append(content[:chunk_size])
        content = content[chunk_size:]
    return parts


def _post_json(path: str, payload: dict) -> dict:
    response = requests.post(
        f"{BACKEND_URL}{path}",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=45,
    )
    response.raise_for_status()
    return response.json()


def _get_json(path: str) -> dict:
    response = requests.get(f"{BACKEND_URL}{path}", timeout=20)
    response.raise_for_status()
    return response.json()


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    canonical_user_id = _canonical_user_id(update)
    web_link = _web_link_for_user(canonical_user_id)
    await update.message.reply_text(
        "Session bridge is active.\n\n"
        f"1) Open web UI: {web_link}\n"
        "2) Ask research questions in web UI.\n"
        "3) Return here for generic answers and recap.\n\n"
        "Commands: /web /new /session /mode <general|dietlog|cheflog>"
    )


async def web_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    canonical_user_id = _canonical_user_id(update)
    await update.message.reply_text(_web_link_for_user(canonical_user_id))


async def new_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    canonical_user_id = _canonical_user_id(update)
    payload = _post_json("/api/session/new", {"canonical_user_id": canonical_user_id})
    await update.message.reply_text(
        f"New shared session started.\n"
        f"session_id: {payload.get('active_session_id')}\n"
        f"web: {_web_link_for_user(canonical_user_id)}"
    )


async def mode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    canonical_user_id = _canonical_user_id(update)
    if not context.args:
        await update.message.reply_text("Usage: /mode <general|dietlog|cheflog>")
        return

    mode = str(context.args[0]).strip().lower()
    payload = _post_json(
        "/api/mode",
        {
            "canonical_user_id": canonical_user_id,
            "bot_mode": mode,
        },
    )
    await update.message.reply_text(
        f"Mode set to {payload.get('bot_mode', mode)}.\n"
        f"session_id: {payload.get('active_session_id')}"
    )


async def session_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    canonical_user_id = _canonical_user_id(update)
    snapshot = _get_json(f"/api/session/{canonical_user_id}")
    short = {
        "canonical_user_id": snapshot.get("canonical_user_id"),
        "bot_mode": snapshot.get("bot_mode"),
        "active_session_id": snapshot.get("active_session_id"),
        "message_count": snapshot.get("message_count"),
    }
    await update.message.reply_text(json.dumps(short, indent=2))


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    canonical_user_id = _canonical_user_id(update)
    user_text = (update.message.text or "").strip()
    if not user_text:
        return

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    except Exception:
        pass

    payload = _post_json(
        "/api/chat",
        {
            "canonical_user_id": canonical_user_id,
            "source": "telegram",
            "message": user_text,
        },
    )
    answer = payload.get("assistant_text", "")
    if not answer:
        answer = "No response text returned from backend."

    for chunk in _split_for_telegram(answer):
        await update.message.reply_text(chunk)


async def health_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    health = _get_json("/health")
    await update.message.reply_text(json.dumps(health, indent=2))


def main() -> None:
    token = _resolve_token()
    app = Application.builder().token(token).concurrent_updates(8).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("web", web_cmd))
    app.add_handler(CommandHandler("new", new_cmd))
    app.add_handler(CommandHandler("mode", mode_cmd))
    app.add_handler(CommandHandler("session", session_cmd))
    app.add_handler(CommandHandler("health", health_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))

    print("telegram_bridge_bot: polling started")
    print(f"telegram_bridge_bot: backend={BACKEND_URL} web={WEB_PUBLIC_URL}")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
