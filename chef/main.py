
#!/usr/bin/env python3

import sys
print("Starting deployment...", flush=True)
sys.stdout.flush()
print(f"Python path: {sys.path}", flush=True)

import asyncio
import nest_asyncio
from flask import Flask
from telegram_bot import run_bot
from threading import Thread
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
sys.stdout.reconfigure(line_buffering=True)

# Allow nested event loops
nest_asyncio.apply()

# Flask app setup
app = Flask(__name__)

@app.route("/health")
def health():
    return "OK"

@app.route("/")
def home():
    return "Telegram Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=3000)

async def async_main():
    try:
        print("Starting telegram bot", flush=True)
        await run_bot()
    except Exception as e:
        print(f"Critical error in bot: {str(e)}", flush=True)
        return False
    return True

def main():
    try:
        print("Main function started", flush=True)
        
        # Start Flask thread
        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()
        print("Flask thread started", flush=True)
        
        # Run telegram bot in the main event loop
        if not asyncio.run(async_main()):
            print("Bot initialization failed", flush=True)
            return
            
    except Exception as e:
        print(f"Critical error: {str(e)}", flush=True)
    finally:
        print("Shutting down...", flush=True)

if __name__ == "__main__":
    print("Starting program...", flush=True)
    main()
