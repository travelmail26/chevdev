import os
import json
import importlib.util

LOGS_DIR = os.path.join(os.path.dirname(__file__), "chat_history_logs") # Directory relative to utilities folder

from datetime import datetime, timezone

DEFAULT_DB_NAME = "chef_dietlog"
DEFAULT_COLLECTION_NAME = "chat_dietlog_sessions"
_mongo_collection = None
_bot_config_module = None


def _get_bot_config_module():
    # Before example: no shared config; After: load central bot_config.py once.
    global _bot_config_module
    if _bot_config_module is not None:
        return _bot_config_module
    base_dir = os.path.dirname(os.path.abspath(__file__))
    chef_root = os.path.dirname(os.path.dirname(base_dir))
    config_path = os.path.join(chef_root, "utilities", "bot_config.py")
    if not os.path.exists(config_path):
        return None
    try:
        spec = importlib.util.spec_from_file_location("bot_config", config_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _bot_config_module = module
    except Exception:
        _bot_config_module = None
    return _bot_config_module


def _normalize_bot_mode(mode: str | None) -> str:
    # Before example: "ChefDietLog" -> "chefdietlog"; After: "ChefDietLog" -> "dietlog".
    module = _get_bot_config_module()
    if module and hasattr(module, "normalize_bot_mode"):
        return module.normalize_bot_mode(mode)
    raw = (mode or "").strip().lower()
    return raw or "dietlog"


def _get_bot_config(mode: str | None) -> dict:
    # Before example: hard-coded defaults; After: pull from bot_config.py when present.
    module = _get_bot_config_module()
    if module and hasattr(module, "get_bot_config"):
        return module.get_bot_config(mode)
    return {
        "mongo_db": os.environ.get("MONGODB_DB_NAME", DEFAULT_DB_NAME),
        "mongo_collection": os.environ.get("MONGODB_COLLECTION_NAME", DEFAULT_COLLECTION_NAME),
    }


def _get_default_bot_mode() -> str:
    # Before example: BOT_MODE unset -> derived folder name; After: normalized fallback.
    mode = os.environ.get("BOT_MODE")
    if mode:
        return _normalize_bot_mode(mode)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return _normalize_bot_mode(os.path.basename(os.path.dirname(base_dir)))


def _get_mongo_collection():
    global _mongo_collection
    if _mongo_collection is not None:
        return _mongo_collection
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        return None
    try:
        from pymongo import MongoClient
    except Exception:
        return None
    client = MongoClient(uri)
    config = _get_bot_config(_get_default_bot_mode())
    database_name = config.get("mongo_db", DEFAULT_DB_NAME)
    collection_name = config.get("mongo_collection", DEFAULT_COLLECTION_NAME)
    _mongo_collection = client[database_name][collection_name]
    return _mongo_collection


def _get_mongo_history(user_id: str):
    collection = _get_mongo_collection()
    if collection is None:
        return None
    return collection.find_one(
        {"user_id": user_id},
        sort=[("last_updated_at", -1)],
    )


def _upsert_mongo_history(user_id: str, message_object: dict, safe_message: dict | None):
    collection = _get_mongo_collection()
    if collection is None:
        return None

    bot_mode = _get_default_bot_mode()
    now = datetime.now(timezone.utc).isoformat()
    session_seed = add_chat_session_keys({"user_id": user_id})

    # Before: file read/write each turn. After: Mongo upsert returns the latest doc.
    update_doc = {
        "$set": {
            "user_id": user_id,
            "bot_mode": _normalize_bot_mode(bot_mode),
            "last_updated_at": now,
        },
        "$setOnInsert": {
            "_id": session_seed["chat_session_id"],
            "chat_session_id": session_seed["chat_session_id"],
            "chat_session_created_at": session_seed["chat_session_created_at"],
        },
    }

    session_info = message_object.get("session_info") if isinstance(message_object, dict) else None
    if isinstance(session_info, dict):
        update_doc["$setOnInsert"]["session_info"] = session_info

    if safe_message is None:
        # Before: $setOnInsert + $push on "messages" conflicted; After: only seed when no push.
        update_doc["$setOnInsert"]["messages"] = session_seed["messages"]

    if safe_message:
        update_doc["$push"] = {"messages": safe_message}
        update_doc["$set"]["user_message"] = safe_message.get("content", "")

    try:
        from pymongo import ReturnDocument
    except Exception:
        ReturnDocument = None

    if ReturnDocument:
        return collection.find_one_and_update(
            {"user_id": user_id},
            update_doc,
            upsert=True,
            return_document=ReturnDocument.AFTER,
            sort=[("last_updated_at", -1)],
        )

    collection.update_one(
        {"user_id": user_id},
        update_doc,
        upsert=True,
    )
    return _get_mongo_history(user_id)


def _load_mongo_helper():
    try:
        # Before example: imports pointed at chef/testscripts/simple_mongo_dump.py.
        # After example: import resolves to chefdietlog/utilities/simple_mongo_dump.py.
        from utilities.simple_mongo_dump import save_chat_session_to_mongo as helper
        return helper
    except Exception:
        try:
            from simple_mongo_dump import save_chat_session_to_mongo as helper
            return helper
        except Exception:
            return None
    return None


save_chat_session_to_mongo = None


def _ensure_mongo_helper():
    global save_chat_session_to_mongo
    if save_chat_session_to_mongo is None:
        save_chat_session_to_mongo = _load_mongo_helper()
    return save_chat_session_to_mongo

def add_chat_session_keys(session_info: dict) -> dict:
    """Adds session_id, session_created_at, and messages keys to a copy of session_info."""

    # 1. Create the new data
    new_data = {
        "chat_session_id": f"{session_info.get('user_id', 'user')}_{datetime.now(timezone.utc).strftime('%d%m%Y_%H%M%S_%f')}",
        "chat_session_created_at": datetime.now(timezone.utc).isoformat(),
        "messages": [{"role": "system", "content": ""}] # Initial neutral message list
    }

    # 2. Combine by updating a copy of session_info
    combined_structure = session_info.copy() # Start with a copy of original data
    combined_structure.update(new_data)     # Add the new keys/values

    return combined_structure

def create_session_log_file(user_id: str) -> str | None:
    print(f"Creating session log file for user_id: {user_id}")
    """
    Creates a new, empty text file named using the user_id and timestamp.

    Args:
        user_id: The identifier for the user.

    Returns:
        The full filepath of the created text file, or None if an error occurred.
    """
    if _get_mongo_collection() is not None:
        # Before example: wrote chat_history_logs/<user>.json; After: Mongo mode skips local files.
        return None
    # 1. Ensure the directory exists
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
    except OSError as e:
        print(f"ERROR: Could not create directory '{LOGS_DIR}': {e}")
        return None

    # 2. Create the unique filename
    
    filename = f"{user_id}_history.json" # Simple .txt file

    # 3. Get the full path
    filepath = os.path.join(LOGS_DIR, filename)

    # 4. Create the empty file
    try:
        # Open in 'w' mode creates the file. The 'with' block immediately closes it,
        # leaving it empty.
        with open(filepath, 'w') as f:
            pass # Do nothing, just create the file
        print(f"SUCCESS: Created empty log file: {filepath}")
        return filepath
    except IOError as e:
        print(f"ERROR: Could not create file '{filepath}': {e}")
        return None


def _sync_history_to_mongo(user_id: str):
    helper = _ensure_mongo_helper()
    if not user_id or not os.environ.get("MONGODB_URI") or not callable(helper):
        return
    # Before: history writes stopped at chat_history_logs/<user>.json.
    # After: with os.environ["MONGODB_URI"] = "mongodb+srv://example/chef", the same write mirrors to MongoDB.
    try:
        helper(str(user_id))
    except Exception as exc:
        print(f"WARNING: Mongo sync skipped for user {user_id}: {exc}")

def message_history_process(message_object: dict, message_to_append_history=None) -> dict:
    import json
    user_id = str(message_object.get('user_id', 'unknown'))

    # Remove or stringify non-serializable fields from message_to_append_history
    def make_json_safe(obj):
        try:
            json.dumps(obj)
            return obj
        except (TypeError, OverflowError):
            return str(obj)

    safe_message = None
    if message_to_append_history:
        safe_message = {k: make_json_safe(v) for k, v in message_to_append_history.items()}

    mongo_doc = _upsert_mongo_history(user_id, message_object, safe_message)
    if mongo_doc:
        return mongo_doc

    filepath = os.path.join(LOGS_DIR, f"{user_id}_history.json")

    # Before example: missing LOGS_DIR -> FileNotFoundError on open(); after: directory is created.
    os.makedirs(LOGS_DIR, exist_ok=True)

    # Try to load existing file, handle empty/corrupt gracefully
    data = None
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                content = f.read().strip()
                if content:
                    data = json.loads(content)
        except (json.JSONDecodeError, IOError):
            data = None
    if not data:
        # If file doesn't exist, is empty, or is corrupt, initialize with the incoming object
        if 'chat_session_id' not in message_object:
            message_object = add_chat_session_keys(message_object)
        data = message_object

    # Ensure messages list exists
    if "messages" not in data or not isinstance(data["messages"], list):
        data["messages"] = []

    # Before example: bot_mode missing -> hard to split configs; After: bot_mode="chefdietlog"/"dietlog".
    data["bot_mode"] = _get_default_bot_mode()

    if safe_message:
        data["messages"].append(safe_message)
        data["user_message"] = safe_message.get("content", "")

    # Save the updated object back to the file
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

    if message_to_append_history:
        # Before: append -> file only. After: append -> file + Mongo snapshot (when MONGODB_URI is set).
        _sync_history_to_mongo(user_id)

    return data

def archive_message_history(message_object: dict, user_id: str) -> None:
    """
    Archives the full message object to a file.
    """
    collection = _get_mongo_collection()
    if collection is not None:
        bot_mode = _get_default_bot_mode()
        now = datetime.now(timezone.utc).isoformat()
        session_id = message_object.get("chat_session_id")
        if not session_id:
            seed = add_chat_session_keys({"user_id": str(user_id)})
            session_id = seed["chat_session_id"]
            message_object.setdefault("chat_session_id", session_id)
            message_object.setdefault("chat_session_created_at", seed["chat_session_created_at"])
            message_object.setdefault("messages", seed["messages"])
        # Before example: archive -> local JSON; After: archive -> Mongo document.
        message_object["user_id"] = str(message_object.get("user_id", user_id))
        message_object["bot_mode"] = bot_mode
        message_object["_id"] = session_id
        message_object["last_updated_at"] = now
        collection.update_one({"_id": session_id}, {"$set": message_object}, upsert=True)
        return

    filepath = os.path.join(LOGS_DIR, f"{user_id}_history.json")
    try:
        with open(filepath, 'w') as f:
            json.dump(message_object, f, indent=2)
        print(f"Archived message history to {filepath} (JSON)")
    except Exception as e:
        with open(filepath, 'w') as f:
            f.write(str(message_object))
        print(f"WARNING: Could not archive as JSON, wrote as string instead. Error: {e}")

    print(f"Archived message history to {filepath}")

def get_full_history_message_object(user_id: str) -> dict:
    """Retrieve the entire message object (including all metadata and messages) for a user from their persistent history file."""
    mongo_doc = _get_mongo_history(str(user_id))
    if mongo_doc:
        return mongo_doc
    filepath = os.path.join(LOGS_DIR, f"{user_id}_history.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                return data
        except Exception as e:
            print(f"ERROR: Could not load persistent message object for user {user_id}: {e}")
    return {}

def append_message_to_history(user_id: dict) -> dict:
    """
    Appends a new message to the 'messages' list in the user's history JSON file.
    The message will have the structure: {"role": role, "content": content}
    Returns True if successful, False otherwise.
    """
    filepath = os.path.join(LOGS_DIR, f"{user_id}.txt")
    if not os.path.exists(filepath):
        print(f"ERROR: History file does not exist: {filepath}")
        return False

    try:
        with open(filepath, 'r+') as f:
            data = json.load(f)
            if "messages" not in data or not isinstance(data["messages"], list):
                data["messages"] = []
            data["messages"].append({"role": role, "content": content})
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()
        print(f"Appended message to {filepath}")
        return True
    except Exception as e:
        print(f"ERROR appending message: {e}")
        return False

# --- Test this single function ---
if __name__ == "__main__":
        # IMPORTANT: Assumes a session file for chat_id 1275000000 exists
    # in 'chat_session_files/', created by the previous step's code.
    # E.g., 'chat_session_files/1275000000_20231028_.... .json'

    test_incoming_message_object = {
        'user_id': 1275000000,
        'application': "dummy_app",
        'session_info': {
            'user_id': 1275000000, 
            'chat_id': 1275000000, 
            'message_id': 1001,
            'timestamp': 1746130241.0,
            'username': 'ferenstein',
            'first_name': '<name>',
            'last_name': '<name>'
        },
        'user_message': 'hi, this is my actual message'
    }

    print("\n--- Attempting to append message ---")
    message_history_process(test_incoming_message_object)

   

    # Check the 'chat_history_logs' directory. You should see two empty .txt files.
