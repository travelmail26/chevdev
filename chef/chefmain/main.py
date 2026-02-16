# main.py

import logging
import sys
import os
import signal
import traceback
import subprocess
import time
from urllib.parse import urlparse
from threading import Thread

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telegram_bot import run_bot_webhook_set

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
    """Keep Codespaces port 8080 public and re-apply periodically."""
    if os.getenv("CODESPACES") != "true":
        logging.info("[Main] Not running in Codespaces, skipping port setup")
        return

    # Before example: startup might run before the forwarded port exists -> 404 Not Found once.
    # After example:  we retry for a while, then keep re-applying visibility every 5 minutes.
    def _keep_codespaces_port_public():
        last_error_message = ""
        for attempt in range(1, 31):
            success, error_message = _set_codespaces_port_public(PORT_NUMBER)
            if success:
                logging.info("[Main] Port %s set to public (attempt %s).", PORT_NUMBER, attempt)
                break
            # Deduplicate repeated startup warnings so logs stay readable.
            if error_message and error_message != last_error_message:
                if "404 Not Found" in error_message or "port_not_ready" in error_message:
                    logging.info("[Main] Port %s not ready yet (%s). Retrying...", PORT_NUMBER, error_message)
                elif error_message == "gh_cli_missing":
                    logging.warning("[Main] gh CLI not found, skipping port setup.")
                    return
                elif error_message == "codespace_name_missing":
                    logging.warning("[Main] Could not resolve codespace name; skipping port setup.")
                    return
                else:
                    logging.warning("[Main] Could not set port %s public (%s)", PORT_NUMBER, error_message)
                last_error_message = error_message
            time.sleep(min(2 * attempt, 15))

        while True:
            time.sleep(300)
            success, error_message = _set_codespaces_port_public(PORT_NUMBER)
            if not success and error_message and error_message != last_error_message:
                logging.warning("[Main] Keepalive could not confirm public port %s (%s)", PORT_NUMBER, error_message)
                last_error_message = error_message
            elif success:
                last_error_message = ""

    Thread(target=_keep_codespaces_port_public, daemon=True).start()
    logging.info("[Main] Started Codespaces port visibility keepalive for port %s.", PORT_NUMBER)

def main():
    logging.info("[Main] Starting up...")
    logging.info(f"[Main] BUILD_TAG={os.getenv('BUILD_TAG', 'unknown')}")

    setup_port_forwarding()



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
