"""
LLM NOTE:
This module runs the Yen Telegram bot.

Flow overview:
1) setup_bot() loads the token and registers Telegram handlers.
2) handle_message() builds a message_object and calls MessageRouter.
3) restart() starts a new Mongo session so history is reset.
4) run_bot_webhook_set() chooses polling vs webhook based on ENVIRONMENT.
"""

import logging
import os
import sys
import traceback
from typing import Dict

try:
    from dotenv import load_dotenv

    # Load default .env so local runs are easy.
    load_dotenv()
except Exception:
    pass

# Ensure local imports resolve when running from repo root.
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from message_router import MessageRouter
from mongo_store import start_conversation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

application = None
message_router = MessageRouter()


def detect_runtime() -> str:
    # Before example: runtime unclear; After example: returns "cloud_run" or "codespaces" or "default".
    if os.getenv("K_SERVICE"):
        return "cloud_run"
    if os.getenv("CODESPACES") == "true":
        return "codespaces"
    return "default"


def get_port() -> int:
    # Before example: PORT unset -> 8080; After example: PORT=9090 -> 9090.
    return int(os.getenv("PORT", "8080"))


def get_webhook_url(runtime: str) -> str | None:
    # Before example: webhook URL hard-coded; After example: runtime picks the right env var.
    if runtime == "codespaces":
        return os.getenv("TELEGRAM_WEBHOOK_CODESPACE")
    return os.getenv("TELEGRAM_WEBHOOK_URL")


def get_token() -> str:
    runtime = detect_runtime()
    environment = os.getenv("ENVIRONMENT", "development")

    if runtime in ("codespaces",) or environment == "development":
        token = os.getenv("TELEGRAM_DEV_KEY")
    else:
        token = os.getenv("TELEGRAM_KEY")

    # Before example: missing token -> crash later; After example: fail fast with clear error.
    if not token:
        raise ValueError("Missing TELEGRAM_DEV_KEY or TELEGRAM_KEY.")
    return token


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! I'm Yen. Send a message to get started.")


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    session_info: Dict[str, object] = {
        "user_id": user_id,
        "chat_id": update.effective_chat.id,
        "message_id": update.effective_message.message_id,
        "timestamp": update.effective_message.date.timestamp(),
        "timestamp_iso": update.effective_message.date.isoformat(),
        "username": update.effective_user.username,
        "first_name": update.effective_user.first_name,
        "last_name": update.effective_user.last_name,
        "trigger_command": "/restart",
    }

    # Before example: /restart reused old history; After example: new session gets a fresh chat_session_id.
    new_doc = start_conversation(user_id, session_info=session_info, system_prompt=message_router.system_prompt)
    if new_doc:
        await update.message.reply_text("New session started. How can I help?")
    else:
        await update.message.reply_text("Storage unavailable. Check MONGODB_URI.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            # Before example: non-text messages error; After example: friendly guidance.
            await update.message.reply_text("Text only for now. Please send a text message.")
            return

        user_id = str(update.message.from_user.id)
        user_text = update.message.text
        session_info: Dict[str, object] = {
            "user_id": user_id,
            "chat_id": update.message.chat_id,
            "message_id": update.message.message_id,
            "timestamp": update.message.date.timestamp(),
            "timestamp_iso": update.message.date.isoformat(),
            "username": update.message.from_user.username,
            "first_name": update.message.from_user.first_name,
            "last_name": update.message.from_user.last_name,
        }

        # Before example: raw text only -> no metadata; After example: message_object includes session_info.
        message_object = {
            "user_id": user_id,
            "user_message": user_text,
            "session_info": session_info,
        }

        reply = message_router.route_message(message_object)
        await update.message.reply_text(reply)
    except Exception as exc:
        logger.error("handle_message error=%s\n%s", exc, traceback.format_exc())
        await update.message.reply_text("Sorry, I ran into an error.")


def setup_bot() -> Application:
    token = get_token()
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("restart", restart))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(~filters.TEXT, handle_message))

    return app


def run_bot_webhook_set() -> None:
    """Run webhook if configured; otherwise fall back to polling."""
    runtime = detect_runtime()
    app = setup_bot()

    webhook_url = get_webhook_url(runtime)
    if webhook_url:
        # Before example: webhook URL unused -> polling only; After example: webhook starts when URL is set.
        app.run_webhook(
            listen="0.0.0.0",
            port=get_port(),
            url_path="webhook",
            webhook_url=f"{webhook_url}/webhook",
        )
        return

    app.run_polling()
