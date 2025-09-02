#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chef.utilities.advanced_recipe_reasoning import advanced_recipe_reasoning

def test_constraint_discovery():
    print("=== Testing Constraint Discovery Behavior ===")
    print()
    
    # Test 1: User wants to explore making recipes
    print("TEST 1: User wants to explore making croissant recipes")
    print("=" * 60)
    
    # Simulate conversation context with recipe data
    conversation_context = [
        {
            "role": "user", 
            "content": "search perplexity for croissant recipes for 2 different types of flour"
        },
        {
            "role": "assistant",
            "content": """Here are two croissant recipes using different types of flour:

## **Whole Wheat Croissants Recipe**
- 500g Janie's Mill Organic Sifted Artisan Bread Flour
- 235g lukewarm milk
- 85g lukewarm water
- 55g sugar
- 25g soft butter for the dough
- 10g salt
- 5g dry instant yeast
- 300g rolling butter

## **Traditional European-Style Croissants**
- 510g all-purpose or bread flour
- 510g unsalted butter
- 1 cup milk
- 2 tsp dry yeast
- 2 tsp salt
- 1/3 cup sugar"""
        }
    ]
    
    query = "i'd like to explore making both of these at the same time"
    
    print(f"USER QUERY: {query}")
    print()
    print("EXPECTED: Short question about constraints (like 'What cooking equipment do you have?')")
    print()
    print("ACTUAL RESPONSE:")
    print("-" * 40)
    
    try:
        response = advanced_recipe_reasoning(query, conversation_context)
        print(response)
        
        # Check if response is appropriately short (constraint discovery)
        word_count = len(response.split())
        print()
        print(f"ANALYSIS: Response has {word_count} words")
        if word_count < 15:
            print("✅ GOOD: Short constraint-discovery question")
        else:
            print("❌ BAD: Response too long, should be asking short constraint question")
            
    except Exception as e:
        print(f"ERROR: {e}")
    
    print()
    print("=" * 80)
    print()
    
    # Test 2: User asks for equipment needs
    print("TEST 2: User asks what equipment they need")
    print("=" * 60)
    
    query2 = "what equipment will i need?"
    print(f"USER QUERY: {query2}")
    print()
    print("EXPECTED: Short question about constraints, NOT a detailed equipment list")
    print()
    print("ACTUAL RESPONSE:")
    print("-" * 40)
    
    try:
        response2 = advanced_recipe_reasoning(query2, conversation_context)
        print(response2)
        
        word_count2 = len(response2.split())
        print()
        print(f"ANALYSIS: Response has {word_count2} words")
        if word_count2 < 15:
            print("✅ GOOD: Short constraint-discovery question")
        else:
            print("❌ BAD: Response too long, should be asking short constraint question")
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_constraint_discovery()
