import logging
import sys
import os

# Keep dev-only runner separate to avoid changing production behavior
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from telegram_bot import setup_bot


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting bot in polling mode...")
    os.environ.setdefault("ENVIRONMENT", "development")
    app = setup_bot()
    logger.info("Bot setup complete, starting polling...")
    app.run_polling()
    logger.info("Polling started successfully")


if __name__ == "__main__":
    main()

