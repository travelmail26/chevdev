# Claude Instructions

This file contains instructions for Claude to help with development in this codebase.

## Project Overview
This is a culinary assistant chat/messaging system with:
- Message routing functionality
- MongoDB storage for conversations
- Firebase storage for media (images/videos)
- AI agents for analyzing conversations and media

## Code Philosophy
**CRITICAL: Keep code simple and beginner-friendly**
- Less is more
- Remove unnecessary debug statements
- Use simple, clear variable names
- Avoid over-complicating logic
- Print only the essential information (the actual content, not verbose debug messages)
- No emojis in code or debug output

## Development Workflow
- Main branch: `main`
- Current working branch: `dev`
- Always run lint/typecheck commands before finalizing changes (if available)

## Key Files and Directories
- `chef/message_router.py` - Message routing functionality
- `chef/testscripts/media_capture_agent.py` - AI agent for conversation/media analysis
- `chef/testscripts/mongo_recent.py` - MongoDB data fetching
- `chef/testscripts/firebase_manual_agent.py` - Firebase image operations
- `chat_history_logs/` - Chat history storage
- `mongo_exports/` - MongoDB export files

## OpenAI Model Configuration
**IMPORTANT:** All OpenAI API calls must use the model: `gpt-5-2025-08-07`

**DO NOT use `gpt-5-nano-2025-08-07` - it's slow or doesn't exist**

When creating or modifying code that uses the OpenAI API:
```python
client.chat.completions.create(
    model="gpt-5-2025-08-07",  # Always use this model
    messages=messages,
    ...
)
```

For streaming responses:
```python
# Simple streaming - just print the content
response = client.chat.completions.create(
    model="gpt-5-2025-08-07",
    messages=messages,
    stream=True
)

for chunk in response:
    if chunk.choices and chunk.choices[0].delta.content:
        content = chunk.choices[0].delta.content
        print(content, end='', flush=True)
        yield content
```

Key rules:
- Use `response` as the variable name for OpenAI responses
- Keep the `stream` parameter name as-is (don't create `stream_mode` variables)
- Print content immediately with `flush=True`

## Data Fetching Philosophy
**CRITICAL: Always filter at the database level, never fetch all data and filter in application code.**

### MongoDB Best Practices:
- **Filter at the source**: Use MongoDB query operators ($regex, $gte, $lte, etc.)
- **Content searches**: Use `query_filter` parameter with $regex for text searches
  - Example: `{'messages.content': {'$regex': 'pizza', '$options': 'i'}}`
- **Date ranges**: Use `since`/`until` parameters or `{'$gte': start, '$lte': end}`
- **Sorting**: Use `.sort('field', -1)` for descending (most recent first)
- **Limiting**: Always use `.limit(N)` for performance, especially with searches
- **Combine filters**: Use time filters + content filters + limit together

### Parameter Design:
- Make all query parameters optional with sensible defaults
- Expose MongoDB's native query capabilities through `query_filter` parameter
- Don't impose arbitrary hardcoded limits
- Default sort: newest first (`last_updated_at` descending)

### Division of Responsibility:
- **AI decides**: WHAT to query for (interprets user intent, constructs MongoDB queries)
- **MongoDB executes**: HOW to filter, sort, and limit efficiently
- **Never**: Fetch everything and filter in Python/JavaScript code

## Agent Intelligence Philosophy
**CRITICAL: Prefer agent intelligence over custom functions**

When working with AI agents (OpenAI, Claude, etc.):
- **Let the agent decide**: Don't write custom Python functions to analyze, filter, or process data
- **Agent-first approach**: Give the agent access to raw data and let it interpret/analyze
- **Trust agent intelligence**: The AI model is smart enough to extract insights, patterns, and answers
- **Avoid over-engineering**: Don't build logic that the agent can handle naturally

### What NOT to do:
- Writing functions to parse/extract URLs from text (agent can do this)
- Writing functions to count, filter, or deduplicate data (agent can do this)
- Writing custom analysis scripts (agent can analyze raw data)

### What to do instead:
- Provide the agent with database query functions
- Let the agent see raw data and decide what's relevant
- Ask the agent questions about the data
- Let the agent construct queries and interpret results

### Conversation History in Agents
- Be aware that conversation history persists across turns
- The agent may reference information from previous responses
- If seeing duplicates or repeated info, it may be from conversation memory
- Consider clearing history when starting fresh queries

## Commands
(To be updated as development commands are discovered)

## Notes for Claude
- Prefer editing existing files over creating new ones
- Follow existing code patterns and conventions
- Check package.json or requirements files for available dependencies
- Use the TodoWrite tool for complex multi-step tasks
- When working with OpenAI API, always use model `gpt-5-2025-08-07`