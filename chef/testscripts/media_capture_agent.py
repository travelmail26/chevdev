#!/usr/bin/env python3
"""
Ultra-Minimal Media Capture Agent
==================================
The agent is smart - it just needs access to data.
MongoDB = conversations
Firebase = images with metadata
"""

import json
import sys
import os
from openai import OpenAI

# Make sure we can import the other scripts
sys.path.insert(0, os.path.dirname(__file__))

# Import the actual functions from the other files
import firebase_manual_agent
import mongo_recent


def fetch_firebase_images(limit, since=None):
    """Get images from Firebase. Returns list of image data."""
    return firebase_manual_agent.get_recent_images_from_firebase(limit, since)


def fetch_firebase_image_by_url(url):
    """Get specific Firebase image info by URL."""
    result = firebase_manual_agent.get_specific_image_url(url)
    if result:
        blob, public_url = result
        return {"url": public_url, "metadata": blob.metadata}
    return None


def fetch_mongodb_conversations(limit=None, since=None, until=None, sort_by=None, query_filter=None):
    """Get conversations from MongoDB. Returns list of conversation data."""
    return mongo_recent.get_recent_chats(limit=limit, since=since, until=until, sort_by=sort_by, query_filter=query_filter)


def fetch_conversation_by_id(chat_id):
    """Get a specific conversation from MongoDB by its ID."""
    # Try as string first
    doc = mongo_recent.collection.find_one({"_id": chat_id})
    if not doc:
        # Try as ObjectId
        try:
            from bson import ObjectId
            doc = mongo_recent.collection.find_one({"_id": ObjectId(chat_id)})
        except:
            pass
    return doc


def analyze_image_url(url, prompt=None):
    """
    Analyze an image from a URL using OpenAI Vision.
    Works with Firebase, Google Storage, or any publicly accessible image URL.
    """
    client = OpenAI()

    if prompt is None:
        prompt = "What's in this image? Describe it in detail."

    response = client.chat.completions.create(
        model="gpt-5-2025-08-07",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": url}
                    }
                ]
            }
        ]
    )

    return response.choices[0].message.content


# Tell the AI what functions it can call
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_firebase_images",
            "description": "Get recent images from Firebase Storage with their metadata",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "How many images to fetch"},
                    "since": {"type": "string", "description": "Optional: only get images after this timestamp"}
                },
                "required": ["limit"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_firebase_image_by_url",
            "description": "Get metadata for a specific Firebase image URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The Firebase URL to check"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_mongodb_conversations",
            "description": "Get conversations from MongoDB using efficient database-level filtering. ALWAYS filter at the database level, never fetch all and filter in code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Optional: max number of conversations to return. Use for performance."},
                    "since": {"type": "string", "description": "Optional: ISO timestamp - only get conversations updated after this time (e.g., '2025-10-17T00:00:00Z')"},
                    "until": {"type": "string", "description": "Optional: ISO timestamp - only get conversations updated before this time"},
                    "sort_by": {"type": "string", "description": "Optional: field to sort by. Default is 'last_updated_at' (descending/newest first). Use '-' prefix for ascending."},
                    "query_filter": {
                        "type": "object",
                        "description": "Optional: MongoDB query object to filter conversations. Use MongoDB query operators for efficient filtering. Examples: {'messages.content': {'$regex': 'https://'}} for URLs, {'messages.content': {'$regex': 'pizza', '$options': 'i'}} for keyword search (case-insensitive)."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_conversation_by_id",
            "description": "Get a specific conversation from MongoDB using its ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "The conversation ID"}
                },
                "required": ["chat_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_image_url",
            "description": "Analyze an image from a URL using OpenAI Vision. Use this when asked to evaluate, assess, or analyze an image URL from Firebase, Google Storage, or any other source.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The image URL to analyze (Firebase, Google Storage, or any public URL)"},
                    "prompt": {"type": "string", "description": "Optional: specific question or instruction for analyzing the image. Defaults to general description."}
                },
                "required": ["url"]
            }
        }
    }
]


def make_json_safe(obj):
    """Convert MongoDB objects to JSON-safe format."""
    import datetime
    from bson import ObjectId
    
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_safe(item) for item in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime.datetime):
        return obj.isoformat()
    else:
        return obj


def talk_to_agent(message, history=None):
    """
    Simple function to talk to the agent.
    The agent is smart - it knows what to do with the data.
    """
    client = OpenAI()
    
    if history is None:
        history = []
    
    # Build conversation
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant with access to conversation and media data.\n\n"
                "## CRITICAL: Use Database-Level Filtering\n"
                "**ALWAYS filter at the MongoDB level using query_filter parameter. NEVER fetch all conversations and filter in code.**\n"
                "This is a fundamental database best practice for performance and efficiency.\n\n"
                "## Available Data Sources\n"
                "1. **MongoDB**: Full conversation history with messages, timestamps, metadata\n"
                "2. **Firebase**: Images/videos with upload timestamps and metadata\n\n"
                "## MongoDB Query Best Practices\n\n"
                "### When to use query_filter parameter:\n"
                "Use query_filter whenever the user asks to find conversations based on CONTENT:\n"
                "- 'Find conversations with URLs' → Use $regex to search message content\n"
                "- 'Conversations mentioning pizza' → Use $regex with case-insensitive search\n"
                "- 'Chats with videos' → Use $regex to find .mp4, .mov extensions\n"
                "- 'Conversations where user asked about X' → Filter by role='user' and content\n\n"
                "### MongoDB Query Operators:\n"
                "```\n"
                "query_filter examples:\n\n"
                "# Find conversations with URLs (http:// or https://)\n"
                "{'messages.content': {'$regex': 'https?://', '$options': 'i'}}\n\n"
                "# Find conversations mentioning 'pizza' (case-insensitive)\n"
                "{'messages.content': {'$regex': 'pizza', '$options': 'i'}}\n\n"
                "# Find conversations with video files\n"
                "{'messages.content': {'$regex': '\\\\.(mp4|mov|avi)', '$options': 'i'}}\n\n"
                "# Find conversations with storage.googleapis.com URLs\n"
                "{'messages.content': {'$regex': 'storage\\\\.googleapis\\\\.com'}}\n\n"
                "# Multiple conditions (AND) - conversations with URLs from today\n"
                "Combine query_filter with since parameter automatically\n"
                "```\n\n"
                "### Parameter Usage:\n\n"
                "- **query_filter**: MongoDB query dict for content-based filtering (USE THIS!)\n"
                "  - Required when searching for specific content/keywords\n"
                "  - Use $regex for text search, $options: 'i' for case-insensitive\n"
                "  - Access nested fields: 'messages.content', 'messages.role'\n\n"
                "- **limit**: Max conversations to return (for performance)\n"
                "  - 'Most recent conversation' → limit=1\n"
                "  - 'Last 10 chats' → limit=10\n"
                "  - When searching (using query_filter), consider adding a limit\n\n"
                "- **since/until**: Time-based filtering\n"
                "  - ISO timestamp format: '2025-10-17T00:00:00Z'\n"
                "  - Automatically combined with query_filter\n\n"
                "- **sort_by**: Usually don't change (default is newest first)\n\n"
                "## Query Examples (USE THESE PATTERNS):\n\n"
                "❌ WRONG: fetch_mongodb_conversations() then filter in code\n"
                "✅ RIGHT: Use query_filter parameter\n\n"
                "User: 'What was the most recent conversation?'\n"
                "→ fetch_mongodb_conversations(limit=1)\n\n"
                "User: 'Find conversations with URLs'\n"
                "→ fetch_mongodb_conversations(\n"
                "    query_filter={'messages.content': {'$regex': 'https?://', '$options': 'i'}},\n"
                "    limit=20  # reasonable limit for performance\n"
                "  )\n\n"
                "User: 'Show me chats from today that mention pizza'\n"
                "→ fetch_mongodb_conversations(\n"
                "    since='2025-11-02T00:00:00Z',\n"
                "    query_filter={'messages.content': {'$regex': 'pizza', '$options': 'i'}}\n"
                "  )\n\n"
                "User: 'Most recent conversation with a video URL'\n"
                "→ fetch_mongodb_conversations(\n"
                "    query_filter={'messages.content': {'$regex': '\\\\.(mp4|mov)', '$options': 'i'}},\n"
                "    limit=1\n"
                "  )\n\n"
                "User: 'Conversations with storage.googleapis.com links from Oct 17'\n"
                "→ fetch_mongodb_conversations(\n"
                "    since='2025-10-17T00:00:00Z',\n"
                "    until='2025-10-17T23:59:59Z',\n"
                "    query_filter={'messages.content': {'$regex': 'storage\\\\.googleapis\\\\.com'}}\n"
                "  )\n\n"
                "## Data Structure:\n"
                "- Conversation doc: {_id, chat_session_created_at, last_updated_at, messages: []}\n"
                "- Message: {role: 'user'|'assistant'|'system', content: string}\n"
                "- Timestamps: ISO 8601 format with timezone\n\n"
                "## Remember:\n"
                "1. ALWAYS use query_filter for content-based searches\n"
                "2. Let MongoDB do the filtering, not your code\n"
                "3. Use reasonable limits for performance\n"
                "4. Combine parameters: query_filter + since + limit together\n"
                "5. Explain results clearly to the user"
            )
        }
    ] + history + [{"role": "user", "content": message}]
    
    # Ask the AI
    response = client.chat.completions.create(
        model="gpt-5-2025-08-07",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto"
    )
    
    ai_message = response.choices[0].message
    
    # If AI wants to use tools
    if hasattr(ai_message, 'tool_calls') and ai_message.tool_calls:
        # Record AI's message
        messages.append({
            "role": "assistant",
            "content": ai_message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                } for tc in ai_message.tool_calls
            ]
        })
        
        # Execute each tool
        for tc in ai_message.tool_calls:
            func_name = tc.function.name
            args = json.loads(tc.function.arguments)
            
            # Call the right function
            try:
                if func_name == "fetch_firebase_images":
                    result = fetch_firebase_images(**args)
                elif func_name == "fetch_firebase_image_by_url":
                    result = fetch_firebase_image_by_url(**args)
                elif func_name == "fetch_mongodb_conversations":
                    result = fetch_mongodb_conversations(**args)
                elif func_name == "fetch_conversation_by_id":
                    result = fetch_conversation_by_id(**args)
                elif func_name == "analyze_image_url":
                    result = analyze_image_url(**args)
                else:
                    result = {"error": "Unknown function"}
                
                # Make sure result is JSON-safe
                result = make_json_safe(result)
                
            except Exception as e:
                result = {"error": str(e)}
            
            # Send result back to AI
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result)
            })
        
        # Get final response
        final = client.chat.completions.create(
            model="gpt-5-2025-08-07",
            messages=messages
        )
        
        return final.choices[0].message.content
    
    return ai_message.content


if __name__ == "__main__":
    print("Chat with the agent. Type 'quit' to exit.")
    print("Try asking: 'What was the most recent conversation?'")
    print("Or: 'Check this Firebase URL for metadata: ...'")
    print("-" * 50)
    
    conversation = []
    
    while True:
        user_input = input("\nYou: ").strip()
        
        if user_input.lower() in ['quit', 'exit']:
            break
        
        if not user_input:
            continue
        
        response = talk_to_agent(user_input, conversation)
        print(f"\nAgent: {response}")
        
        # Update conversation history
        conversation.append({"role": "user", "content": user_input})
        conversation.append({"role": "assistant", "content": response})
