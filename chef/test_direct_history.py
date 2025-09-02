#!/usr/bin/env python3

import sys
import os
sys.path.append('/workspaces/chevdev/chef')

from utilities.advanced_recipe_reasoning import advanced_recipe_reasoning

def test_direct_conversation_history():
    """Test advanced_recipe_reasoning directly with conversation history"""
    
    print("=== TESTING DIRECT CONVERSATION HISTORY ===")
    
    # Simulate a conversation history
    conversation_history = [
        {
            "role": "user",
            "content": "search perplexity for croissant recipes for 2 different types of flour"
        },
        {
            "role": "assistant", 
            "content": "I found two excellent croissant recipes that incorporate two different types of flour. The first combines all-purpose and bread flour (450g + 50g), while the second uses a fresh milled flour blend with soft white, Kamut, and hard white flours."
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
    
    print(f"Testing with {len(conversation_history)} messages in conversation history")
    
    # Test the function
    result = advanced_recipe_reasoning(conversation_history=conversation_history)
    
    print(f"\n=== RESULT ===")
    print(result)
    
    # Check if the response shows context awareness
    context_keywords = ['croissant', 'flour', 'equipment', 'rolling', 'mixer', 'oven']
    context_aware = any(keyword in result.lower() for keyword in context_keywords)
    
    # Check if it's asking appropriate questions or providing equipment info
    progression_aware = (
        'time' in result.lower() or 
        'experience' in result.lower() or
        'rolling pin' in result.lower() or
        'bowl' in result.lower()
    )
    
    print(f"\n=== ANALYSIS ===")
    print(f"✓ Function executed: {len(result) > 0}")
    print(f"✓ Context awareness: {context_aware}")
    print(f"✓ Progression awareness: {progression_aware}")
    
    if context_aware and progression_aware:
        print("✅ SUCCESS: Function is using conversation history effectively!")
    elif context_aware:
        print("⚠️  PARTIAL: Function sees context but may not be progressing properly")
    else:
        print("❌ ISSUE: Function doesn't seem to be using conversation history")

if __name__ == "__main__":
    test_direct_conversation_history()
