#!/usr/bin/env python3

import sys
import os
sys.path.append('/workspaces/chevdev/chef')

from message_router import MessageRouter

def test_croissant_workflow():
    """Test the exact croissant workflow: search then advanced reasoning"""
    
    router = MessageRouter()
    
    print("=== TESTING CROISSANT WORKFLOW ===\n")
    
    # Step 1: Search for croissant recipes
    print("Step 1: Search for croissant recipes for 2 different types of flour")
    print("-" * 60)
    
    messages_1 = [
        {"role": "system", "content": ""},
        {"role": "user", "content": "search perplexity for croissant recipes for 2 different types of flour"}
    ]
    
    try:
        response_1 = router.route_message(messages=messages_1)
        print("SEARCH RESPONSE:")
        print(response_1)
        print("\n" + "="*60 + "\n")
    except Exception as e:
        print(f"ERROR in search step: {e}")
        return
    
    # Step 2: User wants to explore making both at the same time
    print("Step 2: User wants to explore making both at the same time")
    print("-" * 60)
    
    # Simulate the conversation history after the search
    messages_2 = [
        {"role": "system", "content": ""},
        {"role": "user", "content": "search perplexity for croissant recipes for 2 different types of flour"},
        {"role": "assistant", "content": "Based on the search results, here are two distinct croissant recipes using different types of flour: one traditional recipe using regular flour and another using whole wheat flour.\n\n## Traditional Croissants with All-Purpose/Bread Flour\n\nFor classic croissants, you can use either all-purpose or a mix of all-purpose and bread flour. According to the source, \"All‑purpose flour works just fine for your first croissants, it's friendly, widely available, and easy to handle. But if you're looking to go a step further, try mixing 50% all‑purpose with 50% bread flour\"[5](https://lacuisinedegeraldine.fr/en/homemade-croissants). This mix \"gives you thicker, liftier layers and better structure, without making the dough too tough to work with\"[5](https://lacuisinedegeraldine.fr/en/homemade-croissants).\n\n**Traditional Recipe Ingredients:**\n- 510g flour (all-purpose or 50/50 mix with bread flour)\n- 510g unsalted butter\n- 1 cup milk\n- 2 tsp instant yeast\n- 2 tsp salt\n- 1/3 cup sugar[3](https://www.thefreshloaf.com/node/21473/which-flour-use-when-making-croissants)\n\n**Method:**\nMix ingredients on low speed, adding milk as needed. Hand knead until smooth, then wrap and rest at room temperature for 30 minutes before refrigerating. Prepare butter pat by mixing butter with 2 tablespoons flour, then laminate the dough[3](https://www.thefreshloaf.com/node/21473/which-flour-use-when-making-croissants).\n\n## Whole Wheat Croissants\n\nWhole wheat croissants require special consideration because the flour \"acts absolutely different, comparing to regular flour, it is heavier, thirstier and less stretchy\"[1](https://natashasbaking.com/whole-wheat-croissants/). However, with the right approach, \"croissants came out very light, with a beautiful color and unbelievable flavor\"[1](https://natashasbaking.com/whole-wheat-croissants/).\n\n**Whole Wheat Recipe Ingredients (12 croissants):**\n- 500g organic sifted artisan bread flour (stone ground, fine milled)\n- 235g lukewarm milk\n- 85g lukewarm water  \n- 55g sugar\n- 25g soft butter\n- 10g salt\n- 5g dry instant yeast\n- 300g European butter for rolling (82%+ fat content)[1](https://natashasbaking.com/whole-wheat-croissants/)\n\n**Key Considerations for Whole Wheat:**\nThe flour selection is crucial - \"to achieve results you want, you have to use flour, that is suitable for whole wheat croissants (stone ground, sifted and fine milled)\"[1](https://natashasbaking.com/whole-wheat-croissants/). \n\nFor enhanced flavor, you can substitute 100g of the main flour with \"50g Turkey Red flour and 50g Organic Black Emmer flour\"[1](https://natashasbaking.com/whole-wheat-croissants/) for deeper complexity.\n\n## Flour Type Considerations\n\nThe choice between flour types significantly affects texture. Research shows that \"heavier flour is better for sturdy croissants with a bready texture that you'd use for sandwiches and lighter flour is better for a delicate snack pastry\"[4](https://www.youtube.com/watch?v=uhNi65vWMLo). \n\nFor protein content, \"you can get great results from a flour with 13% protein\"[2](https://www.scoolinary.com/forums/discussion/which-flour-is-better-for-croissants), though the mineral content and flour origin also matter significantly.\n\nBoth recipes require proper lamination technique to achieve the characteristic flaky layers, but the whole wheat version demands more careful handling due to the flour's different properties."},
        {"role": "user", "content": "i'd like to explore making both of these at the same time"}
    ]
    
    try:
        response_2 = router.route_message(messages=messages_2)
        print("ADVANCED REASONING RESPONSE:")
        print(response_2)
        print("\n" + "="*60 + "\n")
    except Exception as e:
        print(f"ERROR in advanced reasoning step: {e}")
        return
    
    # Step 3: User asks "what do I need?"
    print("Step 3: User asks 'what do I need?'")
    print("-" * 60)
    
    # Add the previous response to conversation history
    messages_3 = messages_2.copy()
    messages_3.append({"role": "assistant", "content": response_2})
    messages_3.append({"role": "user", "content": "what do i need?"})
    
    try:
        response_3 = router.route_message(messages=messages_3)
        print("REQUIREMENTS RESPONSE:")
        print(response_3)
        print("\n" + "="*60 + "\n")
    except Exception as e:
        print(f"ERROR in requirements step: {e}")
        return
    
    print("=== WORKFLOW TEST COMPLETE ===")

if __name__ == "__main__":
    test_croissant_workflow()
