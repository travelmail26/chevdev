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

def get_recent_chats(limit=None, since=None, until=None, sort_by='last_updated_at', query_filter=None):
    """
    Get chat sessions matching criteria. Uses MongoDB's native query capabilities.

    MongoDB best practices:
    - Filter at the database level, not in application code
    - Use efficient operators: $gte, $lte, $regex, $exists, etc.
    - Sort and limit at query time for performance

    Args:
        limit: Optional limit on number of conversations to return
        since: ISO timestamp string (e.g., "2025-10-27T12:00:00Z") - chats updated after this time
        until: ISO timestamp string - chats updated before this time
        sort_by: Field to sort by, with '-' prefix for descending (default: 'last_updated_at' = descending)
        query_filter: Dict with MongoDB query operators for advanced filtering
                     Examples:
                     - {'messages.content': {'$regex': 'https://', '$options': 'i'}} # contains URL
                     - {'messages.role': 'user'} # has user messages
                     - Can be combined with since/until filters

    Returns:
        List of chat session documents matching all criteria, sorted by sort_by
    """
    # Build MongoDB query
    query = {}

    # Add time-based filters
    if since or until:
        date_filter = {}
        if since:
            date_filter['$gte'] = since
        if until:
            date_filter['$lte'] = until

        # Try last_updated_at first, fall back to chat_session_created_at
        time_query = {'$or': [
            {'last_updated_at': date_filter},
            {'chat_session_created_at': date_filter}
        ]}

        # If we have other filters, combine with $and
        if query_filter:
            query = {'$and': [time_query, query_filter]}
        else:
            query = time_query
    elif query_filter:
        # No time filter, just use the custom filter
        query = query_filter

    # Build cursor with query
    cursor = collection.find(query)

    # Apply sorting (MongoDB best practice for "most recent")
    # Default to descending (newest first) on last_updated_at
    if sort_by:
        # Handle explicit descending prefix
        if sort_by.startswith('-'):
            cursor = cursor.sort(sort_by[1:], 1)  # Ascending
        else:
            cursor = cursor.sort(sort_by, -1)  # Descending (newest first)

    # Apply limit if specified (good for pagination and performance)
    if limit:
        cursor = cursor.limit(limit)

    return list(cursor)

if __name__ == "__main__":
    # Find the two most recent documents (sorted by _id descending)
    recent_docs = get_recent_chats(limit=2)

    print("Two most recent documents:")
    for doc in recent_docs:
        print(doc)


def get_chat_messages(chat_id):
    """Get all messages from a specific chat by ID"""
    doc = collection.find_one({"_id": chat_id})
    if not doc:
        return []
    return doc.get("messages", [])
