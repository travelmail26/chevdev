#!/usr/bin/env python3
"""
Test script for streaming responses in Telegram bot.
This script runs the bot in polling mode and monitors the streaming behavior.
"""

import logging
import sys
import os

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'chefmain'))

from telegram_bot import setup_bot

def main():
    """Run the Telegram bot with streaming enabled in polling mode for testing"""

    # Configure detailed logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('/workspaces/chevdev/chef/testscripts/streaming_test.log')
        ]
    )

    logger = logging.getLogger(__name__)

    # Silence verbose libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logger.info("=" * 60)
    logger.info("STREAMING TEST MODE")
    logger.info("=" * 60)
    logger.info("Testing features:")
    logger.info("  1. Immediate acknowledgment (✓)")
    logger.info("  2. 'Thinking...' messages every 5 seconds")
    logger.info("  3. Streaming responses in 300-char chunks")
    logger.info("  4. MongoDB saves full message (not chunks)")
    logger.info("=" * 60)

    # Set environment to development for polling mode
    os.environ.setdefault("ENVIRONMENT", "development")

    # Setup and run the bot
    logger.info("Setting up Telegram bot...")
    app = setup_bot()

    logger.info("Bot setup complete!")
    logger.info("Starting polling mode...")
    logger.info("Send a message to your bot to test streaming!")
    logger.info("Press Ctrl+C to stop the bot")
    logger.info("=" * 60)

    try:
        app.run_polling(allowed_updates=['message'])
    except KeyboardInterrupt:
        logger.info("\nBot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}", exc_info=True)
    finally:
        logger.info("Test complete!")


if __name__ == "__main__":
    main()
