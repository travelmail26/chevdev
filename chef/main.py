#!/usr/bin/env python3
import os
import sys
import logging
import psutil
import asyncio
import nest_asyncio
from flask import Flask
from threading import Thread
from telegram import Bot
from telegram.error import TelegramError

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Flask app for health checks
app = Flask(__name__)

@app.route("/health")
def health():
    return "OK"

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

    try:
        bot = Bot(token)
        logging.info("Logging out all active bot sessions...")
        await bot.log_out()  # Await the coroutine
        logging.info("Successfully logged out all active bot sessions.")
    except TelegramError as e:
        logging.error(f"Failed to log out bot: {e}")

def terminate_other_instances():
    """Terminate any other running instances of this bot."""
    current_pid = os.getpid()
    current_script = os.path.abspath(__file__)
    terminated = False

    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            if proc.info['cmdline'] and current_script in proc.info['cmdline'][0]:
                if proc.pid != current_pid:
                    logging.warning(f"Terminating another instance of the bot with PID: {proc.pid}")
                    proc.terminate()  # Send SIGTERM
                    proc.wait(timeout=5)  # Wait for the process to terminate
                    terminated = True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            logging.debug(f"Error while processing another instance: {e}")

    if terminated:
        logging.info("Terminated all other running instances of the bot.")
    else:
        logging.info("No other running instances found.")

def handle_pid_file():
    """Create and manage the PID file."""
    if os.path.exists(PID_FILE):
        with open(PID_FILE, "r") as f:
            old_pid = int(f.read().strip())
            if psutil.pid_exists(old_pid):
                logging.warning(f"Terminating stale process with PID: {old_pid}")
                proc = psutil.Process(old_pid)
                proc.terminate()
                proc.wait(timeout=5)

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

def cleanup_pid_file():
    """Remove the PID file on shutdown."""
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)

async def main():
    """Main function to run the bot."""
    # Log out active bot sessions
    await log_out_bot()

    # Terminate other instances
    terminate_other_instances()

    # Handle PID file
    handle_pid_file()

    # Run Flask server
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    try:
        logging.info("Bot is running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(3600)  # Keep the loop alive indefinitely
    except KeyboardInterrupt:
        logging.info("Shutting down bot...")# Placeholder for actual bot logic

if __name__ == "__main__":
    # Apply nest_asyncio for re-entrant event loops
    nest_asyncio.apply()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Shutting down bot.")
    except Exception as e:
        logging.critical(f"Critical error in main: {e}")
    finally:
        cleanup_pid_file()

    
