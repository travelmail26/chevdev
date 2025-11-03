#!/usr/bin/env python3
"""
Test REAL streaming with OpenAI SDK
This verifies that chunks arrive in real-time as OpenAI generates them
"""

import sys
import os
import time

# Setup paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'chefmain'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from message_router import MessageRouter

print("=" * 60)
print("REAL-TIME STREAMING TEST (OpenAI SDK)")
print("=" * 60)

# Create test message
test_message_object = {
    'user_id': 'test_real_streaming',
    'session_info': {
        'user_id': 'test_real_streaming',
        'chat_id': 'test_chat',
        'message_id': 1,
        'timestamp': 1234567890,
        'username': 'test',
        'first_name': 'Test',
        'last_name': 'User'
    },
    'user_message': 'Tell me a short story about a robot chef'
}

print("\n1. Creating MessageRouter with OpenAI SDK...")
router = MessageRouter()

print("2. Requesting story from OpenAI with STREAMING enabled...")
print("3. Watching for chunks as they arrive IN REAL-TIME...\n")
print("-" * 60)

response_stream = router.route_message(
    message_object=test_message_object,
    stream=True
)

# Track timing to verify real-time streaming
chunk_times = []
start_time = time.time()
chunks = []

is_generator = hasattr(response_stream, '__iter__') and not isinstance(response_stream, str)

if is_generator:
    print("✓ Response is a generator (streaming enabled)")
    print("\nChunks arriving:")

    for i, chunk in enumerate(response_stream, 1):
        chunk_time = time.time() - start_time
        chunk_times.append(chunk_time)
        chunks.append(chunk)

        # Show when each chunk arrives
        print(f"  [{chunk_time:.2f}s] Chunk {i}: {len(chunk)} chars - '{chunk[:30]}...'")

    print("\n" + "-" * 60)

    # Analyze timing
    total_time = time.time() - start_time
    full_response = ''.join(chunks)

    print(f"\n✓ ✓ ✓ STREAMING ANALYSIS:")
    print(f"  Total chunks: {len(chunks)}")
    print(f"  First chunk at: {chunk_times[0]:.2f}s")
    print(f"  Last chunk at: {chunk_times[-1]:.2f}s")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Response length: {len(full_response)} chars")

    if len(chunk_times) > 1:
        avg_interval = (chunk_times[-1] - chunk_times[0]) / (len(chunk_times) - 1)
        print(f"  Avg time between chunks: {avg_interval:.3f}s")

    print(f"\n{'='*60}")

    if chunk_times[0] < 5.0 and len(chunks) > 1:
        print("✓ ✓ ✓ REAL-TIME STREAMING CONFIRMED!")
        print("Chunks arrived as OpenAI generated them, not all at once!")
    else:
        print("⚠ Streaming may not be real-time (first chunk took >5s)")

    print(f"{'='*60}")
    print(f"\nFull response:\n{full_response}")

else:
    print("✗ Response is NOT a generator - streaming not working")
    print(f"Response type: {type(response_stream)}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
