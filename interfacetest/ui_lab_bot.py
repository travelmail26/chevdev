#!/usr/bin/env python3
import asyncio
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.error import BadRequest, RetryAfter
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

# Keep local imports predictable when launched as `python interfacetest/ui_lab_bot.py`.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from quick_apis import quick_openai_message, quick_perplexity_search
from quick_apis import quick_openai_message_stream
from telegram_raw import TelegramRawClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
LOG = logging.getLogger("interfacetest.ui_lab_bot")

MAX_TELEGRAM_TEXT = 3900
STREAM_CHARS_PER_EDIT = int(os.getenv("INTERFACETEST_STREAM_CHARS_PER_EDIT", "80"))
STREAM_MIN_EDIT_SECONDS = float(os.getenv("INTERFACETEST_STREAM_MIN_EDIT_SECONDS", "0.7"))


@dataclass
class ChatState:
    stop_requested: bool = False
    last_prompt: str = ""
    last_quick_text: str = ""
    last_search_query: str = ""
    last_search_text: str = ""
    last_search_citations: List[str] = field(default_factory=list)
    pending_stream_text: str = ""
    active_stream_message_id: Optional[int] = None
    stream_phase: str = "idle"


STATE_BY_CHAT: Dict[int, ChatState] = {}


def get_state(chat_id: int) -> ChatState:
    if chat_id not in STATE_BY_CHAT:
        STATE_BY_CHAT[chat_id] = ChatState()
    return STATE_BY_CHAT[chat_id]


def clip_telegram_text(text: str) -> str:
    if len(text) <= MAX_TELEGRAM_TEXT:
        return text
    return text[: MAX_TELEGRAM_TEXT - 120] + "\n\n[truncated for Telegram length limit]"


def first_line(text: str) -> str:
    line = (text or "").strip().splitlines()
    if not line:
        return ""
    return line[0][:280]


def menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("1) Quick + Typing", callback_data="run:quick"),
                InlineKeyboardButton("2) Search + Progress", callback_data="run:search"),
            ],
            [
                InlineKeyboardButton("3) Edit-Streaming", callback_data="run:stream"),
                InlineKeyboardButton("4) Draft Attempt", callback_data="run:draft"),
            ],
        ]
    )


def quick_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Shorter", callback_data="quick:shorter"),
                InlineKeyboardButton("More Detail", callback_data="quick:detail"),
            ],
            [InlineKeyboardButton("Re-Stream", callback_data="quick:restream")],
        ]
    )


def search_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Headline", callback_data="search:headline"),
                InlineKeyboardButton("Details", callback_data="search:details"),
            ],
            [
                InlineKeyboardButton("Sources", callback_data="search:sources"),
                InlineKeyboardButton("Search Again", callback_data="search:again"),
            ],
        ]
    )


def stop_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Stop", callback_data="ctrl:stop")]])


def continue_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("Continue", callback_data="ctrl:continue")]])


async def safe_edit(message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text=clip_telegram_text(text), reply_markup=reply_markup)
    except RetryAfter as exc:
        await asyncio.sleep(float(exc.retry_after) + 0.1)
        await message.edit_text(text=clip_telegram_text(text), reply_markup=reply_markup)
    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            return
        LOG.info("safe_edit skipped: %s", exc)


async def safe_answer_callback(query, text: str = "") -> None:
    try:
        await query.answer(text)
    except BadRequest as exc:
        LOG.info("callback answer skipped: %s", exc)


async def typing_pulse(context: ContextTypes.DEFAULT_TYPE, chat_id: int, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            continue


async def call_with_typing(context: ContextTypes.DEFAULT_TYPE, chat_id: int, fn, *args):
    stop_event = asyncio.Event()
    pulse_task = asyncio.create_task(typing_pulse(context, chat_id, stop_event))
    try:
        result = await asyncio.to_thread(fn, *args)
        return result
    finally:
        stop_event.set()
        await pulse_task


async def stream_text_by_edit(
    context: ContextTypes.DEFAULT_TYPE,
    message,
    chat_id: int,
    text: str,
    state: ChatState,
) -> None:
    state.stream_phase = "editing"
    words = text.split()
    if not words:
        state.stream_phase = "idle"
        await safe_edit(message, "Streaming demo finished with empty text.")
        return

    built_words: List[str] = []
    last_edit_at = 0.0
    last_typing_at = 0.0
    stopped_index = -1

    # Before example: Telegram receives one late wall-of-text message.
    # After example: the same message is edited every ~600ms for pseudo-token streaming.
    for index, word in enumerate(words):
        if state.stop_requested:
            stopped_index = index
            break

        built_words.append(word)
        now = time.monotonic()

        hit_punctuation = word.endswith((".", "!", "?", ",", ";", ":"))
        long_enough = len(" ".join(built_words)) >= 120
        enough_time = now - last_edit_at >= 0.6
        is_last = index == len(words) - 1

        if (hit_punctuation and enough_time) or (long_enough and enough_time) or is_last:
            preview = " ".join(built_words)
            await safe_edit(message, f"Streaming...\n\n{preview} ▌", reply_markup=stop_keyboard())
            last_edit_at = now

        if now - last_typing_at >= 4.0:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            last_typing_at = now

        await asyncio.sleep(0.03)

    if stopped_index >= 0:
        remainder = " ".join(words[stopped_index:]).strip()
        state.pending_stream_text = remainder
        partial = " ".join(built_words).strip()
        state.stream_phase = "paused"
        await safe_edit(
            message,
            f"Stopped and acknowledged.\n\n{partial}\n\nTap Continue to resume.",
            reply_markup=continue_keyboard(),
        )
        return

    state.pending_stream_text = ""
    state.stream_phase = "idle"
    final_text = " ".join(built_words).strip()
    await safe_edit(message, f"Streaming complete.\n\n{final_text}", reply_markup=quick_result_keyboard())


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Interface test lab is running on this bot.\n\n"
        "Try one by one:\n"
        "- /demo_quick <message>\n"
        "- /demo_search <query>\n"
        "- /demo_stream <message>\n"
        "- /demo_cookie_stop\n"
        "- /demo_draft <message>\n"
        "- /uimenu"
    )
    await update.message.reply_text(text, reply_markup=menu_keyboard())


async def cmd_uimenu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Choose a UI demo:", reply_markup=menu_keyboard())


async def run_quick_demo(message, context: ContextTypes.DEFAULT_TYPE, prompt: str) -> None:
    chat_id = message.chat_id
    state = get_state(chat_id)
    state.last_prompt = prompt

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    status_msg = await message.reply_text("Got it. Thinking...")

    result = await call_with_typing(context, chat_id, quick_openai_message, prompt)
    if not result.get("ok"):
        await safe_edit(status_msg, f"Quick demo failed: {result.get('error', 'unknown error')}")
        return

    state.last_quick_text = result.get("text", "")
    duration = result.get("duration_ms", "?")
    model = result.get("model", "unknown")
    final = (
        f"Quick answer ({duration}ms, {model})\n"
        f"{state.last_quick_text}"
    )
    await safe_edit(status_msg, final, reply_markup=quick_result_keyboard())


async def run_search_demo(message, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    chat_id = message.chat_id
    state = get_state(chat_id)
    state.last_search_query = query

    status_msg = await message.reply_text(
        "Search request received.\n\n"
        "1/3 Read query ▱\n"
        "2/3 Search web ▱\n"
        "3/3 Draft answer ▱"
    )

    await safe_edit(
        status_msg,
        "Search request received.\n\n"
        "1/3 Read query ✅\n"
        "2/3 Search web ▱\n"
        "3/3 Draft answer ▱",
    )

    result = await call_with_typing(context, chat_id, quick_perplexity_search, query)

    await safe_edit(
        status_msg,
        "Search request received.\n\n"
        "1/3 Read query ✅\n"
        "2/3 Search web ✅\n"
        "3/3 Draft answer ✅",
    )

    if not result.get("ok"):
        await status_msg.reply_text(f"Search demo failed: {result.get('error', 'unknown error')}")
        return

    state.last_search_text = result.get("text", "")
    state.last_search_citations = result.get("citations", [])
    duration = result.get("duration_ms", "?")
    model = result.get("model", "unknown")
    headline = first_line(state.last_search_text) or "(no headline returned)"

    await safe_edit(
        status_msg,
        f"Search complete ({duration}ms, {model})\n\n{headline}",
        reply_markup=search_result_keyboard(),
    )


async def run_stream_demo(message, context: ContextTypes.DEFAULT_TYPE, prompt: str) -> None:
    chat_id = message.chat_id
    state = get_state(chat_id)
    state.stop_requested = False
    state.last_prompt = prompt
    state.stream_phase = "generating"

    status_msg = await message.reply_text(
        "Streaming demo: connected. Waiting for first tokens...\n\nYou can press Stop now.",
        reply_markup=stop_keyboard(),
    )
    state.active_stream_message_id = status_msg.message_id

    full_text = ""
    last_flushed_chars = 0
    last_edit_at = 0.0
    last_typing_at = 0.0
    start_time = time.monotonic()
    saw_first_delta = False

    try:
        async for event in quick_openai_message_stream(prompt):
            if state.stop_requested:
                LOG.info("stream_stop_observed chat_id=%s phase=live_stream", chat_id)
                state.stream_phase = "paused"
                state.pending_stream_text = ""
                if full_text.strip():
                    await safe_edit(
                        status_msg,
                        "Streaming stopped and acknowledged.\n\n"
                        + clip_telegram_text(full_text)
                        + "\n\n(Partial output kept.)",
                        reply_markup=quick_result_keyboard(),
                    )
                else:
                    await safe_edit(
                        status_msg,
                        "Stopped and acknowledged before first token.\n\nNo partial output yet.",
                        reply_markup=quick_result_keyboard(),
                    )
                return

            if event.get("type") == "delta":
                full_text = str(event.get("full_text") or full_text)
                state.last_quick_text = full_text

                now = time.monotonic()
                if not saw_first_delta:
                    saw_first_delta = True
                    await safe_edit(
                        status_msg,
                        "Streaming started.\n\n" + clip_telegram_text(full_text + " ▌"),
                        reply_markup=stop_keyboard(),
                    )
                    last_flushed_chars = len(full_text)
                    last_edit_at = now
                    continue

                new_chars_since_flush = len(full_text) - last_flushed_chars
                enough_chars = new_chars_since_flush >= STREAM_CHARS_PER_EDIT
                enough_time = (now - last_edit_at) >= STREAM_MIN_EDIT_SECONDS
                punctuation_break = full_text.endswith((".", "!", "?", "\n"))

                # Before example: every tiny token edit risked Telegram rate limits.
                # After example: flush at ~80 chars or punctuation with >=0.7s spacing.
                if (enough_chars and enough_time) or (punctuation_break and enough_time):
                    await safe_edit(
                        status_msg,
                        "Streaming...\n\n" + clip_telegram_text(full_text + " ▌"),
                        reply_markup=stop_keyboard(),
                    )
                    last_flushed_chars = len(full_text)
                    last_edit_at = now

                if now - last_typing_at >= 4.0:
                    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
                    last_typing_at = now

            if event.get("type") == "done":
                break

        if not full_text.strip():
            state.stream_phase = "idle"
            await safe_edit(
                status_msg,
                "Streaming ended with empty output.\n\nTry again with a shorter prompt.",
            )
            return

        state.stream_phase = "idle"
        await safe_edit(
            status_msg,
            "Streaming complete.\n\n" + clip_telegram_text(full_text),
            reply_markup=quick_result_keyboard(),
        )
        elapsed = int(time.monotonic() - start_time)
        LOG.info("stream_complete chat_id=%s chars=%s elapsed_s=%s", chat_id, len(full_text), elapsed)
    except Exception as exc:
        state.stream_phase = "idle"
        await safe_edit(status_msg, f"Stream demo failed: {exc}")


async def run_draft_demo(message, context: ContextTypes.DEFAULT_TYPE, prompt: str) -> None:
    chat_id = message.chat_id
    status_msg = await message.reply_text("Trying native sendMessageDraft...")

    def call_draft_method():
        raw = TelegramRawClient(token=context.bot.token)
        return raw.send_message_draft(chat_id=chat_id, text=f"Draft: {prompt[:180]}")

    result = await asyncio.to_thread(call_draft_method)

    if result.get("ok"):
        await safe_edit(
            status_msg,
            "sendMessageDraft returned ok=true. Check the chat for draft behavior.",
        )
        return

    error_description = result.get("description") or result.get("raw") or str(result)
    await safe_edit(
        status_msg,
        "sendMessageDraft not available here, falling back to edit-based streaming.\n\n"
        f"Telegram response: {error_description[:250]}",
    )
    await run_stream_demo(message, context, prompt)


async def cmd_demo_quick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = " ".join(context.args).strip() or "Give me one practical productivity tip."
    await run_quick_demo(update.effective_message, context, prompt)


async def cmd_demo_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args).strip() or "latest AI model releases this week"
    await run_search_demo(update.effective_message, context, query)


async def cmd_demo_stream(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = " ".join(context.args).strip() or "Write a short update about electric vehicles in 2026."
    await run_stream_demo(update.effective_message, context, prompt)


async def cmd_demo_cookie_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = (
        "Create a very detailed chewy chocolate chip cookie recipe for a beginner baker. "
        "Include exact gram and cup measures, oven prep, dough rest options, mixing science, "
        "texture troubleshooting, substitutions for common allergies, a half-batch table, "
        "make-ahead and freezer workflow, and a short quick-start summary at the end."
    )
    await run_stream_demo(update.effective_message, context, prompt)


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    state = get_state(chat_id)
    state.stop_requested = True
    LOG.info("stop_requested text_or_command chat_id=%s", chat_id)
    await update.effective_message.reply_text(
        "Stop requested and acknowledged.\n\n"
        "If generation is running, I will pause at the next safe checkpoint."
    )


async def cmd_demo_draft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = " ".join(context.args).strip() or "This is a draft streaming probe"
    await run_draft_demo(update.effective_message, context, prompt)


async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await safe_answer_callback(query)
    data = query.data or ""
    chat_id = query.message.chat_id
    state = get_state(chat_id)

    if data == "ctrl:stop":
        state.stop_requested = True
        LOG.info("stop_requested button chat_id=%s message_id=%s", chat_id, query.message.message_id if query.message else None)
        await safe_answer_callback(query, "Stopping...")
        return

    if data == "ctrl:continue":
        if not state.pending_stream_text:
            await query.message.reply_text("Nothing pending to continue.")
            return
        state.stop_requested = False
        state.stream_phase = "editing"
        follow_msg = await query.message.reply_text("Continuing stream...", reply_markup=stop_keyboard())
        state.active_stream_message_id = follow_msg.message_id
        await stream_text_by_edit(context, follow_msg, chat_id, state.pending_stream_text, state)
        return

    if data == "run:quick":
        await query.message.reply_text("Running quick demo with sample prompt...")
        await run_quick_demo(query.message, context, "Summarize why continuous feedback improves chat UX.")
        return

    if data == "run:search":
        await query.message.reply_text("Running search demo with sample query...")
        await run_search_demo(query.message, context, "latest improvements in Telegram bot UX")
        return

    if data == "run:stream":
        await query.message.reply_text("Running edit-streaming demo with sample prompt...")
        await run_stream_demo(query.message, context, "Give 5 concise notes on modern bot messaging UX patterns.")
        return

    if data == "run:draft":
        await query.message.reply_text("Running sendMessageDraft attempt...")
        await run_draft_demo(query.message, context, "Draft probe from interfacetest")
        return

    if data == "quick:shorter":
        if not state.last_quick_text:
            await query.message.reply_text("No quick response cached yet.")
            return
        prompt = f"Rewrite this as 3 short bullets:\n\n{state.last_quick_text}"
        await run_quick_demo(query.message, context, prompt)
        return

    if data == "quick:detail":
        if not state.last_quick_text:
            await query.message.reply_text("No quick response cached yet.")
            return
        prompt = f"Expand this with practical detail and examples:\n\n{state.last_quick_text}"
        await run_quick_demo(query.message, context, prompt)
        return

    if data == "quick:restream":
        if not state.last_quick_text:
            await query.message.reply_text("No response available to re-stream.")
            return
        state.stop_requested = False
        msg = await query.message.reply_text("Re-streaming cached response...", reply_markup=stop_keyboard())
        await stream_text_by_edit(context, msg, chat_id, state.last_quick_text, state)
        return

    if data == "search:headline":
        headline = first_line(state.last_search_text) or "No search result cached yet."
        await query.message.reply_text(f"Headline view:\n\n{headline}")
        return

    if data == "search:details":
        details = state.last_search_text or "No search result cached yet."
        await query.message.reply_text(clip_telegram_text(f"Details view:\n\n{details}"))
        return

    if data == "search:sources":
        if not state.last_search_citations:
            await query.message.reply_text("No source list returned for the last search.")
            return
        lines = [f"[{idx}] {url}" for idx, url in enumerate(state.last_search_citations, start=1)]
        await query.message.reply_text("Sources:\n" + "\n".join(lines[:20]))
        return

    if data == "search:again":
        if not state.last_search_query:
            await query.message.reply_text("No previous search query found.")
            return
        await run_search_demo(query.message, context, state.last_search_query)
        return


def get_token() -> str:
    env = os.getenv("ENVIRONMENT", "development")
    if env == "development":
        token = os.getenv("TELEGRAM_DEV_KEY") or os.getenv("TELEGRAM_KEY")
    else:
        token = os.getenv("TELEGRAM_KEY") or os.getenv("TELEGRAM_DEV_KEY")
    if not token:
        raise ValueError("Missing TELEGRAM_DEV_KEY/TELEGRAM_KEY")
    return token


def main() -> None:
    load_dotenv()
    token = get_token()

    # Before example: unclear startup mode.
    # After example: explicit startup log with ENVIRONMENT and token source intent.
    LOG.info("Starting interfacetest UI lab bot. env=%s", os.getenv("ENVIRONMENT", "development"))

    # Before example: updates were processed sequentially, so stop inputs could queue behind long handlers.
    # After example: concurrent updates allow stop button/text updates to be handled while streaming work runs.
    app = Application.builder().token(token).concurrent_updates(8).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("uimenu", cmd_uimenu))
    app.add_handler(CommandHandler("demo_quick", cmd_demo_quick))
    app.add_handler(CommandHandler("demo_search", cmd_demo_search))
    app.add_handler(CommandHandler("demo_stream", cmd_demo_stream))
    app.add_handler(CommandHandler("demo_cookie_stop", cmd_demo_cookie_stop))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("demo_draft", cmd_demo_draft))
    app.add_handler(MessageHandler(filters.Regex(re.compile(r"^\s*stop\s*$", re.IGNORECASE)), cmd_stop))
    app.add_handler(CallbackQueryHandler(cb_handler))

    # This script is a local demo harness, so polling keeps setup simple.
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
