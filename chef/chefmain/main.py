# main.py

import logging
import sys
import os
import signal
import traceback
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from threading import Thread

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telegram_bot import run_bot_webhook_set
from utilities.history_messages import set_user_active_session, set_user_bot_mode

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logging.basicConfig(level=logging.DEBUG)

# Get the httpx logger
httpx_logger = logging.getLogger("httpx")

# Set the logging level to WARNING or higher
httpx_logger.setLevel(logging.WARNING)

PORT_NUMBER = os.getenv("PORT", "8080")
CHEFMAIN_DIR = Path(__file__).resolve().parent
REPO_ROOT = CHEFMAIN_DIR.parent.parent
PERPLEXITY_CLONE_ROOT = Path(
    os.getenv(
        "PERPLEXITY_CLONE_ROOT",
        str(REPO_ROOT / "interfacetest" / "session_switch_lab" / "perplexity_clone_lab"),
    )
)
PERPLEXITY_WEB_PORT = str(os.getenv("PERPLEXITY_WEB_PORT", "9001"))
PERPLEXITY_SHARED_BACKEND_PORT = str(os.getenv("PERPLEXITY_SHARED_BACKEND_PORT", "9002"))
DEFAULT_ENABLE_PERPLEXITY_CLONE = "1" if os.getenv("CODESPACES") == "true" else "0"
ENABLE_PERPLEXITY_CLONE = os.getenv("ENABLE_PERPLEXITY_CLONE", DEFAULT_ENABLE_PERPLEXITY_CLONE).strip().lower() not in {"0", "false", "no", "off"}
RESET_TEST_SESSION_ON_START = os.getenv("RESET_TEST_SESSION_ON_START", "1").strip().lower() not in {"0", "false", "no", "off"}


def _extract_codespaces_webhook_port() -> str | None:
    webhook_url = os.getenv("TELEGRAM_WEBHOOK_CODESPACE", "").strip()
    if not webhook_url:
        return None
    try:
        host = (urlparse(webhook_url).hostname or "").strip()
        if not host.endswith(".app.github.dev"):
            return None
        subdomain = host[: -len(".app.github.dev")]
        # Before example: "ominous-halibut-...-8080" could drift from PORT env.
        # After example:  extract trailing "-8080" and align runtime port.
        candidate = subdomain.rsplit("-", 1)[-1]
        if candidate.isdigit():
            return candidate
    except Exception:
        return None
    return None


def _align_port_with_codespaces_webhook() -> None:
    global PORT_NUMBER
    if os.getenv("CODESPACES") != "true":
        return
    webhook_port = _extract_codespaces_webhook_port()
    if not webhook_port:
        return
    current_port = str(os.getenv("PORT", PORT_NUMBER or "8080")).strip() or "8080"
    if current_port == webhook_port:
        PORT_NUMBER = current_port
        return
    # Before example: PORT=8180 with webhook URL ending -8080 caused Telegram delivery failures.
    # After example:  runtime forces PORT to webhook-matching value.
    logging.warning(
        "[Main] PORT mismatch detected (PORT=%s, webhook_port=%s). Aligning to webhook_port.",
        current_port,
        webhook_port,
    )
    os.environ["PORT"] = webhook_port
    PORT_NUMBER = webhook_port


def _reset_test_user_session_if_configured() -> None:
    if not RESET_TEST_SESSION_ON_START:
        return
    test_uid = os.getenv("TELEGRAM_TEST_CHAT_ID", "").strip()
    if not test_uid:
        return
    # Before example: restarting main reused old shared session context.
    # After example:  startup seeds a fresh general session for the configured test uid.
    session_info = {"user_id": test_uid, "trigger_command": "startup_reset"}
    set_user_bot_mode(test_uid, "general", session_info=session_info)
    new_session = set_user_active_session(test_uid, session_info=session_info)
    logging.info(
        "[Main] Startup reset: user_id=%s bot_mode=general chat_session_id=%s",
        test_uid,
        new_session.get("chat_session_id"),
    )


def _wait_for_url(url: str, timeout_seconds: int = 90) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            req = Request(url, method="GET")
            with urlopen(req, timeout=3) as resp:
                if 200 <= int(resp.status) < 500:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def _start_perplexity_clone_services() -> list[subprocess.Popen]:
    """Start existing Perplexity clone frontend + shared backend adapter."""
    if not ENABLE_PERPLEXITY_CLONE:
        logging.info("[Main] Perplexity clone startup disabled by ENABLE_PERPLEXITY_CLONE=0")
        return []

    if not PERPLEXITY_CLONE_ROOT.exists():
        raise RuntimeError(f"Perplexity clone root not found: {PERPLEXITY_CLONE_ROOT}")

    backend_script = CHEFMAIN_DIR / "perplexity_clone_shared_backend.py"
    if not backend_script.exists():
        raise RuntimeError(f"Missing backend adapter: {backend_script}")

    children: list[subprocess.Popen] = []

    backend_env = {
        **os.environ,
        "PERPLEXITY_SHARED_BACKEND_PORT": PERPLEXITY_SHARED_BACKEND_PORT,
    }
    backend_proc = subprocess.Popen(
        [sys.executable, str(backend_script)],
        cwd=str(CHEFMAIN_DIR),
        env=backend_env,
    )
    children.append(backend_proc)

    web_env = {
        **os.environ,
        "PORT": PERPLEXITY_WEB_PORT,
        "LAB_SHARED_BACKEND_URL": f"http://127.0.0.1:{PERPLEXITY_SHARED_BACKEND_PORT}",
    }
    web_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(PERPLEXITY_CLONE_ROOT),
        env=web_env,
    )
    children.append(web_proc)

    backend_ready = _wait_for_url(f"http://127.0.0.1:{PERPLEXITY_SHARED_BACKEND_PORT}/health", timeout_seconds=60)
    web_ready = _wait_for_url(f"http://127.0.0.1:{PERPLEXITY_WEB_PORT}", timeout_seconds=120)
    if not backend_ready:
        raise RuntimeError("Perplexity shared backend did not become ready")
    if not web_ready:
        raise RuntimeError("Perplexity clone web did not become ready")

    logging.info("[Main] Perplexity backend URL: http://127.0.0.1:%s", PERPLEXITY_SHARED_BACKEND_PORT)
    logging.info("[Main] Perplexity clone local URL: http://127.0.0.1:%s", PERPLEXITY_WEB_PORT)
    codespace_name = _resolve_codespace_name()
    if codespace_name:
        public_url = f"https://{codespace_name}-{PERPLEXITY_WEB_PORT}.app.github.dev"
        tg_uid = os.getenv("TELEGRAM_TEST_CHAT_ID", "").strip()
        if tg_uid:
            logging.info("[Main] Perplexity clone URL: %s/?uid=%s", public_url, tg_uid)
        else:
            logging.info("[Main] Perplexity clone URL: %s", public_url)

    return children


def _stop_services(children: list[subprocess.Popen]) -> None:
    for proc in children:
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
    time.sleep(2)
    for proc in children:
        if proc and proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass


def _resolve_codespace_name() -> str | None:
    """Resolve codespace name without interactive gh prompts."""
    name_from_env = os.getenv("CODESPACE_NAME")
    if name_from_env:
        return name_from_env

    webhook_url = os.getenv("TELEGRAM_WEBHOOK_CODESPACE", "").strip()
    if webhook_url:
        try:
            host = (urlparse(webhook_url).hostname or "").strip()
            # Before example: no CODESPACE_NAME -> gh tried interactive selection and failed in non-tty.
            # After example:  derive "ominous-halibut-... " from webhook host and call gh with -c directly.
            if host.endswith(".app.github.dev"):
                subdomain = host[: -len(".app.github.dev")]
                dash_port = f"-{PORT_NUMBER}"
                if subdomain.endswith(dash_port):
                    candidate = subdomain[: -len(dash_port)]
                    if candidate:
                        return candidate
        except Exception:
            pass

    try:
        result = subprocess.run(
            ["gh", "codespace", "list", "--json", "name", "--limit", "1"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        raw = (result.stdout or "").strip()
        if raw.startswith("[") and '"name"' in raw:
            # Keep this parser intentionally simple to avoid extra dependencies.
            marker = '"name":"'
            start = raw.find(marker)
            if start != -1:
                start += len(marker)
                end = raw.find('"', start)
                if end != -1:
                    return raw[start:end]
    except Exception:
        pass

    return None


def _run_port_visibility_command(port: str, codespace_name: str | None, timeout_seconds: int = 10):
    """Run one gh visibility command, optionally with explicit codespace name."""
    cmd = ["gh", "codespace", "ports", "visibility", f"{port}:public"]
    if codespace_name:
        cmd.extend(["-c", codespace_name])
    return subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )


def _set_codespaces_port_public(port: str, timeout_seconds: int = 10) -> tuple[bool, str]:
    """Try once to set a Codespaces forwarded port visibility to public."""
    codespace_name = _resolve_codespace_name()
    if not codespace_name:
        return False, "codespace_name_missing"

    try:
        result = _run_port_visibility_command(port, codespace_name, timeout_seconds=timeout_seconds)
        stdout = (result.stdout or "").strip()
        if stdout:
            logging.info("[Main] Port %s visibility command output: %s", port, stdout)
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        error_message = (
            f"exit={exc.returncode}, target={codespace_name}, stdout={stdout or '<empty>'}, stderr={stderr or '<empty>'}"
        )
        return False, error_message
    except FileNotFoundError:
        return False, "gh_cli_missing"
    except Exception as exc:
        return False, f"unexpected_error={exc}"


def setup_port_forwarding():
    """Keep Codespaces ports public and re-apply periodically."""
    if os.getenv("CODESPACES") != "true":
        logging.info("[Main] Not running in Codespaces, skipping port setup")
        return

    # Before example: startup might run before the forwarded port exists -> 404 Not Found once.
    # After example:  we retry for a while, then keep re-applying visibility every 5 minutes.
    def _keep_codespaces_port_public(port: str):
        last_error_message = ""
        for attempt in range(1, 31):
            success, error_message = _set_codespaces_port_public(port)
            if success:
                logging.info("[Main] Port %s set to public (attempt %s).", port, attempt)
                break
            # Deduplicate repeated startup warnings so logs stay readable.
            if error_message and error_message != last_error_message:
                if "404 Not Found" in error_message or "port_not_ready" in error_message:
                    logging.info("[Main] Port %s not ready yet (%s). Retrying...", port, error_message)
                elif error_message == "gh_cli_missing":
                    logging.warning("[Main] gh CLI not found, skipping port setup.")
                    return
                elif error_message == "codespace_name_missing":
                    logging.warning("[Main] Could not resolve codespace name; skipping port setup.")
                    return
                else:
                    logging.warning("[Main] Could not set port %s public (%s)", port, error_message)
                last_error_message = error_message
            time.sleep(min(2 * attempt, 15))

        while True:
            time.sleep(300)
            success, error_message = _set_codespaces_port_public(port)
            if not success and error_message and error_message != last_error_message:
                logging.warning("[Main] Keepalive could not confirm public port %s (%s)", port, error_message)
                last_error_message = error_message
            elif success:
                last_error_message = ""

    ports: list[str] = []
    transport = os.getenv("TELEGRAM_CODESPACES_TRANSPORT", "polling").strip().lower()
    # Before example: polling mode still tried to publish 8080 and produced noisy 404 warnings.
    # After example:  only publish webhook port when webhook transport is explicitly enabled.
    if transport == "webhook":
        ports.append(str(PORT_NUMBER))
    if ENABLE_PERPLEXITY_CLONE and PERPLEXITY_WEB_PORT not in ports:
        ports.append(PERPLEXITY_WEB_PORT)
    if not ports:
        logging.info("[Main] No Codespaces ports requested for public visibility.")
        return
    for port in ports:
        Thread(target=_keep_codespaces_port_public, args=(port,), daemon=True).start()
    logging.info("[Main] Started Codespaces port visibility keepalive for ports: %s", ",".join(ports))

def main():
    logging.info("[Main] Starting up...")
    logging.info(f"[Main] BUILD_TAG={os.getenv('BUILD_TAG', 'unknown')}")
    _align_port_with_codespaces_webhook()
    _reset_test_user_session_if_configured()

    setup_port_forwarding()
    child_services: list[subprocess.Popen] = []
    try:
        child_services = _start_perplexity_clone_services()
    except Exception as exc:
        # Keep Cloud Run bot service alive even if optional local UI stack cannot boot.
        logging.error(f"[Main] Perplexity clone startup failed: {exc}")
        logging.warning("[Main] Continuing without Perplexity clone services.")
        _stop_services(child_services)
        child_services = []

    # We rely on run_bot() for everything.
    # If environment=development => polling
    # If environment=production  => webhook
    try:
        run_bot_webhook_set()
    except KeyboardInterrupt:
        logging.info("[Main] Shutdown requested (KeyboardInterrupt).")
    except Exception as e:
        logging.error(f"[Main] Telegram bot error: {e}\n{traceback.format_exc()}")
    finally:
        _stop_services(child_services)
        logging.info("[Main] Exiting gracefully...")




if __name__ == "__main__":
    #signal.signal(signal.SIGTERM, handle_sigterm)
    main()



def misc():
    # --------------------------------------------------------------------
    # import logging
    # import sys
    # import os
    # import signal
    # import traceback
    # from flask import Flask
    # from threading import Thread

    # from telegram_bot import run_bot  # We'll make sure this is a normal function now

    # # --------------------------------------------------------------------
    # # Logging Configuration
    # # --------------------------------------------------------------------
    # logging.basicConfig(
    #     level=logging.DEBUG,
    #     format="%(asctime)s - %(levelname)s - %(message)s",
    #     handlers=[logging.StreamHandler(sys.stdout)]
    # )

    # # --------------------------------------------------------------------
    # # Flask App (for Cloud Run health checks, etc.)
    # # --------------------------------------------------------------------
    # app = Flask(__name__)

    # @app.route("/health")
    # def health_check():
    #     """Health check endpoint for Google Cloud Run."""
    #     return {"status": "running"}, 200

    # @app.route("/")
    # def home():
    #     """Root endpoint."""
    #     return "Telegram Bot is running!"

    # def run_flask():
    #     """Run Flask in the background on Cloud Run's port 8080."""
    #     app.run(host="0.0.0.0", port=8080, debug=False)

    # # --------------------------------------------------------------------
    # # Graceful Shutdown Handler
    # # --------------------------------------------------------------------
    # def handle_sigterm(*_):
    #     """
    #     Handle SIGTERM for graceful shutdown.
    #     (Cloud Run sends SIGTERM before shutting down the container.)
    #     """
    #     logging.info("[Signal Handler] Received SIGTERM. Shutting down gracefully...")
    #     # Exit immediately or do any cleanup if needed
    #     sys.exit(0)

    # # --------------------------------------------------------------------
    # # Main Entrypoint
    # # --------------------------------------------------------------------
    # def main():
    #     logging.info("[Main] Starting new deployment...")

    #     # 1. Start the Flask server in a background thread
    #     flask_thread = Thread(target=run_flask, daemon=True)
    #     flask_thread.start()
    #     logging.info("[Main] Flask server started on port 8080.")

    #     # 2. Run the Telegram bot in polling mode (synchronous call)
    #     try:
    #         logging.info("[Main] Starting Telegram bot with polling...")
    #         run_bot()  # <--- Normal function call, blocks until polling stops
    #         logging.info("[Main] Telegram bot has stopped.")
    #     except KeyboardInterrupt:
    #         logging.info("[Main] Shutdown requested (KeyboardInterrupt).")
    #     except Exception as e:
    #         logging.error(
    #             f"[Main] Telegram bot encountered an error: {e}\n{traceback.format_exc()}"
    #         )
    #     finally:
    #         logging.info("[Main] Exiting gracefully...")

    # # --------------------------------------------------------------------
    # # Script Execution
    # # --------------------------------------------------------------------
    # if __name__ == "__main__":
    #     signal.signal(signal.SIGTERM, handle_sigterm)
    #     main()
    # def handle_sigterm(*_):
    #     logging.info("Received SIGTERM, shutting down gracefully...")
    #     sys.exit(0)


    # app = Flask(__name__)

    # Optional health endpoint (only truly useful if you keep Flask running)
    # @app.route("/health")
    # def health_check():
    #     return {"status": "running"}, 200
    pass
