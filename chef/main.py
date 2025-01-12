#!/usr/bin/env python3
import os
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Method 1: Direct dictionary access
try:
    logging.debug('Testing direct dictionary access')
    logging.debug(os.environ['SERVICE_ACCOUNT_FILE_PH'])
    logging.debug('Direct dictionary access successful')
except KeyError:
    logging.debug('Direct dictionary access failed')

# Method 2: Using get() with default value
try:
    logging.debug('Testing get() method')
    logging.debug(os.environ.get('SERVICE_ACCOUNT_FILE_PH', 'Not found'))
    logging.debug('Get method access successful')
except Exception as e:
    logging.debug(f'Get method access failed: {str(e)}')

# Method 3: Dictionary membership test
try:
    logging.debug('Testing membership test')
    if 'SERVICE_ACCOUNT_FILE_PH' in os.environ:
        logging.debug(os.environ['SERVICE_ACCOUNT_FILE_PH'])
        logging.debug('Membership test successful')
    else:
        logging.debug('SERVICE_ACCOUNT_FILE_PH not in environment')
except Exception as e:
    logging.debug(f'Membership test failed: {str(e)}')

import asyncio
import nest_asyncio
from flask import Flask
from threading import Thread
from telegram_bot import run_bot

app = Flask(__name__)


@app.route("/health")
def health():
    return "OK"


@app.route("/")
def home():
    return "Telegram Bot is running!"


def run_flask():
    """
    Runs Flask in a background thread so we don't block
    our main asyncio event loop.
    """
    app.run(host="0.0.0.0", port=8080, debug=False)



pid_file = "bot.pid"

def check_running_instances():
    """Check for other running instances of this bot"""
    current_pid = os.getpid()
    current_script = os.path.abspath(__file__)

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['cmdline'] and current_script == proc.info['cmdline'][0]:
                if proc.pid != current_pid:
                    logging.warning(f"Found another instance running with PID: {proc.pid}")
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            logging.debug(f"Skipped a process due to: {e}")
    return False


async def main():
    logging.debug('Testing direct dictionary access')
    """
    1. Start Flask in a background thread
    2. Await the Telegram bot's polling
    """
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Now run the Telegram bot (which starts its own polling internally).
    await run_bot()




if __name__ == "__main__":
    # nest_asyncio allows you to re-enter the already running loop,
    # helpful if the library tries to handle its own event loop internally.
    
    if check_running_instances():
        logging.error("Another instance is already running. Exiting.")
        sys.exit(1)

    # Handle PID file
    if os.path.exists(pid_file):
        with open(pid_file, "r") as f:
            old_pid = int(f.read().strip())
            if psutil.pid_exists(old_pid):
                logging.error(f"Bot is already running with PID: {old_pid}. Exiting.")
                sys.exit(1)

    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

    try:
        # Ensure compatibility with nested event loops
        nest_asyncio.apply()
        asyncio.run(main())
    except Exception as e:
        logging.critical(f"Critical error in main: {e}")
    finally:
        # Clean up PID file
        if os.path.exists(pid_file):
            os.remove(pid_file)
    
    nest_asyncio.apply()

    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Critical error in main: {e}")
        # If desired, do a sys.exit(1) or just let it crash.
