#!/usr/bin/env python3
import asyncio
import nest_asyncio
from flask import Flask
from threading import Thread
from telegram_bot import run_bot
import os

# Method 1: Direct dictionary access
try:
    print('DEBUG: Testing direct dictionary access')
    print(os.environ['SERVICE_ACCOUNT_FILE_PH'])
    print('Direct dictionary access successful')
except KeyError:
    print('DEBUG: Direct dictionary access failed')

# Method 2: Using get() with default value
try:
    print('DEBUG: Testing get() method')
    print(os.environ.get('SERVICE_ACCOUNT_FILE_PH', 'Not found'))
    print('Get method access successful')
except Exception as e:
    print('DEBUG: Get method access failed:', str(e))

# Method 3: Dictionary membership test
try:
    print('DEBUG: Testing membership test')
    if 'SERVICE_ACCOUNT_FILE_PH' in os.environ:
        print(os.environ['SERVICE_ACCOUNT_FILE_PH'])
        print('Membership test successful')
    else:
        print('SERVICE_ACCOUNT_FILE_PH not in environment')
except Exception as e:
    print('DEBUG: Membership test failed:', str(e))

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
    app.run(host="0.0.0.0", port=8080)

async def main():
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
    nest_asyncio.apply()

    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Critical error in main: {e}")
        # If desired, do a sys.exit(1) or just let it crash.
