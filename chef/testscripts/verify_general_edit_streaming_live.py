#!/usr/bin/env python3
"""
Live verification for general-mode single-message edit streaming.
Creates evidence files (JSON, logs, PNG screenshots) in chef/testscripts/output/general_streaming_verify/.
"""

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

from PIL import Image, ImageDraw, ImageFont

sys.path.append('/workspaces/chevdev/chef/chefmain')

import telegram_bot
from telegram_bot import setup_bot, restart, bot_mode_switch_general, handle_message, stop_stream

OUT_DIR = '/workspaces/chevdev/chef/testscripts/output/general_streaming_verify'
os.makedirs(OUT_DIR, exist_ok=True)

CHAT_ID = int(os.getenv('TELEGRAM_TEST_CHAT_ID', '1275063227'))
USER_ID = CHAT_ID


@dataclass
class FakeUser:
    id: int
    username: str = 'live_stream_verify'
    first_name: str = 'Live'
    last_name: str = 'Verify'


@dataclass
class FakeChat:
    id: int


class FakeMessage:
    _next_id = 930000

    def __init__(self, bot, chat_id: int, user_id: int, text: str):
        FakeMessage._next_id += 1
        self.bot = bot
        self.chat_id = chat_id
        self.from_user = FakeUser(user_id)
        self.message_id = FakeMessage._next_id
        self.date = datetime.now(timezone.utc)
        self.text = text
        self.audio = None
        self.voice = None
        self.photo = None
        self.video = None

    async def reply_text(self, text: str):
        return await self.bot.send_message(chat_id=self.chat_id, text=text)


class FakeUpdate:
    def __init__(self, bot, chat_id: int, user_id: int, text: str):
        self.message = FakeMessage(bot, chat_id, user_id, text)
        self.effective_user = self.message.from_user
        self.effective_chat = FakeChat(chat_id)
        self.effective_message = self.message


class FakeContext:
    def __init__(self, app):
        self.application = app
        self.bot = app.bot
        self.job_queue = app.job_queue


async def call_handler(handler, context, text: str):
    update = FakeUpdate(context.bot, CHAT_ID, USER_ID, text)
    await handler(update, context)


async def run_text(context, text: str):
    update = FakeUpdate(context.bot, CHAT_ID, USER_ID, text)
    await handle_message(update, context)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def render_text_screenshot(path: str, title: str, lines: List[str]) -> None:
    font = ImageFont.load_default()
    width = 1600
    margin = 20
    line_h = 18
    wrapped: List[str] = [title, ""]
    for line in lines:
        text = str(line)
        while len(text) > 170:
            wrapped.append(text[:170])
            text = text[170:]
        wrapped.append(text)
    height = max(600, margin * 2 + line_h * (len(wrapped) + 2))
    img = Image.new('RGB', (width, height), color=(250, 250, 250))
    draw = ImageDraw.Draw(img)
    y = margin
    for line in wrapped:
        draw.text((margin, y), line, fill=(20, 20, 20), font=font)
        y += line_h
    img.save(path)


async def main() -> None:
    os.environ['ENVIRONMENT'] = 'development'
    os.environ['GENERAL_EDIT_STREAMING'] = '1'

    app = setup_bot()
    context = FakeContext(app)

    evidence: Dict[str, Any] = {
        'started_at': now_iso(),
        'chat_id': CHAT_ID,
        'scenarios': [],
        'log_lines': [],
    }

    # Capture key logs.
    class Capture(logging.Handler):
        def emit(self, record):
            msg = self.format(record)
            if (
                'xai_tool_round start' in msg
                or 'tool_context_messages:' in msg
                or 'route_message start:' in msg
                or 'route_message end:' in msg
                or 'stream_edit_failed' in msg
            ):
                evidence['log_lines'].append(msg)

    log_handler = Capture()
    log_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logging.getLogger().addHandler(log_handler)

    # Wrap stream edit helper to capture message-id timeline.
    original_safe_edit = telegram_bot._safe_edit_stream_message
    edit_events: List[Dict[str, Any]] = []

    async def wrapped_safe_edit(bot, chat_id: int, message_id: int, text: str):
        edit_events.append({
            'ts': time.time(),
            'chat_id': chat_id,
            'message_id': message_id,
            'text_preview': str(text).replace('\n', ' ')[:220],
            'text_len': len(str(text or '')),
        })
        return await original_safe_edit(bot, chat_id, message_id, text)

    telegram_bot._safe_edit_stream_message = wrapped_safe_edit

    async def run_scenario(name: str, turns: List[str], stop_after_seconds: float = 0.0):
        scenario_start_index = len(edit_events)
        await call_handler(restart, context, '/restart')
        await call_handler(bot_mode_switch_general, context, '/general')

        if stop_after_seconds > 0:
            task = asyncio.create_task(run_text(context, turns[0]))
            await asyncio.sleep(stop_after_seconds)
            await call_handler(stop_stream, context, '/stop')
            await task
        else:
            for turn in turns:
                await run_text(context, turn)

        scenario_events = edit_events[scenario_start_index:]
        message_ids = sorted({e['message_id'] for e in scenario_events})
        scenario = {
            'name': name,
            'turns': turns,
            'edit_event_count': len(scenario_events),
            'unique_message_ids': message_ids,
            'first_edit': scenario_events[0] if scenario_events else None,
            'last_edit': scenario_events[-1] if scenario_events else None,
            'stopped_marker_seen': any('[Stopped by user]' in (e['text_preview'] or '') for e in scenario_events),
        }
        evidence['scenarios'].append(scenario)

    # Scenario 1: general brainstorming (non-tool path)
    await run_scenario(
        'general_brainstorm_non_tool',
        ["without searching, give me 20 detailed hashbrown brainstorming ideas for a brunch menu"],
    )

    # Scenario 2: internet search (tool/function-call path) then follow-up general
    await run_scenario(
        'general_with_perplexity_then_followup',
        [
            "search the internet for best hashbrown thickness and cite two sources",
            "without searching again, explain in 2 sentences why thickness affects crispness",
        ],
    )

    # Scenario 3: stop behavior
    await run_scenario(
        'general_stop_midstream',
        [
            "search the internet for detailed hashbrown technique comparisons and include key quotes",
        ],
        stop_after_seconds=2.5,
    )

    telegram_bot._safe_edit_stream_message = original_safe_edit
    logging.getLogger().removeHandler(log_handler)

    evidence['finished_at'] = now_iso()

    json_path = os.path.join(OUT_DIR, 'evidence.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(evidence, f, indent=2)

    log_path = os.path.join(OUT_DIR, 'captured_logs.txt')
    with open(log_path, 'w', encoding='utf-8') as f:
        for line in evidence['log_lines']:
            f.write(line + '\n')

    summary_lines: List[str] = []
    summary_lines.append(f"Started: {evidence['started_at']}")
    summary_lines.append(f"Finished: {evidence['finished_at']}")
    summary_lines.append("")
    for sc in evidence['scenarios']:
        summary_lines.append(f"Scenario: {sc['name']}")
        summary_lines.append(f"  edit_event_count={sc['edit_event_count']}")
        summary_lines.append(f"  unique_message_ids={sc['unique_message_ids']}")
        summary_lines.append(f"  stopped_marker_seen={sc['stopped_marker_seen']}")
        if sc['first_edit']:
            summary_lines.append(f"  first_edit={sc['first_edit']['text_preview']}")
        if sc['last_edit']:
            summary_lines.append(f"  last_edit={sc['last_edit']['text_preview']}")
        summary_lines.append("")

    summary_txt = os.path.join(OUT_DIR, 'summary.txt')
    with open(summary_txt, 'w', encoding='utf-8') as f:
        f.write('\n'.join(summary_lines) + '\n')

    screenshot_summary = os.path.join(OUT_DIR, 'screenshot_summary.png')
    render_text_screenshot(screenshot_summary, 'General Streaming Verification Summary', summary_lines)

    screenshot_logs = os.path.join(OUT_DIR, 'screenshot_logs.png')
    render_text_screenshot(
        screenshot_logs,
        'Captured Runtime Logs (Key Lines)',
        evidence['log_lines'][:80],
    )

    print('EVIDENCE_JSON', json_path)
    print('EVIDENCE_LOGS', log_path)
    print('EVIDENCE_SUMMARY', summary_txt)
    print('SCREENSHOT_SUMMARY', screenshot_summary)
    print('SCREENSHOT_LOGS', screenshot_logs)


if __name__ == '__main__':
    asyncio.run(main())
