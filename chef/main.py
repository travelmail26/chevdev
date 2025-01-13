import logging
import sys
import os
import signal
import traceback
from flask import Flask
from threading import Thread

# Import your existing bot-startup function (now synchronous in telegram_bot.py)
from telegram_bot import run_bot  

# --------------------------------------------------------------------
# Logging Configuration
# --------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --------------------------------------------------------------------
# Flask App (for Cloud Run health checks, etc.)
# --------------------------------------------------------------------
app = Flask(__name__)

@app.route("/health")
def health_check():
    """Health check endpoint for Google Cloud Run."""
    return {"status": "running"}, 200

@app.route("/")
def home():
    """Root endpoint."""
    return "Telegram Bot is running!"

def run_flask():
    """Run Flask in the background on Cloud Run's port 8080."""
    app.run(host="0.0.0.0", port=8080, debug=False)

# --------------------------------------------------------------------
# Graceful Shutdown Handler
# --------------------------------------------------------------------
def handle_sigterm(*_):
    """
    Handle SIGTERM for graceful shutdown.
    (Cloud Run sends SIGTERM before shutting down the container.)
    """
    logging.info("[Signal Handler] Received SIGTERM. Shutting down gracefully...")
    # Exit immediately or do any cleanup if needed
    sys.exit(0)

# --------------------------------------------------------------------
# Main Entrypoint
# --------------------------------------------------------------------
def main():
    logging.info("[Main] Starting new deployment...")

    # 1. Start the Flask server in a background thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logging.info("[Main] Flask server started on port 8080.")

    # 2. Run the Telegram bot in polling mode
    #    This should block until the bot stops (synchronous).
    try:
        logging.info("[Main] Starting Telegram bot with polling...")
        run_bot()  # <--- No 'await' needed. It's synchronous now!
        logging.info("[Main] Telegram bot has stopped.")
    except KeyboardInterrupt:
        logging.info("[Main] Shutdown requested (KeyboardInterrupt).")
    except Exception as e:
        logging.error(
            f"[Main] Telegram bot encountered an error: {e}\n{traceback.format_exc()}"
        )
    finally:
        logging.info("[Main] Exiting gracefully...")

# --------------------------------------------------------------------
# Script Execution
# --------------------------------------------------------------------
if __name__ == "__main__":
    # Attach the SIGTERM handler
    signal.signal(signal.SIGTERM, handle_sigterm)
    main()
