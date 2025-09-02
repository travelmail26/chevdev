#!/usr/bin/env python3

import sys
import os
import json
sys.path.append('/workspaces/chevdev/chef')

# Create a simple test history file
test_user_id = "test_integration_user"
history_file = f"/workspaces/chevdev/chef/chat_history_logs/{test_user_id}_history.json"

# Create test conversation history with recent recipe data
test_history = {
    "messages": [
        {
            "role": "user",
            "content": "search perplexity for croissant recipes for 2 different types of flour",
            "timestamp": "2025-01-14T10:00:00"
        },
        {
            "role": "assistant", 
            "content": "I found croissant recipes using multiple flour types including all-purpose + bread flour combinations. Here's a detailed recipe using 500g bread flour, 250g all-purpose flour, 125g butter, 10g salt, 12g sugar, 8g fresh yeast, and 400ml milk.",
            "timestamp": "2025-01-14T10:01:00"
        },
        {
            "role": "user",
            "content": "i'd like to explore making these recipes at the same time",
            "timestamp": "2025-01-14T10:02:00"
        },
        {
            "role": "assistant",
            "content": "Great! Making multiple croissant variations simultaneously is excellent for comparing textures and flavors. We can batch the dough preparations and coordinate the timing for lamination and proofing stages.",
            "timestamp": "2025-01-14T10:03:00"
        }
    ]
}

# Write test history file
with open(history_file, 'w') as f:
    json.dump(test_history, f, indent=2)

print(f"Created test history file: {history_file}")

# Now test with message router
from message_router import MessageRouter

def test_message_router_integration():
    """Test that message router properly passes conversation history"""
    
    print("\n=== TESTING MESSAGE ROUTER INTEGRATION ===")
    
    router = MessageRouter()
    
    # Test message that should trigger advanced reasoning
    test_message = {
        "user_id": test_user_id,
        "user_message": "what equipment will i need?"
    }
    
    print(f"Sending message: {test_message['user_message']}")
    print(f"With user_id: {test_user_id}")
    
    try:
        # This should load the conversation history and pass it to advanced reasoning
        response = router.route_message(message_object=test_message)
        print(f"\n=== RESPONSE ===")
        print(response)
        
        # Check if response shows context awareness
        context_aware = any(keyword in response.lower() for keyword in ['equipment', 'rolling', 'bowl', 'time'])
        
        print(f"\n=== ANALYSIS ===")
        print(f"✓ Message router executed: {len(response) > 0}")
        print(f"✓ Context awareness: {context_aware}")
        
        if context_aware:
            print("✅ SUCCESS: Message router + advanced reasoning integration working!")
        else:
            print("❌ ISSUE: Integration may not be working properly")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_message_router_integration()
