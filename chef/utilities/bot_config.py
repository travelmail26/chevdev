import os


CHEF_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def normalize_bot_mode(mode: str | None) -> str:
    # Before example: "ChefMain" -> "cheflog"; After: "dietlog" stays "dietlog".
    raw = (mode or "").strip().lower()
    # Before example: "/cook" stored as "cook" -> unknown; After example: "cook" -> "cheflog".
    if raw in ("chef", "chefmain", "cheflog", "main", "cook"):
        return "cheflog"
    # Before example: "/log" stored as "log" -> unknown; After example: "log" -> "dietlog".
    if raw in ("diet", "dietlog", "chefdietlog", "log"):
        return "dietlog"
    # Before example: "Nano" -> unknown; After example: "Nano" -> "nano".
    if raw in ("nano", "chefnano", "recipe"):
        return "nano"
    # Before example: "/general" stored as "general" -> unknown; After example: "general" -> "general".
    if raw in ("general", "brainstorm", "chat_general"):
        return "general"
    return "cheflog"


BOT_CONFIG = {
    "cheflog": {
        # Before: path scattered in code; After: single source of truth here.
        "instructions_path": os.path.join(
            CHEF_ROOT, "chefmain", "utilities", "instructions", "instructions_base.txt"
        ),
        # Example: cheflog -> chef_chatbot.chat_sessions.
        "mongo_db": os.environ.get("MONGODB_DB_NAME", "chef_chatbot"),
        "mongo_collection": os.environ.get("MONGODB_COLLECTION_NAME", "chat_sessions"),
    },
    "dietlog": {
        # Before: path scattered in code; After: single source of truth here.
        "instructions_path": os.path.join(
            CHEF_ROOT, "chefdietlog", "utilities", "instructions", "instructions_base.txt"
        ),
        # Example: dietlog -> chef_dietlog.chat_dietlog_sessions.
        "mongo_db": os.environ.get("MONGODB_DB_NAME_DIETLOG", "chef_dietlog"),
        "mongo_collection": os.environ.get(
            "MONGODB_COLLECTION_NAME_DIETLOG", "chat_dietlog_sessions"
        ),
    },
    "nano": {
        # Before: nano had no entry; After: nano uses its own instructions + recipe DB.
        "instructions_path": os.path.join(
            CHEF_ROOT, "chefnano", "utilities", "instructions", "instructions_base.txt"
        ),
        # Example: nano -> recipe.recipe_chats.
        "mongo_db": os.environ.get("MONGODB_DB_NAME_RECIPE", "recipe"),
        "mongo_collection": os.environ.get("MONGODB_COLLECTION_NAME_RECIPE", "recipe_chats"),
    },
    "general": {
        # Before: no dedicated general prompt; After: /general uses a brainstorming instruction file.
        "instructions_path": os.path.join(
            CHEF_ROOT, "chefmain", "utilities", "instructions", "instructions_general.txt"
        ),
        # Before: general chats mixed into cheflog collection.
        # After:  general chats route to chat_general.* by default.
        "mongo_db": os.environ.get("MONGODB_DB_NAME_GENERAL", "chat_general"),
        "mongo_collection": os.environ.get("MONGODB_COLLECTION_NAME_GENERAL", "chat_general"),
    },
}


def get_bot_config(mode: str | None) -> dict:
    # Before example: unknown -> used scattered defaults; After: falls back to "cheflog".
    normalized = normalize_bot_mode(mode)
    return BOT_CONFIG.get(normalized, BOT_CONFIG["cheflog"])


def get_bot_instructions_path(mode: str | None) -> str:
    # Before example: hard-coded path; After: centralized in BOT_CONFIG.
    return get_bot_config(mode)["instructions_path"]


def get_mode_store_config() -> dict:
    # Before example: mode storage implicit; After: explicit DB/collection here.
    return {
        "mongo_db": os.environ.get(
            "MONGODB_MODE_DB_NAME", os.environ.get("MONGODB_DB_NAME", "chef_chatbot")
        ),
        "mongo_collection": os.environ.get(
            "MONGODB_MODE_COLLECTION_NAME", "bot_modes"
        ),
    }
