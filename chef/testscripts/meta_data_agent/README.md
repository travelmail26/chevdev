# Media Metadata Agent

A conversational AI agent that translates plain language queries into MongoDB database calls using `mongo_simple`.

## Overview

This agent provides natural language access to:
- **MongoDB conversations** (via `mongo_simple.py`)
- **Firebase images/videos** (via parent directory's `firebase_manual_agent.py`)

## Files

- `query.py` - Simple query interface (run this to interact with the agent)
- `media_metadata_agent.py` - Main agent script with OpenAI integration
- `mongo_simple.py` - Simple MongoDB query interface
- `README.md` - This file

## How It Works

The agent translates plain language into MongoDB function calls:

### Simple Text Search
```
User: "Find conversations about pizza"
Agent calls: fetch_mongodb_conversations(content_search='pizza', limit=10)
```

### Advanced Filtering
```
User: "Find conversations with URLs"
Agent calls: fetch_mongodb_conversations(
    query_filter={'messages.content': {'$regex': 'https?://', '$options': 'i'}},
    limit=20
)
```

### Time-Based Queries
```
User: "Show conversations from today"
Agent calls: fetch_mongodb_conversations(
    since='2025-11-06T00:00:00Z',
    limit=20
)
```

### Combined Filters
```
User: "Show me today's chats about pizza"
Agent calls: fetch_mongodb_conversations(
    content_search='pizza',
    since='2025-11-06T00:00:00Z',
    limit=10
)
```

## mongo_simple.py API

### query_chats()

```python
def query_chats(
    content_search=None,      # Simple text search in messages
    created_since=None,       # ISO timestamp - chats created after
    created_until=None,       # ISO timestamp - chats created before
    limit=None,               # Max number of results
    sort_by='chat_session_created_at',  # Sort field
    query_filter=None         # MongoDB query dict
)
```

**Parameters:**
- `content_search`: Case-insensitive text search in message content
- `created_since`/`created_until`: ISO timestamp strings for date filtering
- `limit`: Maximum number of conversations to return
- `sort_by`: Field to sort by (default: newest first)
- `query_filter`: Advanced MongoDB query operators

**Examples:**

```python
# Simple text search
query_chats(content_search="pizza", limit=10)

# Date range
query_chats(
    created_since="2025-10-14T00:00:00Z",
    created_until="2025-10-14T23:59:59Z",
    limit=10
)

# Advanced filtering
query_chats(
    query_filter={'messages.content': {'$regex': 'https://', '$options': 'i'}},
    limit=20
)

# Combined filters
query_chats(
    content_search="chicken",
    created_since="2025-11-01T00:00:00Z",
    limit=5
)
```

## Usage

### Quick Start - Query Interface

```bash
cd chef/testscripts/meta_data_agent
python3 query.py
```

This starts an interactive session where you can ask questions in plain language.

### Direct Agent Usage

```bash
python3 media_metadata_agent.py
```

### Example Queries

- "What was the most recent conversation?"
- "Find conversations about pizza"
- "Show me chats from today"
- "Find conversations with URLs"
- "Show chats from October 17th"
- "Most recent conversation with a video URL"

## Environment Variables

Required:
- `MONGODB_URI` - MongoDB connection string
- `FIREBASEJSON` - Firebase credentials JSON (for image queries)

Optional:
- `MONGODB_DB_NAME` - Database name (default: "chef_chatbot")
- `MONGODB_COLLECTION_NAME` - Collection name (default: "chat_sessions")

## Database-Level Filtering

The agent follows best practices by:
- Filtering at the database level (not in application code)
- Using MongoDB query operators for efficiency
- Combining time filters with content filters
- Always setting reasonable limits for performance

## MongoDB Query Operators

Common operators used:
- `$regex` - Pattern matching
- `$options: 'i'` - Case-insensitive search
- `$gte`/`$lte` - Greater/less than for dates
- Nested field access: `messages.content`, `messages.role`
