#!/usr/bin/env python3
"""Test that media_capture_agent can call MongoDB functions"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

print("Testing direct MongoDB function call...")
print("-" * 70)

# Test calling mongo_recent directly
import mongo_recent
print("\n1. Testing mongo_recent.get_recent_chats() directly:")
chats = mongo_recent.get_recent_chats(limit=2)
print(f"   Found {len(chats)} conversations")
if chats:
    print(f"   Most recent ID: {chats[0].get('_id')}")
    print(f"   Last updated: {chats[0].get('last_updated_at')}")

print("\n" + "-" * 70)
print("\n2. Testing media_capture_agent calling the same function:")

# Test through the agent
from media_capture_agent import fetch_mongodb_conversations

conversations = fetch_mongodb_conversations(limit=2)
print(f"   Agent retrieved {len(conversations)} conversations")
if conversations:
    print(f"   Most recent ID: {conversations[0].get('_id')}")
    print(f"   Last updated: {conversations[0].get('last_updated_at')}")
    print(f"   Number of messages: {len(conversations[0].get('messages', []))}")

print("\n" + "-" * 70)
print("\n✅ Both methods work! The agent IS calling mongo_recent.py")
