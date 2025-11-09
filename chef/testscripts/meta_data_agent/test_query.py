#!/usr/bin/env python3
"""Test the agent with a specific query"""

from media_metadata_agent import talk_to_agent

# Test query
query = "in the mongo db database, find me the conversation that happend or was updated today november 6th. describe the conversation that happened"

print("Testing with query:")
print(f'"{query}"')
print("=" * 70)

response = talk_to_agent(query)
print(f"\n{response}")
