#!/usr/bin/env python3
import os
from datetime import datetime, timezone
from pymongo import MongoClient

# Connect to MongoDB using environment variable
uri = os.environ.get("MONGODB_URI")
if not uri:
    raise RuntimeError("MONGODB_URI is not set.")
client = MongoClient(uri)

# Specify your database and collection
db_name = os.environ.get("MONGODB_DB_NAME", "chef_chatbot")
collection_name = os.environ.get("MONGODB_COLLECTION_NAME", "chat_sessions")
db = client[db_name]
collection = db[collection_name]

def query_chats(
    content_search=None,
    created_since=None,
    created_until=None,
    limit=None,
    sort_by='last_updated_at',
    query_filter=None
):
    """
    General function to query chat sessions in the database.

    Args:
        content_search: String to search in messages.content (case-insensitive regex match)
        created_since: ISO timestamp string - chats created OR updated after this time
        created_until: ISO timestamp string - chats created OR updated before this time
        limit: Optional limit on number of conversations to return
        sort_by: Field to sort by, with '-' prefix for descending (default: 'last_updated_at' = descending)
        query_filter: Dict with MongoDB query operators for additional filtering
                     Examples:
                     - {'messages.role': 'system'}  # Messages with system role
                     - {'_id': {'$in': [id1, id2]}}  # Specific chat IDs

    Returns:
        List of chat session documents matching all criteria, sorted by sort_by

    Usage Example:
        # Find conversations from October 14, 2025, containing "chicken" in content
        results = query_chats(
            content_search="chicken",
            created_since="2025-10-14T00:00:00Z",
            created_until="2025-10-14T23:59:59Z",
            limit=10
        )
    """
    # Build MongoDB query
    query = {}

    # Add content search if provided (searches in the messages array)
    if content_search:
        query['messages.content'] = {'$regex': content_search, '$options': 'i'}

    # Add date filters - search BOTH created_at AND updated_at
    if created_since or created_until:
        date_filter = {}
        if created_since:
            date_filter['$gte'] = created_since
        if created_until:
            date_filter['$lte'] = created_until

        # Search both created and updated dates using $or
        query['$or'] = [
            {'chat_session_created_at': date_filter},
            {'last_updated_at': date_filter}
        ]

    # Merge with custom query_filter using $and if needed
    if query_filter:
        if query:
            query = {'$and': [query, query_filter]}
        else:
            query = query_filter

    # Build cursor with query
    cursor = collection.find(query)

    # Apply sorting (default to descending on chat_session_created_at for newest first)
    if sort_by:
        if sort_by.startswith('-'):
            cursor = cursor.sort(sort_by[1:], 1)  # Ascending
        else:
            cursor = cursor.sort(sort_by, -1)  # Descending

    # Apply limit
    if limit:
        cursor = cursor.limit(limit)

    return list(cursor)

def get_chat_messages(chat_id):
    """Get all messages from a specific chat by ID"""
    doc = collection.find_one({"_id": chat_id})
    if not doc:
        return []
    return doc.get("messages", [])

if __name__ == "__main__":
    # Example: Find chats with "recipe" in content, created since a certain date, limited to 2
    example_docs = query_chats(
        content_search="recipe",
        created_since="2025-10-01T00:00:00Z",
        limit=2
    )
    print("Example query results:")
    for doc in example_docs:
        print(doc)
