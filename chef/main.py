import logging
import sys
import os
import asyncio
import nest_asyncio
from flask import Flask
from threading import Thread
from telegram_bot import run_bot
import signal
import traceback

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
    return {"status": "polling"}, 200

@app.route("/")
def home():
    return "Telegram Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=8080, debug=False)

async def monitor_logging():
    try:
        while True:
            logging.info("from main.py: Bot is actively polling for updates...")
            await asyncio.sleep(300)
    except asyncio.CancelledError:
        logging.info("Monitor logging task was cancelled.")
    except Exception as e:
        logging.error(f"Error in monitor_logging: {e}\n{traceback.format_exc()}")

async def log_active_tasks():
    try:
        while True:
            active_tasks = asyncio.all_tasks()
            task_details = [
                {"name": task.get_name(), "status": task._state, "is_done": task.done()}
                for task in active_tasks
            ]
            logging.debug(f"Active tasks: {task_details}")
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        logging.info("Active task logger was cancelled.")
    except Exception as e:
        logging.error(f"Error in log_active_tasks: {e}\n{traceback.format_exc()}")

async def main():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    telegram_bot_task = asyncio.create_task(run_bot(), name="TelegramBotTask")
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

        # Flush logs
        logging.info("Finalizing shutdown. Flushing logs...")
        for handler in logging.getLogger().handlers:
            handler.flush()

def handle_sigterm(signal_received, frame):
    logging.info("Received SIGTERM. Attempting graceful shutdown...")
    for task in asyncio.all_tasks():
        if not task.done():
            logging.debug(f"Cancelling task: {task.get_name()}")
            task.cancel()

if __name__ == "__main__":
    nest_asyncio.apply()
    signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        logging.info("Starting the application...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Shutting down bot (KeyboardInterrupt).")
    except Exception as e:
        logging.critical(f"Critical error in main: {e}\n{traceback.format_exc()}")
