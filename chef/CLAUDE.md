# Claude Instructions

This file contains instructions for Claude to help with development in this codebase.

## Project Overview
This is a culinary assistant chat/messaging system with:
- Message routing functionality
- MongoDB storage for conversations
- Firebase storage for media (images/videos)
- AI agents for analyzing conversations and media

## Development Workflow
- Main branch: `main`
- Current working branch: `dev`
- Always run lint/typecheck commands before finalizing changes (if available)

## Key Files and Directories
- `message_router.py` - Message routing functionality
- `testscripts/media_capture_agent.py` - AI agent for conversation/media analysis
- `testscripts/mongo_recent.py` - MongoDB data fetching
- `testscripts/firebase_manual_agent.py` - Firebase image operations
- `../chat_history_logs/` - Chat history storage
- `../mongo_exports/` - MongoDB export files

## OpenAI Model Configuration
**IMPORTANT:** All OpenAI API calls must use the model: `gpt-5-2025-08-07`

When creating or modifying code that uses the OpenAI API:
```python
client.chat.completions.create(
    model="gpt-5-2025-08-07",  # Always use this model
    messages=messages,
    ...
)
```

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

## Commands
(To be updated as development commands are discovered)

## Notes for Claude
- Prefer editing existing files over creating new ones
- Follow existing code patterns and conventions
- Check package.json or requirements files for available dependencies
- Use the TodoWrite tool for complex multi-step tasks
- When working with OpenAI API, always use model `gpt-5-2025-08-07`