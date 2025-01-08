#!/usr/bin/env python3
import os
import sys
import time
import logging
import asyncio
import nest_asyncio
from flask import Flask
from threading import Thread
from telegram_bot import run_bot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True
)

# Test environment variable
def test_env_variable():
    try:
        logging.info("Testing environment variable 'SERVICE_ACCOUNT_FILE_PH'")
        env_value = os.environ.get('SERVICE_ACCOUNT_FILE_PH', None)
        if env_value:
            logging.info(f"'SERVICE_ACCOUNT_FILE_PH': {env_value}")
        else:
            logging.warning("'SERVICE_ACCOUNT_FILE_PH' not found in environment variables")
    except Exception as e:
        logging.error(f"Error accessing 'SERVICE_ACCOUNT_FILE_PH': {e}")

# Flask application
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

# Main async function
async def main():
    logging.info("Starting Flask in a background thread...")
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    logging.info("Starting Telegram bot polling...")
    await run_bot()

# Guardrail to keep the application running
if __name__ == "__main__":
    logging.info("Starting application...")
    test_env_variable()  # Check the environment variable on startup
    try:
        nest_asyncio.apply()
        asyncio.run(main())
        while True:
            time.sleep(1)  # Keep the application running
    except Exception as e:
        logging.critical(f"Critical error in main: {e}")
        sys.exit(1)
