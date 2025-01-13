import logging
import sys
import os
import asyncio
import psutil
import nest_asyncio
from flask import Flask
from threading import Thread
from telegram_bot import run_bot  # Import run_bot from your Telegram bot script
from concurrent.futures import ThreadPoolExecutor
import signal

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Ensure logs go to stdout
    ]
)

logging.info("Starting new deployment...")

# Flask app for health checks
app = Flask(__name__)

@app.route("/health")
def health_check():
    return {"status": "polling"}, 200

@app.route("/")
def home():
    return "Telegram Bot is running!"

def run_flask():
    """Run Flask in a background thread."""
    app.run(host="0.0.0.0", port=8080, debug=False)

PID_FILE = "bot.pid"

async def monitor_logging():
    """Log a message periodically to ensure the bot is running."""
    while True:
        logging.info("from main.py: Bot is actively polling for updates...")
        await asyncio.sleep(12600)  # Approximately 3.5 hours

async def log_active_tasks():
    """Log all active tasks periodically."""
    while True:
        active_tasks = asyncio.all_tasks()
        logging.debug(f"Active tasks: {[task.get_name() for task in active_tasks]}")
        await asyncio.sleep(60)

async def main():
    """Main function to run the bot and Flask server."""
    # Run Flask server in a separate thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Start the Telegram bot in parallel
    telegram_bot_task = asyncio.create_task(run_bot())

    # Start monitoring tasks
    monitor_task = asyncio.create_task(monitor_logging())
    task_logger = asyncio.create_task(log_active_tasks())

    try:
        await telegram_bot_task  # Wait for Telegram bot task to complete
    except Exception as e:
        logging.error(f"Telegram bot encountered an error: {e}")
    finally:
        monitor_task.cancel()
        task_logger.cancel()
        try:
            await asyncio.gather(monitor_task, task_logger, return_exceptions=True)
        except asyncio.CancelledError:
            logging.info("Monitor and task logger cancelled.")

def handle_sigterm():
    """Handle SIGTERM signal for graceful shutdown."""
    logging.info("Received SIGTERM. Shutting down gracefully...")
    for task in asyncio.all_tasks():
        task.cancel()

if __name__ == "__main__":
    # Ensure the event loop allows nested usage
    nest_asyncio.apply()

    # Handle SIGTERM signal for Google Cloud Run
    signal.signal(signal.SIGTERM, lambda *_: asyncio.run(handle_sigterm()))

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Shutting down bot.")
    except Exception as e:
        logging.critical(f"Critical error in main: {e}")
