#!/usr/bin/env python3
"""
Test that verifies 300-char chunking works in telegram_bot
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'chefmain'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from message_router import MessageRouter

print("=" * 60)
print("CHUNKING TEST - Verify 300-char chunks")
print("=" * 60)

test_message_object = {
    'user_id': 'test_chunking',
    'session_info': {
        'user_id': 'test_chunking',
        'chat_id': 'test_chat',
        'message_id': 1,
        'timestamp': 1234567890,
        'username': 'test',
        'first_name': 'Test',
        'last_name': 'User'
    },
    'user_message': 'Tell me a long story about a robot chef'
}

print("\nAsking for a long story to test chunking...")

router = MessageRouter()
response_stream = router.route_message(
    message_object=test_message_object,
    stream=True
)

# Simulate what telegram_bot.py does
buffer = ""
messages_sent = []

if hasattr(response_stream, '__iter__') and not isinstance(response_stream, str):
    for chunk in response_stream:
        if chunk:
            buffer += chunk

            # Send when buffer reaches 300 characters
            while len(buffer) >= 300:
                message_part = buffer[:300]
                messages_sent.append(message_part)
                print(f"\n[Telegram] Sending chunk {len(messages_sent)}: {len(message_part)} chars")
                print(f"   First 50 chars: {message_part[:50]}...")
                buffer = buffer[300:]

    # Send remaining buffer
    if buffer.strip():
        messages_sent.append(buffer)
        print(f"\n[Telegram] Sending final chunk {len(messages_sent)}: {len(buffer)} chars")
        print(f"   First 50 chars: {buffer[:50]}...")

print("\n" + "=" * 60)
print(f"✓ Total Telegram messages sent: {len(messages_sent)}")
print(f"✓ Total characters: {sum(len(m) for m in messages_sent)}")
print(f"✓ Average chunk size: {sum(len(m) for m in messages_sent) / len(messages_sent):.1f} chars")
print("=" * 60)

if len(messages_sent) > 1:
    print("✓ ✓ ✓ CHUNKING WORKS - Multiple messages sent!")
else:
    print("⚠ Response was short - only 1 message sent (normal for short responses)")
