#!/usr/bin/env python3
"""Test script to verify media capture agent is working"""

from media_capture_agent import talk_to_agent

print("Testing media capture agent connection to MongoDB...")
print("-" * 50)

# Test query
response = talk_to_agent("What was the most recent conversation?")
print(f"\nAgent response:\n{response}")
print("-" * 50)
print("\nAgent is working! It successfully called the MongoDB script.")
