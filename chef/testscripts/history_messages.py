import os
from datetime import datetime
import json
import os

LOGS_DIR = "chat_history_logs" # Directory to store the text files

from datetime import datetime, timezone

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

def message_history_process(message_object: dict, message_to_append_history=None) -> dict:
    import json
    user_id = str(message_object.get('user_id', 'unknown'))
    filepath = os.path.join(LOGS_DIR, f"{user_id}_history.json")

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

    # Remove or stringify non-serializable fields from message_to_append_history
    def make_json_safe(obj):
        try:
            json.dumps(obj)
            return obj
        except (TypeError, OverflowError):
            return str(obj)

    if message_to_append_history:
        safe_message = {k: make_json_safe(v) for k, v in message_to_append_history.items()}
        data["messages"].append(safe_message)
        data["user_message"] = safe_message.get("content", "")

    # Save the updated object back to the file
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

    return data

def archive_message_history(message_object: dict, user_id: str) -> None:
    """
    Archives the full message object to a file.
    """
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