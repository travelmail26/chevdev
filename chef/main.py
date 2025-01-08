#!/usr/bin/env python3
import os
import sys
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True
)

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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)

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
    app.run(host="0.0.0.0", port=8080)

async def main():
    logging.debug('main function in main.py triggered')
    """
    1. Start Flask in a background thread
    2. Await the Telegram bot's polling
    """
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Now run the Telegram bot (which starts its own polling internally).
    await run_bot()

if __name__ == "__main__":
    try:
        print("Starting application...", flush=True)
        main()
        while True:
            time.sleep(1)
    except Exception as e:
        print(f"Startup error: {str(e)}", flush=True)
        sys.exit(1)
    # nest_asyncio allows you to re-enter the already running loop,
    # helpful if the library tries to handle its own event loop internally.

    nest_asyncio.apply()

    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Critical error in main: {e}")
