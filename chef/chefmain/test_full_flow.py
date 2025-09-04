#!/usr/bin/env python3

import sys
import os
sys.path.append('/workspaces/chevdev')
sys.path.append('/workspaces/chevdev/chef/chefmain') 
sys.path.append('/workspaces/chevdev/chef')

def test_complete_system():
    """Test the complete flow: Message Router -> Perplexity -> Advanced Reasoning"""
    
    print("=== TESTING COMPLETE SYSTEM FLOW ===\n")
    
    # Setup environment variables
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ OPENAI_API_KEY not set")
        return
    if not os.getenv('PERPLEXITY_KEY'):
        print("❌ PERPLEXITY_KEY not set") 
        return
    
    print("✅ API keys found")
    
    try:
        # Import with proper error handling
        print("→ Importing MessageRouter...")
        
        # Mock the missing dependencies first
        import utilities
        utilities.sheetscall = type('MockModule', (), {
            'sheets_call': lambda *a, **k: "Mock sheets result",
            'task_create': lambda *a, **k: "Mock task created",
            'fetch_preferences': lambda *a, **k: "Mock preferences", 
            'fetch_recipes': lambda *a, **k: "Mock recipes",
            'update_task': lambda *a, **k: "Mock task updated"
        })()
        
        utilities.firestore_chef = type('MockModule', (), {
            'firestore_get_docs_by_date_range': lambda *a, **k: "Mock firestore data"
        })()
        
        utilities.openai_agent_no_tool = type('MockModule', (), {
            'call_openai_no_tool': lambda *a, **k: "Mock general response"
        })()
        
        # Mock message_user module
        import message_user
        message_user.process_message_object = lambda x: print(f"→ Would send to user: {x.get('user_message', '')[:100]}...")
        
        from message_router import MessageRouter
        print("✅ MessageRouter imported successfully")
        
        router = MessageRouter()
        print("✅ MessageRouter initialized")
        
        # Test Turn 1: Search for recipes
        print("\n" + "="*50)
        print("TURN 1: User asks for croissant recipes")
        print("="*50)
        
        message_obj1 = {
            'user_id': 'test_user_123',
            'session_info': {'user_id': 'test_user_123', 'chat_id': 'test_chat'},
            'user_message': 'search perplexity for two croissant recipes'
        }
        
        print(f"→ Sending to MessageRouter: '{message_obj1['user_message']}'")
        print("→ Expected flow: MessageRouter → search_perplexity → recipe results")
        
        response1 = router.route_message(message_object=message_obj1)
        
        print(f"\n📋 RESPONSE 1:")
        print(response1)
        print("\n" + "-"*50)
        
        # Test Turn 2: Explore the recipes
        print("\nTURN 2: User wants to explore the recipes")
        print("="*50)
        
        message_obj2 = {
            'user_id': 'test_user_123',
            'session_info': {'user_id': 'test_user_123', 'chat_id': 'test_chat'},
            'user_message': 'help me explore these recipes and choose the best one for my situation'
        }
        
        print(f"→ Sending to MessageRouter: '{message_obj2['user_message']}'")
        print("→ Expected flow: MessageRouter → advanced_recipe_reasoning → constraint questions")
        
        response2 = router.route_message(message_object=message_obj2)
        
        print(f"\n📋 RESPONSE 2:")
        print(response2)
        
        print("\n" + "="*50)
        print("✅ COMPLETE SYSTEM TEST FINISHED!")
        print("="*50)
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("→ Make sure all dependencies are available")
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_complete_system()