import logging
import sys
import os
import asyncio
import signal
import traceback
from flask import Flask
from threading import Thread
from telegram_bot import run_bot  # Your bot's main function

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logging.info("Starting new deployment...")

# Flask app for health checks
app = Flask(__name__)

@app.route("/health")
def health_check():
    """Health check endpoint for Google Cloud Run."""
    return {"status": "polling"}, 200

@app.route("/")
def home():
    """Root endpoint."""
    return "Telegram Bot is running!"

def run_flask():
    """Run Flask in a background thread."""
    app.run(host="0.0.0.0", port=8080, debug=False)

async def monitor_logging():
    """Logs periodically to ensure the bot is running."""
    while True:
        logging.info("[Monitor] Bot is actively polling for updates...")
        await asyncio.sleep(300)  # Log every 5 minutes

async def log_active_tasks():
    """Logs active tasks periodically."""
    while True:
        active_tasks = asyncio.all_tasks()
        logging.debug(f"[Task Logger] Active tasks: {[task.get_name() for task in active_tasks]}")
        await asyncio.sleep(60)

async def main():
    """Main function to start Flask and Telegram bot."""
    logging.info("[Main] Starting services...")

    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logging.info("[Main] Flask server started.")

    # Start Telegram bot and monitoring tasks
    telegram_bot_task = asyncio.create_task(run_bot(), name="TelegramBotTask")
    monitor_task = asyncio.create_task(monitor_logging(), name="MonitorLoggingTask")
    task_logger_task = asyncio.create_task(log_active_tasks(), name="TaskLoggerTask")

    # Wait for Telegram bot to complete
    try:
        await telegram_bot_task
    except Exception as e:
        logging.error(f"[Main] Telegram bot encountered an error: {e}\n{traceback.format_exc()}")
    finally:
        # Cancel monitoring tasks
        monitor_task.cancel()
        task_logger_task.cancel()
        await asyncio.gather(monitor_task, task_logger_task, return_exceptions=True)
        logging.info("[Main] Monitoring tasks cancelled. Exiting gracefully.")

def handle_sigterm():
    """Handle SIGTERM signal for graceful shutdown."""
    logging.info("[Signal Handler] Received SIGTERM. Shutting down gracefully...")
    for task in asyncio.all_tasks():
        task.cancel()

if __name__ == "__main__":
    # Apply SIGTERM handler
    signal.signal(signal.SIGTERM, lambda *_: asyncio.run_coroutine_threadsafe(handle_sigterm(), asyncio.get_event_loop()))

    # Use an explicit event loop
    loop = asyncio.get_event_loop()

    try:
        logging.info("[Main] Entering event loop...")
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("[Main] Shutdown requested (KeyboardInterrupt).")
    except Exception as e:
        logging.critical(f"[Main] Critical error: {e}\n{traceback.format_exc()}")
    finally:
        logging.info("[Main] Finalizing shutdown...")
        loop.close()
