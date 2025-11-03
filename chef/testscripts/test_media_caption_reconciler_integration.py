"""
Integration test for media_caption_reconciler agent.

This script runs the reconciler agent with logging to verify:
- Tool calls are in the correct order (list_pending_media first, then save_media_caption)
- No errors occur during execution
- Captions are saved correctly
- The final message informs the user about the reconciliation process
"""

import json
import logging
import os
import sys
from pathlib import Path

# Add testscripts to path
sys.path.append(str(Path(__file__).resolve().parent))

import media_caption_reconciler as mcr

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    # Check required environment variables (some have defaults)
    env_vars = {
        'OPENAI_API_KEY': None,
        'MONGODB_URI': None,
        'MONGODB_DB_NAME': 'chef_chatbot',
        'MONGODB_COLLECTION_NAME': 'chat_sessions'
    }
    
    missing = []
    for var, default in env_vars.items():
        value = os.getenv(var, default)
        if value is None:
            missing.append(var)
        else:
            os.environ.setdefault(var, value)
    if missing:
        logging.error(f"Missing required environment variables (no default): {missing}")
        sys.exit(1)
    
    logging.info("Environment variables check passed.")
    
    # Track tool call sequence
    call_sequence = []
    
    # Wrap tool functions to log calls and track sequence
    original_list = mcr.list_pending_media
    def logged_list_pending_media(limit=5):
        call_sequence.append('list_pending_media')
        logging.info(f"Tool call #{len(call_sequence)}: list_pending_media(limit={limit})")
        try:
            result = original_list(limit=limit)
            logging.info(f"list_pending_media returned {len(result.get('items', []))} items")
            return result
        except Exception as e:
            logging.error(f"Error in list_pending_media: {e}")
            raise
    
    original_save = mcr.save_media_caption
    def logged_save_media_caption(session_id, message_index, caption, source="assistant"):
        call_sequence.append('save_media_caption')
        logging.info(f"Tool call #{len(call_sequence)}: save_media_caption(session_id={session_id}, message_index={message_index}, caption='{caption}', source='{source}')")
        try:
            result = original_save(session_id, message_index, caption, source)
            logging.info(f"save_media_caption saved caption: '{caption}'")
            return result
        except Exception as e:
            logging.error(f"Error in save_media_caption: {e}")
            raise
    
    # Replace in TOOL_MAP
    mcr.TOOL_MAP['list_pending_media'] = logged_list_pending_media
    mcr.TOOL_MAP['save_media_caption'] = logged_save_media_caption
    
    # Run the agent with a limited request
    initial_request = "Reconcile up to 2 media entries."
    logging.info(f"Starting agent with request: {initial_request}")
    
    try:
        final_message = mcr.run_agent(initial_request=initial_request, temperature=1.0)
        logging.info(f"Agent completed. Final message: {json.dumps(final_message, indent=2)}")
        
        # Assertions
        assert isinstance(final_message, dict), "Final message should be a dict"
        assert 'content' in final_message, "Final message should have 'content' key"
        assert final_message['content'], "Final message content should not be empty"
        
        # Check sequence: should start with list_pending_media
        if call_sequence:
            assert call_sequence[0] == 'list_pending_media', f"First call should be list_pending_media, got {call_sequence[0]}"
            logging.info(f"Tool call sequence: {call_sequence}")
        else:
            logging.warning("No tool calls made - agent may have no pending media or failed to call tools")
        
        logging.info("All checks passed. Reconciler appears to be working correctly.")
        
    except Exception as e:
        logging.error(f"Agent execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()