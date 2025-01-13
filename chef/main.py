import logging
import sys
import os
import asyncio
import psutil
import nest_asyncio
from flask import Flask
from threading import Thread
from telegram_bot import run_bot  # Import run_bot from your Telegram bot script
import signal
import traceback

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
    """Log a message periodically to ensure the bot is running."""
    try:
        while True:
            logging.info("from main.py: Bot is actively polling for updates...")
            await asyncio.sleep(300)  # Log every 5 minutes
    except asyncio.CancelledError:
        logging.info("Monitor logging task was cancelled.")
    except Exception as e:
        logging.error(f"Error in monitor_logging: {e}\n{traceback.format_exc()}")

async def log_active_tasks():
    """Log all active tasks periodically."""
    try:
        while True:
            active_tasks = asyncio.all_tasks()
            logging.debug(f"Active tasks: {[task.get_name() for task in active_tasks]}")
            await asyncio.sleep(60)  # Log every minute
    except asyncio.CancelledError:
        logging.info("Active task logger was cancelled.")
    except Exception as e:
        logging.error(f"Error in log_active_tasks: {e}\n{traceback.format_exc()}")

async def main():
    """Main function to run the bot and Flask server."""
    # Start Flask server in a separate thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Start the Telegram bot
    telegram_bot_task = asyncio.create_task(run_bot(), name="TelegramBotTask")

    # Start monitoring tasks
    monitor_task = asyncio.create_task(monitor_logging(), name="MonitorLoggingTask")
    task_logger = asyncio.create_task(log_active_tasks(), name="ActiveTaskLogger")

    try:
        logging.info("Starting main asyncio loop...")
        await telegram_bot_task
    except Exception as e:
        logging.error(f"Telegram bot encountered an error: {e}\n{traceback.format_exc()}")
    finally:
        logging.info("Shutting down tasks...")
        monitor_task.cancel()
        task_logger.cancel()
        try:
            await asyncio.gather(monitor_task, task_logger, return_exceptions=True)
        except asyncio.CancelledError:
            logging.info("Monitor and task logger tasks cancelled.")

def handle_sigterm(signal_received, frame):
    """Handle SIGTERM signal for graceful shutdown."""
    logging.info("Received SIGTERM. Shutting down gracefully...")
    for task in asyncio.all_tasks():
        task.cancel()

if __name__ == "__main__":
    # Ensure the event loop allows nested usage
    nest_asyncio.apply()

    # Handle SIGTERM signal for Google Cloud Run
    signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        logging.info("Starting the application...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Shutting down bot (KeyboardInterrupt).")
    except Exception as e:
        logging.critical(f"Critical error in main: {e}\n{traceback.format_exc()}")
