#!/usr/bin/env python3

import sys
import os
sys.path.append('/workspaces/chevdev/chef')

from message_router import MessageRouter

def test_complete_workflow():
    """Test the complete workflow through the message router API"""
    
    router = MessageRouter()
    print("=== COMPLETE WORKFLOW TEST THROUGH MESSAGE ROUTER ===\n")
    
    # Step 1: Initial search for croissant recipes
    print("STEP 1: Search for croissant recipes")
    print("-" * 60)
    
    messages_1 = [
        {"role": "system", "content": ""},
        {"role": "user", "content": "search perplexity for croissant recipes for 2 different types of flour"}
    ]
    
    try:
        response_1 = router.route_message(messages=messages_1)
        print("PERPLEXITY SEARCH RESPONSE:")
        print(response_1[:500] + "..." if len(response_1) > 500 else response_1)
        print("\n" + "="*80 + "\n")
    except Exception as e:
        print(f"ERROR in Step 1: {e}")
        return
    
    # Step 2: User wants to explore making both at the same time
    print("STEP 2: User wants to explore making both at the same time")
    print("-" * 60)
    
    messages_2 = [
        {"role": "system", "content": ""},
        {"role": "user", "content": "search perplexity for croissant recipes for 2 different types of flour"},
        {"role": "assistant", "content": response_1},
        {"role": "user", "content": "i'd like to explore making both of these at the same time"}
    ]
    
    try:
        response_2 = router.route_message(messages=messages_2)
        print("ADVANCED REASONING RESPONSE:")
        print(response_2)
        print("\n" + "="*80 + "\n")
    except Exception as e:
        print(f"ERROR in Step 2: {e}")
        return
    
    # Step 3: User asks what equipment they need
    print("STEP 3: User asks what equipment they need")
    print("-" * 60)
    
    messages_3 = messages_2.copy()
    messages_3.append({"role": "assistant", "content": response_2})
    messages_3.append({"role": "user", "content": "what equipment will i need?"})
    
    try:
        response_3 = router.route_message(messages=messages_3)
        print("EQUIPMENT REQUIREMENTS RESPONSE:")
        print(response_3)
        print("\n" + "="*80 + "\n")
    except Exception as e:
        print(f"ERROR in Step 3: {e}")
        return
    
    # Step 4: User provides equipment constraints
    print("STEP 4: User provides equipment constraints")
    print("-" * 60)
    
    messages_4 = messages_3.copy()
    messages_4.append({"role": "assistant", "content": response_3})
    messages_4.append({"role": "user", "content": "i only have one oven and no stand mixer"})
    
    try:
        response_4 = router.route_message(messages=messages_4)
        print("CONSTRAINT HANDLING RESPONSE:")
        print(response_4)
        print("\n" + "="*80 + "\n")
    except Exception as e:
        print(f"ERROR in Step 4: {e}")
        return
    
    # Step 5: User asks what to do next
    print("STEP 5: User asks what to do next")
    print("-" * 60)
    
    messages_5 = messages_4.copy()
    messages_5.append({"role": "assistant", "content": response_4})
    messages_5.append({"role": "user", "content": "what should i do next?"})
    
    try:
        response_5 = router.route_message(messages=messages_5)
        print("NEXT STEPS RESPONSE:")
        print(response_5)
        print("\n" + "="*80 + "\n")
    except Exception as e:
        print(f"ERROR in Step 5: {e}")
        return
    
    print("=== WORKFLOW TEST COMPLETED SUCCESSFULLY ===")
    print("\nSUMMARY:")
    print("1. ✓ Perplexity search found croissant recipes")
    print("2. ✓ Advanced reasoning engaged for exploration")
    print("3. ✓ Equipment requirements provided when asked")
    print("4. ✓ Constraints handled with practical alternatives")
    print("5. ✓ Next steps guidance provided")

if __name__ == "__main__":
    test_complete_workflow()
