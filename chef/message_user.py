# chef/message_user.py

import requests
import re 
import logging

# It's good practice to get a logger specific to this module
logger = logging.getLogger(__name__)



# THIS IS THE FUNCTION THAT WORKS WITH THE Application OBJECT
# def extract_token_from_application_object(application_obj):
#     """Extracts the bot token directly from the Telegram Application object."""
#     if application_obj and hasattr(application_obj, 'bot') and hasattr(application_obj.bot, 'token'):
#         return application_obj.bot.token
#     # Log an error if token extraction fails
#     logger.error("Could not extract token: Application object, its 'bot' attribute, or 'bot.token' attribute is missing or invalid.")
#     return None

# This function expects a string and uses regex (kept for reference if used elsewhere, but not by process_message_object)
def extract_token_from_string_representation(application_string_repr): 
    """Extracts the bot token from its string representation using regex."""
    if not isinstance(application_string_repr, str):
        logger.warning(f"extract_token_from_string_representation received non-string: {type(application_string_repr)}")
        return None
    match = re.search(r"token='([^']*)'", application_string_repr)
    if match:
        return match.group(1)
    logger.warning(f"Could not find token in string representation (first 100 chars): {application_string_repr[:100]}")
    return None


def extract_token_from_file(session_info):
    """Reads the application data file for the user and extracts the bot token using regex."""
    user_id = session_info.get('user_id')
    if not user_id:
        logger.error("No user_id found in session_info for token extraction.")
        return None
    filename = f"application_data_for_{user_id}.txt"
    try:
        with open(filename, "r") as f:
            application_data_str = f.read()
            print(f"DEBUG: Application data string (first 100 chars): {application_data_str[:100]}") # Debugging output
        # More robust regex: match token='...' or token="..." or token=... (no quotes)
        match = re.search(r"token[=:\s]*['\"]?([a-zA-Z0-9:_-]+)['\"]?", application_data_str)
        print(f"DEBUG: Regex match result: {match.group(1)}") # Debugging output
        if match:
            return match.group(1)
        logger.error(f"Could not find token in application data file for user_id {user_id}. Contents: {application_data_str[:200]}")
        return None
    except FileNotFoundError:
        logger.error(f"Application data file not found for user_id {user_id}: {filename}")
        return None
    except Exception as e:
        logger.error(f"Error reading application data file for user_id {user_id}: {e}")
        return None


def process_message_object(message_object):
    """
    Extracts necessary information from the message_object and sends a message
    to the Telegram user. The content of message_object['user_message'] is sent.
    """
    print(f"DEBUG: process_message_object called. Type of message_object: {type(message_object)}") # Debugging output

    # Validate the structure of message_object
    if not isinstance(message_object, dict):
        logger.error(f"Invalid message_object: Expected a dictionary, got {type(message_object)}.")
        return

    required_keys = ['session_info', 'user_message']
    missing_keys = [key for key in required_keys if key not in message_object]
    if missing_keys:
        logger.error(f"Invalid message_object: Missing required keys: {', '.join(missing_keys)}. Available keys: {list(message_object.keys())}")
        return

    session_info = message_object.get('session_info')
    if not isinstance(session_info, dict):
        logger.error(f"Invalid session_info in message_object: Expected a dictionary, got {type(session_info)}.")
        return
        
    chat_id_to_send = session_info.get('chat_id')
    if not chat_id_to_send:
        logger.error("chat_id missing or invalid in message_object's session_info.")
        return
    
    # === THE CRITICAL FIX IS HERE ===
    # Use the function that correctly extracts the token from the application data file
    bot_token = extract_token_from_file(session_info)
    # === END OF CRITICAL FIX ===
    
    if not bot_token:
        # extract_token_from_application_object already logs the error,
        # but we can add context here.
        logger.error(f"Failed to extract bot token for chat_id {chat_id_to_send}. Message cannot be sent.")
        return
    
    # The content of 'user_message' should be the tool output or AI's final textual response.
    # Ensure it's converted to a string before sending.
    message_to_send = str(message_object['user_message'])

    if not message_to_send.strip(): # Do not send empty or whitespace-only messages
        logger.info(f"Message content for chat_id {chat_id_to_send} is empty or whitespace only. Message not sent.")
        return

    logger.info(f"Attempting to send message to chat_id: {chat_id_to_send}")
    # For security, avoid logging the full token or log only a small, non-sensitive part if necessary for debugging.
    # logger.debug(f"Using bot_token (last 6 chars for verification): ...{bot_token[-6:]}") 
    logger.info(f"Message content (first 200 chars): '{message_to_send[:200]}...'")

    # Call the function to send the message via Telegram API
    send_telegram_message(chat_id_to_send, bot_token, message_to_send)


def send_telegram_message(chat_id, token, message_text):
    """Sends a message to a specific Telegram chat_id using the provided bot token.
    If the message exceeds 4000 characters, it's sent in chunks.
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    max_length = 4000  # Adjusted based on user feedback
    responses = []

    if len(message_text) <= max_length:
        message_chunks = [message_text]
    else:
        logger.info(f"Message for chat_id {chat_id} is longer than {max_length} characters. Splitting into chunks.")
        message_chunks = [message_text[i:i + max_length] for i in range(0, len(message_text), max_length)]

    for i, chunk in enumerate(message_chunks):
        payload = {
            'chat_id': chat_id,
            'text': str(chunk)  # Ensure chunk is explicitly a string
        }
        try:
            # It's good practice to set a timeout for network requests.
            logger.info(f"Sending chunk {i+1}/{len(message_chunks)} to chat_id {chat_id}...")
            response = requests.post(url, data=payload, timeout=10)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
            logger.info(f"Chunk {i+1}/{len(message_chunks)} sent successfully to chat_id {chat_id}. Response: {response.json()}")
            responses.append(response.json())
        except requests.exceptions.Timeout:
            logger.error(f"Timeout error sending chunk {i+1}/{len(message_chunks)} to chat_id {chat_id}.")
            responses.append({'ok': False, 'error_code': 'timeout', 'description': 'Request timed out.'})
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending chunk {i+1}/{len(message_chunks)} to chat_id {chat_id}: {e}")
            error_response = {'ok': False, 'error_code': 'request_exception', 'description': str(e)}
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Telegram API Response Status: {e.response.status_code}, Content: {e.response.text}")
                error_response['telegram_status_code'] = e.response.status_code
                error_response['telegram_content'] = e.response.text
            responses.append(error_response)
        except Exception as e:  # Catch any other unexpected errors
            logger.error(f"Unexpected error in send_telegram_message (chunk {i+1}/{len(message_chunks)}) for chat_id {chat_id}: {e}", exc_info=True)
            responses.append({'ok': False, 'error_code': 'unexpected_error', 'description': str(e)})

    if not responses: # Should not happen if there's at least one chunk
        return None
    if len(responses) == 1:
        return responses[0] # Return single response directly
    else:
        # For multiple chunks, you might want to return all responses or a summary
        # For now, returning all responses.
        return responses

if __name__ == "__main__":
    # This block is for testing this module directly.
    # You would need to set up mock objects for message_object, application_obj etc.
    # For example:
    # logging.basicConfig(level=logging.DEBUG) # Enable logging for testing
    # print("Testing message_user.py functions...")
    
    # Mock Application and Bot objects for testing extract_token_from_application_object
    # class MockBot:
    #     def __init__(self, token):
    #         self.token = token
    # class MockApplication:
    #     def __init__(self, token):
    #         self.bot = MockBot(token)
            
    # test_app_obj = MockApplication("YOUR_TEST_TOKEN")
    # token = extract_token_from_application_object(test_app_obj)
    # print(f"Extracted token: {token}") # Should be YOUR_TEST_TOKEN

    # test_app_obj_no_token = MockApplication(None)
    # token_none = extract_token_from_application_object(test_app_obj_no_token)
    # print(f"Extracted token (should be None): {token_none}")

    # test_app_obj_bad_structure = object() # Not an application object
    # token_bad = extract_token_from_application_object(test_app_obj_bad_structure)
    # print(f"Extracted token (should be None due to bad structure): {token_bad}")

    # To test process_message_object, you'd construct a full mock_message_object
    # mock_message_object_example = {
    #     'application': test_app_obj,
    #     'session_info': {'chat_id': '123456789'},
    #     'user_message': 'This is a test message from __main__.'
    # }
    # process_message_object(mock_message_object_example) # This would try to send a real Telegram message if token is valid

    pass