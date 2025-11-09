#!/usr/bin/env python3
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from telegram_bot import setup_bot

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting bot in polling mode...")

    app = setup_bot()
    logger.info("Bot setup complete, starting polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
