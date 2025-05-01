import logging
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def send_message_to_user(user_id, message, application=None, context=None):
    """
    Sends a message to the user, either via Telegram or by printing to console.

    Args:
        user_id: The identifier for the user (e.g., Telegram chat_id).
        message: The string message content to send.
        application: The Telegram Application instance (if sending via Telegram).
        context: Optional context (e.g., Telegram ContextTypes.DEFAULT_TYPE).
                 Currently unused but included for future flexibility.
    """
    if not message or not isinstance(message, str) or not message.strip():
        logger.warning(f"Attempted to send empty or invalid message to user {user_id}. Aborting.")
        return

    if application and user_id:
        try:
            # Attempt to send via Telegram
            logger.info(f"Sending Telegram message to user {user_id}")
            # Ensure the bot instance is available
            if hasattr(application, 'bot'):
                 # Split message if too long for Telegram
                max_length = 4096
                if len(message) > max_length:
                    logger.warning(f"Message to {user_id} exceeds Telegram limit ({len(message)} > {max_length}). Splitting.")
                    parts = [message[i:i+max_length] for i in range(0, len(message), max_length)]
                    for part in parts:
                        await application.bot.send_message(chat_id=user_id, text=part)
                        await asyncio.sleep(0.1) # Small delay between parts
                else:
                    await application.bot.send_message(chat_id=user_id, text=message)

            else:
                 logger.error("Telegram application object does not have a 'bot' attribute.")
                 # Fallback to printing
                 print(f"Fallback Print (User {user_id}): {message}")

        except Exception as e:
            logger.error(f"Failed to send Telegram message to user {user_id}: {e}")
            # Fallback to printing if Telegram fails
            print(f"Fallback Print (User {user_id}): {message}")
    else:
        # Default to printing if Telegram context is not available
        logger.info(f"Printing message for user {user_id} (No Telegram context)")
        print(f"To {user_id}: {message}")

# Example of how other scripts might use this (for illustration):
# async def example_usage():
#     # Example 1: Sending via print (no application provided)
#     await send_message_to_user("console_user_1", "This message goes to the console.")
#
#     # Example 2: Sending via Telegram (requires a running bot application instance)
#     # Assuming 'app' is your initialized Telegram Application
#     # await send_message_to_user(123456789, "This message goes via Telegram.", application=app)
#
# if __name__ == "__main__":
#     # To run the example usage (requires an event loop)
#     # asyncio.run(example_usage())
#     pass





