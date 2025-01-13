import logging
import sys
import os
import asyncio
import psutil
import nest_asyncio
from flask import Flask
from threading import Thread
from telegram_bot import run_bot  # Import run_bot from your Telegram bot script

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Ensure logs go to stdout
    ]
)

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


async def log_out_bot():
    """Log out all active Telegram bot sessions."""
    token = os.getenv("TELEGRAM_KEY") or os.getenv("TELEGRAM_DEV_KEY")
    if not token:
        logging.error("No Telegram token found in environment variables. Exiting.")
        sys.exit(1)


def terminate_other_instances():
    """Terminate any other running instances of this bot."""
    current_pid = os.getpid()
    current_script = os.path.abspath(__file__)
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            if proc.info['cmdline'] and current_script in proc.info['cmdline'][0]:
                if proc.pid != current_pid:
                    logging.warning(f"Terminating another instance of the bot with PID: {proc.pid}")
                    proc.terminate()
                    proc.wait(timeout=5)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass


def handle_pid_file():
    """Create and manage the PID file."""
    if os.path.exists(PID_FILE):
        with open(PID_FILE, "r") as f:
            old_pid = int(f.read().strip())
            if psutil.pid_exists(old_pid):
                proc = psutil.Process(old_pid)
                proc.terminate()
                proc.wait(timeout=5)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


async def monitor_logging():
    """Log a message every 5 seconds to ensure the bot is running."""
    while True:
        logging.info("Bot is actively polling for updates...")
        await asyncio.sleep(5)


async def main():
    """Main function to run the bot and Flask server."""
    ### Terminate other instances
    #terminate_other_instances()

    ### Handle PID file
    #handle_pid_file()

    # Run Flask server in a separate thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Start the Telegram bot in parallel
    telegram_bot_task = asyncio.create_task(run_bot())

    # Start the monitoring task
    monitor_task = asyncio.create_task(monitor_logging())

    try:
        await telegram_bot_task  # Wait for Telegram bot task to complete
    except Exception as e:
        logging.error(f"Telegram bot encountered an error: {e}")
    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            logging.info("Monitor task cancelled.")


if __name__ == "__main__":
    nest_asyncio.apply()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Shutting down bot.")
    except Exception as e:
        logging.critical(f"Critical error in main: {e}")
