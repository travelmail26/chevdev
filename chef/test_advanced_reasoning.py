#!/usr/bin/env python3

import sys
import os
sys.path.append('/workspaces/chevdev/chef')

from utilities.advanced_recipe_reasoning import advanced_recipe_reasoning

def test_advanced_reasoning_directly():
    """Test the advanced recipe reasoning function directly with the croissant context"""
    
    print("=== TESTING ADVANCED RECIPE REASONING DIRECTLY ===\n")
    
    # Simulate the query that would be sent to advanced_recipe_reasoning
    # This includes the conversation context that the message router would inject
    query = """Current query: i'd like to explore making both of these at the same time

Conversation context:
search perplexity for croissant recipes for 2 different types of flour

Based on the search results, here are two distinct croissant recipes using different types of flour combinations:

## **Classic All-Purpose and Bread Flour Combination**

A proven recipe combines **450g all-purpose flour with 50g bread flour**. This creates a 90-10 ratio that maintains workability while adding structure. Here's the complete recipe:

**Ingredients:**
- 450g all-purpose flour + 50g bread flour
- 44g sugar
- 10g salt
- 50g soft unsalted butter
- 8g instant yeast
- 317g whole milk
- 283g unsalted butter for the butter block

## **Whole Wheat Flour Combinations**

For those seeking more complex flavors, whole wheat combinations offer excellent results. One option uses **300g white whole wheat flour combined with 200g whole wheat pastry flour**. This pairing balances the nutty flavor of whole wheat with the tenderness of pastry flour.

Both require standard croissant lamination techniques."""
    
    print("Query being sent to advanced_recipe_reasoning:")
    print("-" * 60)
    print(query)
    print("\n" + "="*60 + "\n")
    
    try:
        response = advanced_recipe_reasoning(query=query)
        print("ADVANCED RECIPE REASONING RESPONSE:")
        print("-" * 60)
        print(response)
        print("\n" + "="*60 + "\n")
    except Exception as e:
        print(f"ERROR: {e}")
        return
    
    # Now test the "what do I need?" scenario
    print("=== TESTING 'WHAT DO I NEED?' SCENARIO ===\n")
    
    query_2 = """Current query: what do i need?

Conversation context:
User: search perplexity for croissant recipes for 2 different types of flour
