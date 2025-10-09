# LLM Handoff Summary: Recipe AI System

## Overall Goal
Multi-turn conversational AI for recipe assistance via Telegram. Users can flexibly switch between constraint-discovery questioning and search tools mid-conversation.

## How It Works (Brief)
1. Telegram webhook → `message_router.py` → OpenAI function calling → recipe tools
2. AI model selects tools naturally (no forced heuristics)
3. Two main flows: constraint-discovery (`advanced_recipe_reasoning`) and search (`search_perplexity`)
4. Users can interrupt/override structured questioning anytime

## Key APIs Used
- **OpenAI API** - function calling for tool selection and responses
- **Telegram Bot API** - webhook integration for messaging
- **Perplexity API** - external search functionality
- Likely recipe database API (check message_router.py for endpoints)

## Critical File Structure

**CORE PRODUCT**: `/workspaces/chevdev/chef/chefmain/`
- `message_router.py` - **MOST IMPORTANT** - handles all tool selection and routing
- Never add forced tool selection logic here (user hates this)

**INSTRUCTIONS**: `/workspaces/chevdev/chef/utilities/instructions/`
- `recipe_experimenting.txt` - constraint-discovery system prompts
- `instructions_recipe.txt` - recipe database handling rules
- Place new instruction files here

**TESTING**: `/workspaces/chevdev/chef/testscripts/`  
- `SYSTEM_BEHAVIOR_NOTES.md` - successful behaviors to preserve
- Place test scripts and behavior documentation here
- `advanced_recipe_reasoning.py` - constraint-discovery tool implementation

## Key Files to Read First
1. `chef/chefmain/message_router.py` - understand tool selection flow & API integrations
2. `chef/utilities/instructions/recipe_experimenting.txt` - see constraint-discovery prompts  
3. `chef/testscripts/SYSTEM_BEHAVIOR_NOTES.md` - critical behaviors to preserve

## Secrets/Variables
- OpenAI API key, Telegram bot token, Perplexity API key
- Check for API keys and database credentials in environment variables
- Never hardcode secrets in files
- Look for `.env` files or environment variable usage in message_router.py

## User's Rules
- **NEVER** add forced tool selection heuristics
- **ALWAYS** let AI model choose tools naturally
- **PREFER** editing existing files over creating new ones
- **TEST** through full Telegram pipeline, not isolated functions

## Current Status
Tool selection fixed, user overrides working, plagiarism handling added. System allows natural conversation flow with flexible tool switching.

## Example Conversation Flow

### Desired Flow (Working Now):
**Turn 1:**
- User: "I want to make croissants. Search perplexity for two croissant recipes"
- Script: `message_router.py` → calls OpenAI → selects `search_perplexity`
- Variables passed: `user_message`, `chat_history`
- Result: Perplexity searches for croissant recipes

**Turn 2:**
- User: "I want to experiment with those recipes at the same time"
- Script: `message_router.py` → OpenAI selects `advanced_recipe_reasoning`
- Variables: `user_message`, `chat_history`, `recipe_context`
- Tool: `advanced_recipe_reasoning.py` loads instructions from `recipe_experimenting.txt`
- Result: "What cooking equipment do you have?"

**Turn 3:**
- User: "what do I need?" (USER OVERRIDE)
- Script: `message_router.py` → OpenAI naturally chooses `advanced_recipe_reasoning`
- Variables: `user_message`, `equipment_constraints`
- Result: "Rolling pin, bowl, oven. How much time can you dedicate?" (flexible response)

**Turn 4:**
- User: "search perplexity for those exact recipes again and have it return the full ingredient list"
- Script: `message_router.py` → OpenAI selects `search_perplexity` (natural tool switching)
- Variables: `user_message`, `recipe_context`, `search_query`
- Result: Detailed ingredient list from Perplexity

### What Was Broken Before:
**Turn 3 Problem:**
- Script: `message_router.py` lines 342-371 had continuity heuristic
- Forced: `tool_choice = 'advanced_recipe_reasoning'` regardless of user intent
- Result: Rigid constraint gathering instead of flexible "what do I need?" response

**Turn 4 Problem:**
- Same forced tool selection prevented natural switching to `search_perplexity`
- User explicitly requested Perplexity but system stayed locked in `advanced_recipe_reasoning`
- Variables: `force_tool_choice` override prevented natural `tool_choice` selection