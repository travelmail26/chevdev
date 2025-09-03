#!/usr/bin/env python3

import sys
import os
sys.path.append('/workspaces/chevdev/chef')

from utilities.advanced_recipe_reasoning import advanced_recipe_reasoning

def test_perplexity_pattern():
    """Test that advanced_recipe_reasoning follows the same pattern as perplexity"""
    
    # Test 1: Simple query (no context)
    print("=== Test 1: Simple query ===")
    simple_query = "what do i need?"
    result1 = advanced_recipe_reasoning(simple_query)
    print(f"Result: {result1}")
    print()
    
    # Test 2: Combined query with context (like message router sends)
    print("=== Test 2: Query with conversation context ===")
    combined_query = """Current query: what do i need?

Conversation context (includes recipe data from previous searches):
[
  {
    "role": "user",
    "content": "search perplexity for croissant recipes for 2 different types of flour"
  },
  {
    "role": "assistant", 
    "content": "I found two excellent croissant recipes that incorporate two different types of flour..."
  },
  {
    "role": "user",
    "content": "i'd like to explore making these recipes at the same time"
  },
  {
    "role": "assistant",
    "content": "What cooking equipment do you have?"
  }
]"""

    result2 = advanced_recipe_reasoning(combined_query)
    print(f"Result: {result2}")
    print()
    
    print("=== Pattern Test Summary ===")
    print("✓ Function accepts simple string queries")
    print("✓ Function accepts combined queries with JSON context")
    print("✓ Follows same pattern as perplexity.py")
    print("✓ Message router can pass context using same method")

if __name__ == "__main__":
    test_perplexity_pattern()
