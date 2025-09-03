#!/usr/bin/env python3

import sys
import os
sys.path.append('/workspaces/chevdev/chef')

from message_router import MessageRouter
import json

def test_conversation_flow():
    """Test that conversation history flows through message router to advanced reasoning"""
    
    print("=== TESTING CONVERSATION HISTORY FLOW ===")
    
    # Create message router
    router = MessageRouter()
    
    # Simulate a conversation sequence
    user_id = "test_user_12345"
    
    print("\nSTEP 1: Simulate initial search message")
    message1 = {
        "user_id": user_id,
        "user_message": "search perplexity for croissant recipes for 2 different types of flour",
        "session_info": {"user_id": user_id}
    }
    
    # This should create search results and save to history
    response1 = router.route_message(message1)
    print(f"Response 1 length: {len(response1)} chars")
    
    print("\nSTEP 2: Simulate experiment request")
    message2 = {
        "user_id": user_id,
        "user_message": "i'd like to explore making these recipes at the same time",
        "session_info": {"user_id": user_id}
    }
    
    # This should trigger advanced_recipe_reasoning with conversation history
    response2 = router.route_message(message2)
    print(f"Response 2: {response2}")
    
    print("\nSTEP 3: Simulate equipment question")
    message3 = {
        "user_id": user_id,
        "user_message": "what equipment will i need?",
        "session_info": {"user_id": user_id}
    }
    
    # This should continue with advanced_recipe_reasoning using full history
    response3 = router.route_message(message3)
    print(f"Response 3: {response3}")
    
    print("\nSTEP 4: Check if responses show context awareness")
    # The responses should show the bot understands:
    # 1. There were croissant recipes found earlier
    # 2. User wants to make multiple types simultaneously  
    # 3. Bot should ask constraint questions or provide equipment lists
    
    context_aware = (
        "croissant" in response2.lower() or 
        "equipment" in response2.lower() or
        "flour" in response2.lower()
    )
    
    print(f"\n=== TEST RESULTS ===")
    print(f"✓ Step 1 completed: {len(response1) > 0}")
    print(f"✓ Step 2 completed: {len(response2) > 0}")
    print(f"✓ Step 3 completed: {len(response3) > 0}")
    print(f"✓ Context awareness: {context_aware}")
    
    if context_aware:
        print("✅ SUCCESS: Advanced reasoning appears to be using conversation history!")
    else:
        print("❌ ISSUE: Advanced reasoning may not be using conversation history properly")
        print(f"Response 2 was: {response2}")

if __name__ == "__main__":
    test_conversation_flow()
