#!/usr/bin/env python3
"""Query the agent about the most recent conversation"""

from media_capture_agent import talk_to_agent

print("Asking agent for details about the most recent conversation...")
print("-" * 70)

response = talk_to_agent("Tell me more about the most recent conversation. What was discussed between the user and agent? Show me all the messages.")
print(f"\n{response}")
print("-" * 70)
