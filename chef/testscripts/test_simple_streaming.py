#!/usr/bin/env python3
"""
Simple test that verifies streaming works exactly like main.py uses it.
"""

import sys
import os

# Setup paths exactly like main.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'chefmain'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from message_router import MessageRouter

print("=" * 60)
print("SIMPLE STREAMING TEST (mimics main.py behavior)")
print("=" * 60)

# Create test message object like telegram_bot creates
test_message_object = {
    'user_id': 'test_streaming_user',
    'session_info': {
        'user_id': 'test_streaming_user',
        'chat_id': 'test_chat',
        'message_id': 1,
        'timestamp': 1234567890,
        'username': 'test',
        'first_name': 'Test',
        'last_name': 'User'
    },
    'user_message': 'hi'
}

print("\n1. Creating MessageRouter...")
router = MessageRouter()

print("2. Calling route_message with stream=True...")
print("3. User message: 'hi'\n")

response_stream = router.route_message(
    message_object=test_message_object,
    stream=True
)

print("4. Checking if response is a generator...")
is_generator = hasattr(response_stream, '__iter__') and not isinstance(response_stream, str)
print(f"   Is generator: {is_generator}")

if is_generator:
    print("\n5. ✓ PASS: Response is streaming!")
    print("6. Collecting chunks...\n")

    chunks = []
    for i, chunk in enumerate(response_stream, 1):
        chunks.append(chunk)
        print(f"   Chunk {i}: '{chunk[:50]}...' ({len(chunk)} chars)")

    full_response = ''.join(chunks)
    print(f"\n7. Total chunks: {len(chunks)}")
    print(f"8. Full response length: {len(full_response)} chars")
    print(f"9. Full response: {full_response}")
    print("\n✓ ✓ ✓ TEST PASSED - Streaming works!")
else:
    print("\n5. ✗ FAIL: Response is NOT streaming")
    print(f"   Response type: {type(response_stream)}")
    print(f"   Response: {response_stream}")
    print("\n✗ ✗ ✗ TEST FAILED")

print("=" * 60)
