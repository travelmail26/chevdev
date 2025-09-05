#!/usr/bin/env python3
"""
Test the complete conversation flow with advanced recipe reasoning:
1. Simulate croissant recipes from search
2. User says "explore recipes" 
3. Advanced reasoning asks about equipment
4. User asks "what do I need?" 
5. Bot provides equipment list
6. User says they're missing equipment
7. Bot acknowledges and moves to ingredients
8. User asks "what ingredients do I need?"
9. Bot provides ingredient list
10. User says they're missing an ingredient
11. Bot acknowledges and continues workflow
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))

from advanced_recipe_reasoning import advanced_recipe_reasoning

def test_full_conversation_flow():
    """Test conversation flow with manual evaluation after each response."""
    
    print("=== INTERACTIVE CONVERSATION FLOW TEST ===\n")
    
    # Start with conversation history that includes croissant recipes
    conversation_history = [
        {
            "role": "user",
            "content": "find me two croissant recipes on perplexity"
        },
        {
            "role": "assistant", 
            "content": """Here are two croissant recipes:

**Recipe 1: Quick and Easy Croissants from Scratch**
- 250g strong bread flour
- 150g cold unsalted butter, cubed  
- 120ml tepid milk
- 3 tbsp sugar
- 7g dry active yeast
- 1/2 tsp salt
- 1 egg yolk for glazing

**Recipe 2: Professional French-Style Croissants**
For the Dough:
- 510g all-purpose flour
- 65g granulated sugar
- 12g fine sea salt
- 10g instant yeast
- 144g cold water
- 144g cold whole milk
- 43g unsalted butter, softened

For Butter Layer:
- 284g cold unsalted butter

Equipment needed: Stand mixer, rolling pin, large work surface, baking sheets, oven"""
        }
    ]
    
    # Start the conversation
    turn_count = 1
    
    while True:
        print(f"\n{'='*60}")
        print(f"TURN {turn_count}")
        print('='*60)
        
        # Get user input
        user_message = input(f"\nEnter your message (or 'quit' to exit): ").strip()
        
        if user_message.lower() in ['quit', 'exit', 'q']:
            break
            
        if not user_message:
            continue
            
        print(f"\nUser says: '{user_message}'")
        
        # Add user message to conversation history
        conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        try:
            # Call advanced recipe reasoning with conversation history
            response = advanced_recipe_reasoning(
                conversation_history=conversation_history
            )
            
            print(f"\n{'='*50}")
            print("BOT RESPONSE:")
            print('='*50)
            print(response)
            print('='*50)
            
            # Add bot response to conversation history for next turn
            conversation_history.append({
                "role": "assistant", 
                "content": response
            })
            
            # Pause for evaluation
            input(f"\n[Press Enter to continue to next turn or Ctrl+C to exit...]")
            
        except Exception as e:
            print(f"\nERROR in turn {turn_count}: {e}")
            import traceback
            traceback.print_exc()
            break
        except KeyboardInterrupt:
            print(f"\n\nTest interrupted by user.")
            break
            
        turn_count += 1
    
    print(f"\n{'='*60}")
    print("CONVERSATION TEST COMPLETE")
    print('='*60)
    
    # Print final conversation history for review
    print(f"\n=== FINAL CONVERSATION HISTORY ({len(conversation_history)} messages) ===")
    for i, msg in enumerate(conversation_history):
        role_display = msg['role'].upper()
        content_preview = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
        print(f"{i+1}. {role_display}: {content_preview}")

if __name__ == "__main__":
    test_full_conversation_flow()