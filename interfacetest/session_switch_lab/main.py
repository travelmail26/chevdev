#!/usr/bin/env python3
"""Single launcher for shared web + Telegram lab.

Usage:
  python main.py

Starts:
- shared backend API
- Perplexity-style web UI
- Telegram bridge bot (cheftestdev token)
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib import request


LAB_ROOT = Path(__file__).resolve().parent
WEB_ROOT = LAB_ROOT / "perplexity_clone_lab"
BACKEND_SCRIPT = LAB_ROOT / "shared_session_backend.py"
TELEGRAM_BRIDGE_SCRIPT = LAB_ROOT / "telegram_bridge_bot.py"
RUNTIME_DIR = LAB_ROOT / "runtime"
SESSION_STORE_PATH = RUNTIME_DIR / "session_store.json"

DEFAULT_BACKEND_PORT = 9002
DEFAULT_WEB_PORT = 9001


def resolve_web_public_url(web_port: int, explicit: str | None = None) -> str:
    if explicit:
        return explicit.rstrip("/")

    env_url = os.getenv("LAB_WEB_PUBLIC_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")

    codespace_name = os.getenv("CODESPACE_NAME", "").strip()
    if codespace_name:
        return f"https://{codespace_name}-{web_port}.app.github.dev"

    return f"http://127.0.0.1:{web_port}"


def find_conflicting_bot_processes() -> list[str]:
    """Detect other Telegram bot runners that can steal updates for the same token."""
    try:
        result = subprocess.run(
            ["pgrep", "-af", "chef/chefmain/main.py|chef/chefmain/telegram_bot.py"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return []

    conflicts: list[str] = []
    current_pid = os.getpid()
    for raw in (result.stdout or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if "pgrep -af" in line:
            continue
        if str(current_pid) in line:
            continue
        conflicts.append(line)
    return conflicts


def clear_lab_memory() -> None:
    """Clear persisted shared-session memory for a fresh run."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if SESSION_STORE_PATH.exists():
        SESSION_STORE_PATH.unlink()


class ServiceStack:
    def __init__(
        self,
        backend_port: int,
        web_port: int,
        web_public_url: str,
        enable_real_web_research: bool,
        enable_real_telegram_generic: bool,
        enable_telegram_bridge: bool,
    ) -> None:
        self.backend_port = backend_port
        self.web_port = web_port
        self.web_public_url = web_public_url
        self.enable_real_web_research = enable_real_web_research
        self.enable_real_telegram_generic = enable_real_telegram_generic
        self.enable_telegram_bridge = enable_telegram_bridge

        self.backend_url = f"http://127.0.0.1:{self.backend_port}"
        self.web_url = f"http://127.0.0.1:{self.web_port}"

        self.backend_proc: subprocess.Popen | None = None
        self.web_proc: subprocess.Popen | None = None
        self.telegram_proc: subprocess.Popen | None = None

    def _spawn_backend(self) -> None:
        env = {
            **os.environ,
            "LAB_BACKEND_PORT": str(self.backend_port),
            "LAB_ENABLE_REAL_WEB_RESEARCH": "1" if self.enable_real_web_research else "0",
            "LAB_ENABLE_REAL_TELEGRAM_GENERIC": "1" if self.enable_real_telegram_generic else "0",
        }
        self.backend_proc = subprocess.Popen(
            [sys.executable, str(BACKEND_SCRIPT)],
            cwd=str(LAB_ROOT),
            env=env,
        )

    def _spawn_web(self) -> None:
        env = {
            **os.environ,
            "PORT": str(self.web_port),
            "LAB_SHARED_BACKEND_URL": self.backend_url,
        }
        self.web_proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(WEB_ROOT),
            env=env,
        )

    def _spawn_telegram_bridge(self) -> None:
        if not self.enable_telegram_bridge:
            return
        env = {
            **os.environ,
            "LAB_SHARED_BACKEND_URL": self.backend_url,
            "LAB_WEB_PUBLIC_URL": self.web_public_url,
        }
        self.telegram_proc = subprocess.Popen(
            [sys.executable, str(TELEGRAM_BRIDGE_SCRIPT)],
            cwd=str(LAB_ROOT),
            env=env,
        )

    def _wait_for_url(self, url: str, timeout_seconds: int = 90) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            try:
                req = request.Request(url, method="GET")
                with request.urlopen(req, timeout=3) as resp:
                    if 200 <= resp.status < 500:
                        return True
            except Exception:
                pass
            time.sleep(1)
        return False

    def start(self) -> None:
        self._spawn_backend()
        self._spawn_web()

        backend_ready = self._wait_for_url(f"{self.backend_url}/health", timeout_seconds=60)
        web_ready = self._wait_for_url(self.web_url, timeout_seconds=120)

        if not backend_ready:
            raise RuntimeError("Backend did not become ready")
        if not web_ready:
            raise RuntimeError("Web server did not become ready")

        self._spawn_telegram_bridge()

    def stop(self) -> None:
        # Graceful stop order:
        # 1) Telegram bridge via SIGINT (lets PTB polling close cleanly)
        # 2) web/backend via terminate
        # 3) force kill leftovers
        if self.telegram_proc and self.telegram_proc.poll() is None:
            try:
                self.telegram_proc.send_signal(signal.SIGINT)
            except Exception:
                pass

        for proc in [self.web_proc, self.backend_proc]:
            if not proc or proc.poll() is not None:
                continue
            try:
                proc.terminate()
            except Exception:
                pass

        time.sleep(2)

        for proc in [self.telegram_proc, self.web_proc, self.backend_proc]:
            if not proc or proc.poll() is not None:
                continue
            try:
                proc.kill()
            except Exception:
                pass

    def children_healthy(self) -> bool:
        # If any started child exits, treat as unhealthy.
        for proc in [self.backend_proc, self.web_proc, self.telegram_proc]:
            if proc and proc.poll() is not None:
                return False
        return True


def print_banner(stack: ServiceStack) -> None:
    print("\nSession Switch Lab is running.")
    print(f"Open this URL in browser: {stack.web_public_url}")
    print(f"Local web URL:            {stack.web_url}")
    print(f"Local backend URL:        {stack.backend_url}")
    print("\nTelegram side:")
    print("- Open cheftestdev in Telegram")
    print("- Send: /start")
    print("- Use the /web link it returns (includes your uid)")
    print("- Then switch back and forth between Telegram and web")
    print("\nMemory policy:")
    print("- Lab shared-session memory is cleared automatically at startup.")
    print("\nPress Ctrl+C to stop.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Single launcher for web + Telegram shared session lab")
    parser.add_argument("--backend-port", type=int, default=DEFAULT_BACKEND_PORT)
    parser.add_argument("--web-port", type=int, default=DEFAULT_WEB_PORT)
    parser.add_argument("--web-public-url", default="", help="Public URL to share in Telegram /web command")
    parser.add_argument("--no-real-web", action="store_true", help="Disable live Perplexity web research")
    parser.add_argument("--no-real-telegram", action="store_true", help="Disable live xAI generic Telegram responses")
    parser.add_argument("--real-telegram", action="store_true", help="Deprecated alias (Telegram real model is on by default)")
    parser.add_argument("--no-telegram-bridge", action="store_true", help="Do not start Telegram bridge bot")
    parser.add_argument("--keep-memory", action="store_true", help="Do not clear shared session memory at startup")
    args = parser.parse_args()

    web_public_url = resolve_web_public_url(args.web_port, explicit=args.web_public_url or None)

    stack = ServiceStack(
        backend_port=args.backend_port,
        web_port=args.web_port,
        web_public_url=web_public_url,
        enable_real_web_research=not args.no_real_web,
        enable_real_telegram_generic=(not args.no_real_telegram) or args.real_telegram,
        enable_telegram_bridge=not args.no_telegram_bridge,
    )

    def _handle_signal(_sig, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        conflicts = find_conflicting_bot_processes()
        if conflicts:
            print("Startup blocked: found conflicting chef bot process(es) that can intercept Telegram updates.")
            for line in conflicts:
                print(f"  - {line}")
            print("Stop them first, then re-run:")
            print('  pkill -f "chef/chefmain/main.py|chef/chefmain/telegram_bot.py"')
            return 1

        if not args.keep_memory:
            clear_lab_memory()
            print("Startup: cleared lab shared-session memory.")

        stack.start()
        print_banner(stack)

        while True:
            time.sleep(2)
            if not stack.children_healthy():
                raise RuntimeError("One or more child services exited unexpectedly")

    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Startup/runtime failed: {exc}")
        return 1
    finally:
        stack.stop()


if __name__ == "__main__":
    raise SystemExit(main())
