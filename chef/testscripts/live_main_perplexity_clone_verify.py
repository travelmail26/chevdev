#!/usr/bin/env python3
"""Live verification for main.py + existing Perplexity clone + Telegram webhook path."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests
from pymongo import MongoClient


REPO_ROOT = Path("/workspaces/chevdev")
MAIN_PATH = REPO_ROOT / "chef" / "chefmain" / "main.py"
OUT_DIR = REPO_ROOT / "chef" / "testscripts" / "output" / "live_main_perplexity_clone_verify"
OUT_DIR.mkdir(parents=True, exist_ok=True)

WEB_PORT = int(os.getenv("LIVE_VERIFY_WEB_PORT", "9131"))
BACKEND_PORT = int(os.getenv("LIVE_VERIFY_BACKEND_PORT", "9132"))
MAIN_WEBHOOK_PORT = int(os.getenv("LIVE_VERIFY_MAIN_PORT", "8080"))
TEST_UID = os.getenv("TELEGRAM_TEST_CHAT_ID", "1275063227").strip()


def wait_for_url(url: str, timeout_seconds: int = 120) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=5)
            if 200 <= r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def wait_for_webhook(port: int, timeout_seconds: int = 120) -> bool:
    deadline = time.time() + timeout_seconds
    url = f"http://127.0.0.1:{port}/webhook"
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code in {200, 400, 401, 403, 404, 405}:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def run_playwright_phase1(web_url: str, uid: str, screenshot_1: Path) -> dict:
    js = f"""
import {{ chromium }} from '/workspaces/chevdev/testscripts/livecook/node_modules/playwright/index.mjs';
const browser = await chromium.launch({{ headless: true }});
const page = await browser.newPage({{ viewport: {{ width: 1365, height: 900 }} }});

let chatPosts = 0;
page.on('request', req => {{
  if (req.method() === 'POST' && req.url().includes('/api/chat')) chatPosts += 1;
}});

await page.goto('{web_url}/?uid={uid}', {{ waitUntil: 'networkidle' }});

async function waitAssistantCountIncrease(before) {{
  await page.waitForFunction(
    (count) => document.querySelectorAll('[data-testid=\"message-assistant\"]').length > count,
    before,
    {{ timeout: 60000 }}
  );
}}

async function sendTurn(text) {{
  const before = await page.locator('[data-testid=\"message-assistant\"]').count();
  await page.fill('[data-testid=\"input-chat\"]', text);
  await page.click('[data-testid=\"button-send\"]');
  await waitAssistantCountIncrease(before);
}}

await sendTurn('thinking about making fallow hashbrown');
await sendTurn('search the internet for common mistakes for butter emulsion and keep it short');
await page.screenshot({{ path: '{screenshot_1.as_posix()}', fullPage: true }});

console.log(JSON.stringify({{ ok: true, chatPosts }}));
await browser.close();
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", js],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Playwright phase 1 failed: {proc.stderr or proc.stdout}")
    return json.loads((proc.stdout or "").strip())


def run_playwright_phase2(web_url: str, uid: str, screenshot_2: Path) -> dict:
    js2 = f"""
import {{ chromium }} from '/workspaces/chevdev/testscripts/livecook/node_modules/playwright/index.mjs';
const browser = await chromium.launch({{ headless: true }});
const page = await browser.newPage({{ viewport: {{ width: 1365, height: 900 }} }});
await page.goto('{web_url}/?uid={uid}', {{ waitUntil: 'networkidle' }});
await page.waitForTimeout(1500);

const before = await page.locator('[data-testid=\"message-assistant\"]').count();
await page.fill('[data-testid=\"input-chat\"]', 'what did i just ask?');
await page.click('[data-testid=\"button-send\"]');
await page.waitForFunction(
  (count) => document.querySelectorAll('[data-testid=\"message-assistant\"]').length > count,
  before,
  {{ timeout: 60000 }}
);
await page.waitForTimeout(500);
await page.screenshot({{ path: '{screenshot_2.as_posix()}', fullPage: true }});
const body = await page.locator('body').innerText();
await browser.close();
console.log(JSON.stringify({{ ok: true, body_head: body.slice(0, 2400) }}));
"""
    proc2 = subprocess.run(
        ["node", "--input-type=module", "-e", js2],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc2.returncode != 0:
        raise RuntimeError(f"Playwright phase 2 failed: {proc2.stderr or proc2.stdout}")
    return json.loads((proc2.stdout or "").strip())


def post_fake_webhook_text(user_id: str, text: str) -> requests.Response:
    now = int(time.time())
    update = {
        "update_id": now,
        "message": {
            "message_id": now,
            "date": now,
            "chat": {"id": int(user_id), "type": "private"},
            "from": {"id": int(user_id), "is_bot": False, "first_name": "Greg", "username": "greg"},
            "text": text,
        },
    }
    return requests.post(f"http://127.0.0.1:{MAIN_WEBHOOK_PORT}/webhook", json=update, timeout=30)


def _resolve_telegram_token() -> str:
    return (os.getenv("TELEGRAM_DEV_KEY") or os.getenv("TELEGRAM_KEY") or "").strip()


def get_telegram_webhook_info() -> dict:
    token = _resolve_telegram_token()
    if not token:
        return {"ok": False, "reason": "missing_telegram_token"}
    resp = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("ok"):
        return {"ok": False, "reason": "api_not_ok", "payload": payload}
    return {"ok": True, "result": payload.get("result", {})}


def wait_for_telegram_webhook(expected_url: str | None, timeout_seconds: int = 60) -> dict:
    if not expected_url:
        return {"ok": False, "reason": "expected_url_missing"}
    deadline = time.time() + timeout_seconds
    last = {}
    while time.time() < deadline:
        info = get_telegram_webhook_info()
        last = info
        if info.get("ok"):
            result = info.get("result") or {}
            if str(result.get("url", "")).strip() == str(expected_url).strip():
                return info
        time.sleep(2)
    return last


def mongo_snapshot(user_id: str) -> dict:
    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        return {"available": False, "reason": "MONGODB_URI missing"}

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")

    uid = str(user_id)
    mode_doc = client["chef_chatbot"]["bot_modes"].find_one({"user_id": uid}) or {}
    general_docs = list(
        client["chat_general"]["chat_general"].find(
            {"user_id": uid},
            {"_id": 1, "last_updated_at": 1, "bot_mode": 1},
        )
    )
    cheflog_count = client["chef_chatbot"]["chat_sessions"].count_documents({"user_id": uid})
    dietlog_count = client["chef_dietlog"]["chat_dietlog_sessions"].count_documents({"user_id": uid})

    latest_general = None
    if general_docs:
        latest_general = sorted(
            general_docs,
            key=lambda d: str(d.get("last_updated_at", "")),
        )[-1]

    return {
        "available": True,
        "bot_mode": mode_doc.get("bot_mode"),
        "active_session_id": mode_doc.get("active_session_id"),
        "general_count": len(general_docs),
        "general_latest_id": str(latest_general.get("_id")) if latest_general else None,
        "general_latest_updated": latest_general.get("last_updated_at") if latest_general else None,
        "cheflog_count": int(cheflog_count),
        "dietlog_count": int(dietlog_count),
    }


def main() -> int:
    screenshot_1 = OUT_DIR / "01_clone_web_before_telegram.png"
    screenshot_2 = OUT_DIR / "02_clone_web_after_telegram.png"
    log_path = OUT_DIR / "main_runtime.log"
    evidence_path = OUT_DIR / "evidence.json"
    summary_path = OUT_DIR / "summary.txt"
    mongo_before = mongo_snapshot(TEST_UID)

    env = {
        **os.environ,
        "BOT_MODE": "general",
        "PORT": str(MAIN_WEBHOOK_PORT),
        "TELEGRAM_CODESPACES_TRANSPORT": "webhook",
        "ENABLE_PERPLEXITY_CLONE": "1",
        "PERPLEXITY_WEB_PORT": str(WEB_PORT),
        "PERPLEXITY_SHARED_BACKEND_PORT": str(BACKEND_PORT),
        "TELEGRAM_TEST_CHAT_ID": TEST_UID,
    }

    with open(log_path, "w", encoding="utf-8") as lf:
        proc = subprocess.Popen(
            [sys.executable, str(MAIN_PATH)],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=lf,
            stderr=subprocess.STDOUT,
            text=True,
        )

    try:
        if not wait_for_url(f"http://127.0.0.1:{WEB_PORT}", timeout_seconds=150):
            raise RuntimeError("Perplexity clone web did not come up")
        if not wait_for_url(f"http://127.0.0.1:{BACKEND_PORT}/health", timeout_seconds=90):
            raise RuntimeError("Shared backend did not come up")
        if not wait_for_webhook(MAIN_WEBHOOK_PORT, timeout_seconds=90):
            raise RuntimeError(f"Telegram webhook endpoint not ready on port {MAIN_WEBHOOK_PORT}")
        expected_webhook_url = f"{str(os.getenv('TELEGRAM_WEBHOOK_CODESPACE', '')).strip().rstrip('/')}/webhook"
        telegram_webhook_info = wait_for_telegram_webhook(expected_webhook_url, timeout_seconds=60)
        if expected_webhook_url and telegram_webhook_info.get("ok"):
            got_url = str((telegram_webhook_info.get("result") or {}).get("url", "")).strip()
            if got_url != expected_webhook_url:
                raise RuntimeError(f"Telegram webhook URL mismatch. expected={expected_webhook_url} got={got_url}")

        # Force test traffic into general mode only, then reset that session.
        mode_resp = post_fake_webhook_text(TEST_UID, "/general")
        time.sleep(2)
        web_cmd_resp = post_fake_webhook_text(TEST_UID, "/web")
        time.sleep(2)
        restart_resp = post_fake_webhook_text(TEST_UID, "/restart")
        time.sleep(2)

        web_result_phase_1 = run_playwright_phase1(
            web_url=f"http://127.0.0.1:{WEB_PORT}",
            uid=TEST_UID,
            screenshot_1=screenshot_1,
        )

        # Trigger a live Telegram-path turn while web is running.
        telegram_note = "telegram note saffron-42"
        webhook_resp = post_fake_webhook_text(TEST_UID, telegram_note)
        time.sleep(5)
        webhook_followup_resp = post_fake_webhook_text(TEST_UID, "what did i just ask?")
        time.sleep(4)
        webhook_code_resp = post_fake_webhook_text(TEST_UID, "code 11")
        time.sleep(4)

        # Web follow-up after Telegram webhook turns.
        web_result_phase_2 = run_playwright_phase2(
            web_url=f"http://127.0.0.1:{WEB_PORT}",
            uid=TEST_UID,
            screenshot_2=screenshot_2,
        )

        # Pull shared session for concrete evidence
        session_resp = requests.get(
            f"http://127.0.0.1:{BACKEND_PORT}/api/session/{TEST_UID}?bot_mode=general",
            timeout=20,
        )
        session_resp.raise_for_status()
        session_data = session_resp.json()
        mongo_after = mongo_snapshot(TEST_UID)

        runtime_log = log_path.read_text(encoding="utf-8", errors="replace")
        runtime_hits = []
        for marker in [
            f"route_message start: user_id={TEST_UID}",
            "xai_tool_round start",
            "Perplexity clone URL:",
            "POST /webhook",
        ]:
            if marker in runtime_log:
                runtime_hits.append(marker)
        runtime_flags = {
            "has_chat_not_found": "Chat not found" in runtime_log,
            "explicit_search_true_count": runtime_log.count("explicit_search_intent=True"),
            "explicit_search_false_count": runtime_log.count("explicit_search_intent=False"),
        }

        statuses = [
            mode_resp.status_code,
            web_cmd_resp.status_code,
            restart_resp.status_code,
            webhook_resp.status_code,
            webhook_followup_resp.status_code,
            webhook_code_resp.status_code,
        ]
        if any(code != 200 for code in statuses):
            raise RuntimeError(f"Unexpected webhook status codes: {statuses}")

        if runtime_flags["has_chat_not_found"]:
            raise RuntimeError("Telegram path hit 'Chat not found' during test run")

        if runtime_flags["explicit_search_true_count"] < 1 or runtime_flags["explicit_search_false_count"] < 1:
            raise RuntimeError(f"Unexpected explicit_search_intent signal counts: {runtime_flags}")

        if mongo_after.get("available"):
            if mongo_after.get("bot_mode") != "general":
                raise RuntimeError(f"Expected bot_mode=general, got {mongo_after.get('bot_mode')}")
            if mongo_after.get("cheflog_count") != mongo_before.get("cheflog_count"):
                raise RuntimeError(
                    f"cheflog docs changed for uid {TEST_UID}: before={mongo_before.get('cheflog_count')} after={mongo_after.get('cheflog_count')}"
                )
            if mongo_after.get("dietlog_count") != mongo_before.get("dietlog_count"):
                raise RuntimeError(
                    f"dietlog docs changed for uid {TEST_UID}: before={mongo_before.get('dietlog_count')} after={mongo_after.get('dietlog_count')}"
                )
            if mongo_after.get("general_count", 0) < mongo_before.get("general_count", 0):
                raise RuntimeError(
                    f"general docs count moved backwards: before={mongo_before.get('general_count')} after={mongo_after.get('general_count')}"
                )

        evidence = {
            "uid": TEST_UID,
            "web_port": WEB_PORT,
            "backend_port": BACKEND_PORT,
            "webhook_port": MAIN_WEBHOOK_PORT,
            "webhook_statuses": [
                mode_resp.status_code,
                web_cmd_resp.status_code,
                restart_resp.status_code,
                webhook_resp.status_code,
                webhook_followup_resp.status_code,
                webhook_code_resp.status_code,
            ],
            "runtime_flags": runtime_flags,
            "mongo_before": mongo_before,
            "mongo_after": mongo_after,
            "telegram_expected_webhook_url": expected_webhook_url,
            "telegram_webhook_info": telegram_webhook_info,
            "runtime_markers_found": runtime_hits,
            "session_message_count": session_data.get("message_count"),
            "session_tail": (session_data.get("messages") or [])[-10:],
            "web_phase_1": web_result_phase_1,
            "web_phase_2": web_result_phase_2,
            "screenshots": [str(screenshot_1), str(screenshot_2)],
            "main_log": str(log_path),
        }
        evidence_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

        summary = [
            f"uid: {TEST_UID}",
            f"web_url: http://127.0.0.1:{WEB_PORT}/?uid={TEST_UID}",
            f"backend_health: http://127.0.0.1:{BACKEND_PORT}/health",
            f"webhook_statuses: {evidence['webhook_statuses']}",
            f"mongo_before: {mongo_before}",
            f"mongo_after: {mongo_after}",
            f"telegram_expected_webhook_url: {expected_webhook_url}",
            f"telegram_webhook_info: {telegram_webhook_info}",
            f"runtime_flags: {runtime_flags}",
            f"session_message_count: {evidence['session_message_count']}",
            f"runtime_markers_found: {evidence['runtime_markers_found']}",
            f"screenshot_1: {screenshot_1}",
            f"screenshot_2: {screenshot_2}",
            f"evidence_json: {evidence_path}",
            f"main_log: {log_path}",
        ]
        summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8")

        print(f"EVIDENCE_JSON {evidence_path}")
        print(f"SUMMARY_TXT {summary_path}")
        print(f"SCREENSHOT_1 {screenshot_1}")
        print(f"SCREENSHOT_2 {screenshot_2}")
        return 0
    finally:
        try:
            proc.send_signal(signal.SIGINT)
        except Exception:
            pass
        time.sleep(1)
        if proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        time.sleep(1)
        if proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
