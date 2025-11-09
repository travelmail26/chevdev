#!/usr/bin/env python3
"""Get the actual most recent conversation from MongoDB"""

import mongo_recent

print("Getting the ACTUAL most recent conversation from MongoDB...")
print("=" * 70)

# Get the most recent conversation
chats = mongo_recent.get_recent_chats(limit=1)

if chats:
    chat = chats[0]
    print(f"\nConversation ID: {chat.get('_id')}")
    print(f"Created: {chat.get('chat_session_created_at')}")
    print(f"Last Updated: {chat.get('last_updated_at')}")
    print(f"\nMessages ({len(chat.get('messages', []))}):")
    print("-" * 70)

    for i, msg in enumerate(chat.get('messages', []), 1):
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')

        # Show tool calls if present
        tool_calls = msg.get('tool_calls', [])

        print(f"\n{i}. [{role.upper()}]")
        if content:
            print(f"   {content}")

        if tool_calls:
            for tc in tool_calls:
                func = tc.get('function', {})
                print(f"   → Tool: {func.get('name')}")
                print(f"   → Args: {func.get('arguments')}")

        # Show tool results
        if role == 'tool':
            print(f"   Tool result: {content[:200]}...")

    print("\n" + "=" * 70)
else:
    print("No conversations found!")
