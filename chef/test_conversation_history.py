#!/usr/bin/env python3

import sys
import os
sys.path.append('/workspaces/chevdev/chef')

from utilities.advanced_recipe_reasoning import advanced_recipe_reasoning

def test_conversation_history_approach():
    """Test the new approach where we pass conversation history directly"""
    
    # Simulate conversation history like message router would pass
    conversation_history = [
        {
            "role": "user",
            "content": "search perplexity for croissant recipes for 2 different types of flour"
        },
        {
            "role": "assistant", 
            "content": "I found croissant recipes using different flour combinations: AP+bread flour and fresh milled flour blends..."
        },
        {
            "role": "user",
            "content": "i'd like to explore making these recipes at the same time"
        },
        {
            "role": "assistant",
            "content": "What cooking equipment do you have?"
        },
        {
            "role": "user",
            "content": "what equipment will i need?"
        }
    ]
    
    print("=== Testing Conversation History Approach ===")
    print(f"Passing {len(conversation_history)} messages to advanced_recipe_reasoning")
    print()
    
    # Call the function with conversation history
    result = advanced_recipe_reasoning(conversation_history=conversation_history)
    print("Result:")
    print(result)
    print()
    
    print("=== Expected Behavior ===")
    print("Bot should recognize:")
    print("1. User asked 'what equipment will i need?' after being asked about equipment")
    print("2. Should provide brief equipment list and move to next constraint (time)")
    print("3. Should NOT repeat 'What cooking equipment do you have?'")

if __name__ == "__main__":
    test_conversation_history_approach()
