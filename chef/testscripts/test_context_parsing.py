#!/usr/bin/env python3

import sys
import os
sys.path.append('/workspaces/chevdev/chef')

from utilities.advanced_recipe_reasoning import advanced_recipe_reasoning

def test_context_parsing():
    # Test with conversation context (similar to what message router sends)
    test_query = """Current query: what do i need?

Conversation context (includes recipe data from previous searches):
[
  {
    "role": "user",
    "content": "search perplexity for croissant recipes for 2 different types of flour"
  },
  {
    "role": "assistant", 
    "content": "I found two excellent croissant recipes..."
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

    print("Testing context parsing...")
    print("Input query structure:")
    print("- Has 'Current query: what do i need?'")
    print("- Has conversation context with 4 previous messages")
    print("- Should recognize user is asking for equipment list")
    print("- Should progress to next constraint (time)")
    print()
    
    # Call the function
    result = advanced_recipe_reasoning(test_query)
    print("Result:")
    print(result)
    print()
    
    # Test without context
    simple_query = "what do i need?"
    print("Testing without context...")
    result2 = advanced_recipe_reasoning(simple_query)
    print("Result:")
    print(result2)

if __name__ == "__main__":
    test_context_parsing()
