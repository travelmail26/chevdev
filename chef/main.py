# main.py

import logging
import sys
import os
import signal
import traceback
#from flask import Flask
from threading import Thread

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

def main():
    logging.info("[Main] Starting up...")

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