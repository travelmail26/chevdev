#!/usr/bin/env python3
"""
Minimal wrapper for recipe_bot.
"""

from __future__ import annotations

import os

import recipe_bot


def main() -> None:
    os.environ["BOT_QUESTION"] = (
        "List all the different temperatures that a user has cooked onions. "
        "List them with date, temp, and outcome if available."
    )
    recipe_bot.main()


if __name__ == "__main__":
    main()
