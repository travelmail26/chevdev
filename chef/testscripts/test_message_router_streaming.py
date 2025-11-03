#!/usr/bin/env python3
"""
Direct test of message_router streaming functionality.
Tests the OpenAI SSE parsing without requiring Telegram.
"""

import sys
import os
import json

# Add parent directory to path
chef_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
chefmain_dir = os.path.join(chef_dir, 'chefmain')
sys.path.insert(0, chefmain_dir)
sys.path.insert(0, chef_dir)

from message_router import MessageRouter

def test_streaming_response():
    """Test that message_router properly streams responses"""

    print("=" * 60)
    print("MESSAGE ROUTER STREAMING TEST")
    print("=" * 60)

    router = MessageRouter()

    # Create a test message object
    test_message_object = {
        'user_id': 'test_user_streaming',
        'session_info': {
            'user_id': 'test_user_streaming',
            'chat_id': 'test_chat',
            'message_id': 1,
            'timestamp': 1234567890,
            'username': 'test_user',
            'first_name': 'Test',
            'last_name': 'User'
        },
        'user_message': 'Tell me a very short story about a robot chef'
    }

    print("\nTest message:", test_message_object['user_message'])
    print("\nStreaming mode: ENABLED")
    print("-" * 60)

    # Test streaming
    print("\nChunks received:")
    response_stream = router.route_message(
        message_object=test_message_object,
        stream=True
    )

    chunk_count = 0
    full_response = ""

    # Check if it's a generator
    if hasattr(response_stream, '__iter__') and not isinstance(response_stream, str):
        print("✓ Response is a generator (streaming)")

        for chunk in response_stream:
            chunk_count += 1
            full_response += chunk
            print(f"  Chunk {chunk_count}: '{chunk}' (len={len(chunk)})")
    else:
        print("✗ Response is NOT a generator (non-streaming)")
        full_response = str(response_stream)

    print("-" * 60)
    print(f"\nTotal chunks: {chunk_count}")
    print(f"Full response length: {len(full_response)} chars")
    print(f"\nFull response:\n{full_response}")
    print("\n" + "=" * 60)

    # Verify the response was saved to history
    history_file = f"/workspaces/chevdev/chef/utilities/chat_history_logs/test_user_streaming_history.json"
    if os.path.exists(history_file):
        print("✓ History file created")
        with open(history_file, 'r') as f:
            history = json.load(f)
            messages = history.get('messages', [])
            assistant_messages = [m for m in messages if m.get('role') == 'assistant']
            if assistant_messages:
                last_assistant = assistant_messages[-1]
                saved_content = last_assistant.get('content', '')
                print(f"✓ Last assistant message in history: {len(saved_content)} chars")
                if saved_content == full_response:
                    print("✓ PASS: Saved message matches streamed response!")
                else:
                    print("✗ FAIL: Saved message doesn't match!")
                    print(f"  Expected: {full_response[:100]}...")
                    print(f"  Got: {saved_content[:100]}...")
    else:
        print("✗ History file not found")

    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_streaming_response()
