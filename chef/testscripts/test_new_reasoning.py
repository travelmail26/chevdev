#!/usr/bin/env python3

import sys
import os
sys.path.append('/workspaces/chevdev/chef')

from utilities.advanced_recipe_reasoning import advanced_recipe_reasoning

def test_history_reading():
    # Test that the function can read conversation history directly from user_id
    test_user_id = "1275063227"  # User ID that has chat history
    test_query = "what do i need?"
    
    print(f"Testing advanced_recipe_reasoning with user_id: {test_user_id}")
    print(f"Query: {test_query}")
    print()
    
    # Call the function with user_id
    result = advanced_recipe_reasoning(query=test_query, user_id=test_user_id)
    print("Result:")
    print(result)
    print()
    
    # Test without user_id (should work but have no context)
    print("Testing without user_id (no context)...")
    result2 = advanced_recipe_reasoning(query=test_query, user_id=None)
    print("Result:")
    print(result2)

if __name__ == "__main__":
    test_history_reading()
