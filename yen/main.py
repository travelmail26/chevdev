"""
LLM NOTE:
Entrypoint for the Yen bot. This file only bootstraps logging and
runs telegram_bot.run_bot_webhook_set(). Keep it small so startup is
predictable and easy to debug.
"""

import logging
import os
import sys
import traceback

# Ensure local imports resolve when running from repo root.
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from telegram_bot import run_bot_webhook_set

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def main() -> None:
    logging.info("Yen main: starting up...")
    try:
        # Before example: main did nothing; After example: it starts the Telegram bot.
        run_bot_webhook_set()
    except KeyboardInterrupt:
        logging.info("Yen main: shutdown requested (KeyboardInterrupt).")
    except Exception as exc:
        logging.error("Yen main error: %s\n%s", exc, traceback.format_exc())
    finally:
        logging.info("Yen main: exiting.")


if __name__ == "__main__":
    main()
