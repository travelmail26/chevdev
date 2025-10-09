# System Behavior Notes

## Flexible Tool Selection Working Correctly

### Date: 2025-09-05
### Status: ✅ VERIFIED WORKING

**Key Success: Natural Tool Switching During Advanced Recipe Reasoning**

### What Happened:
- User was in advanced recipe reasoning (exploring croissant recipes). Bot did not get the full recipe ingredients the first time
- User asked: "search perplexity for those exact recipes again and have it return the full ingredient list"
- **AI model correctly chose `search_perplexity`** instead of staying forced in `advanced_recipe_reasoning`
- Perplexity successfully provided detailed ingredient list from Natasha's Baking recipe

### Why This Is Critical:
1. **Context Awareness**: Model understood that explicit "search perplexity" request meant switching tools
2. **Natural Flow**: Users can seamlessly call Perplexity mid-conversation when they need specific information
3. **No Forced Continuity**: System doesn't rigidly force `advanced_recipe_reasoning` when user clearly wants search
4. **Mixed Workflows**: Supports complex conversation patterns users actually want

### Technical Details:
- **Fixed Issue**: Removed continuity heuristic that was forcing tool selection
- **Result**: AI model makes natural tool choices based on user intent
- **Tool Flow**: `advanced_recipe_reasoning` → `search_perplexity` → back to reasoning (seamless)

### Should Be Preserved In Future Tests:
- ✅ Natural tool transitions work correctly  
- ✅ Users can get additional info during recipe exploration
- ✅ Context switching happens intelligently
- ✅ Mixed conversation flows are supported

### Test Pattern To Maintain:
1. Start with recipe search (`search_perplexity`)
2. Move to recipe exploration (`advanced_recipe_reasoning`) 
3. Mid-conversation: request specific search (`search_perplexity`)
4. Continue with recipe planning (`advanced_recipe_reasoning`)

**This represents ideal conversational AI behavior - flexible, context-aware, user-driven tool selection.**

## User Override Functionality

### Date: 2025-09-05
### Status: ✅ VERIFIED WORKING

**User overrides like "what do I need?" work correctly:**
- Triggers comprehensive equipment/ingredient lists instead of rigid constraint-gathering
- Flexible instruction set allows natural interruptions of structured questioning
- Users can ask "what ingredients do I need?" and get detailed responses

**Key Fix**: Removed forced tool selection heuristics, allowing natural AI model decision-making.