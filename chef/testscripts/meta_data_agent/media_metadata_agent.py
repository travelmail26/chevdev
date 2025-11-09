#!/usr/bin/env python3
"""
Ultra-Minimal Media Capture Agent
==================================
The agent is smart - it just needs access to data.
MongoDB = conversations (using mongo_simple)
Firebase = images with metadata
"""

import json
import sys
import os
from openai import OpenAI

# Make sure we can import the other scripts
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import the actual functions from the other files
import firebase_manual_agent
import mongo_simple
import mongo_media


def analyze_image_url(url):
    """
    Analyze an image from a URL using OpenAI Vision.
    Works with Firebase, Google Storage, or any publicly accessible image URL.
    """
    client = OpenAI()

    prompt = "What's in this image? Describe it in detail. " \
        "Focus on the food and cooking. What is the food? " \
        "What is it's color or texture or arrangement? " \
        "Any relevant numbers, equipment or anything relevant to cooking approach or how the food is cooked." \
        "Do not make any recommendations or suggestions related to cooking or health"

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
            "name": "get_recent_images_from_firebase",
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
            "name": "get_specific_image_url",
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
            "name": "query_chats",
            "description": "Get conversations from MongoDB using mongo_simple. Translates plain language into MongoDB calls. ALWAYS filter at the database level, never fetch all and filter in code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content_search": {"type": "string", "description": "Optional: Search for text in message content (case-insensitive). Example: 'pizza' finds messages containing 'pizza'."},
                    "limit": {"type": "integer", "description": "Optional: max number of conversations to return. Always set a reasonable limit (10-20) for performance."},
                    "created_since": {"type": "string", "description": "Optional: ISO timestamp - get conversations created OR updated after this time (e.g., '2025-11-06T00:00:00Z'). ALWAYS use this for date queries."},
                    "created_until": {"type": "string", "description": "Optional: ISO timestamp - get conversations created OR updated before this time"},
                    "sort_by": {"type": "string", "description": "Optional: field to sort by. Default is 'last_updated_at' (descending/newest first). Use '-' prefix for ascending."},
                    "query_filter": {
                        "type": "object",
                        "description": "Optional: MongoDB query object for advanced filtering. Use MongoDB query operators. Examples: {'messages.content': {'$regex': 'https://'}} for URLs, {'messages.role': 'user'} for user messages only."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_chat_messages",
            "description": "Get all messages from a specific conversation using its ID",
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
            "description": "Analyze an image from a URL using OpenAI Vision. Use this when asked to evaluate, assess, or analyze an image URL from Firebase, Google Storage, or any other source. Provides detailed food and cooking analysis without recommendations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The image URL to analyze (Firebase, Google Storage, or any public URL)"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "store_media_description",
            "description": "Store a media URL with its description in MongoDB media_metadata collection. Use this after analyzing an image to save the description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The media URL"},
                    "description": {"type": "string", "description": "The description of the media content"}
                },
                "required": ["url", "description"]
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
    print(f"\n→ Query: {message}")
    print("→ Processing...")

    client = OpenAI()

    if history is None:
        history = []

    # Build conversation
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant with access to conversation and media data.\n"
                "You translate plain language queries into MongoDB function calls using mongo_simple.\n\n"

                "## CRITICAL: Use Database-Level Filtering\n"
                "**ALWAYS filter at the MongoDB level. NEVER fetch all conversations and filter in code.**\n\n"

                "## Available Data Sources\n"
                "1. **MongoDB (via mongo_simple)**: Full conversation history\n"
                "2. **Firebase**: Images/videos with metadata\n"
                "3. **OpenAI Vision**: Analyze image content from URLs\n"
                "4. **Media Metadata Storage**: Store URL descriptions in media_metadata collection\n\n"

                "## Media Description Workflow\n"
                "When asked to describe/analyze and save/store a media URL:\n\n"
                "**OPTION 1 - User provided description:**\n"
                "If the user already provided a description in the conversation (e.g., 'This is chicken soup' or 'Here's my pasta dish'):\n"
                "1. Use the user's description directly\n"
                "2. Call store_media_description(url, user_description)\n\n"
                "**OPTION 2 - No user description:**\n"
                "If the user did NOT provide a description:\n"
                "1. FIRST: Call analyze_image_url(url) to get AI-generated description\n"
                "2. SECOND: Call store_media_description(url, ai_description)\n\n"
                "**IMPORTANT:** You must actually CALL the functions - don't just say you will!\n"
                "**IMPORTANT:** Check conversation history for user descriptions before calling analyze_image_url!\n\n"

                "## Translating Plain Language to MongoDB Calls\n\n"

                "### Simple Text Search - Use content_search parameter:\n"
                "User: 'Find conversations about pizza'\n"
                "→ query_chats(content_search='pizza', limit=10)\n\n"

                "User: 'Show chats mentioning chicken'\n"
                "→ query_chats(content_search='chicken', limit=20)\n\n"

                "### Advanced Filtering - Use query_filter parameter:\n"
                "User: 'Find conversations with URLs'\n"
                "→ query_chats(\n"
                "    query_filter={'messages.content': {'$regex': 'https?://', '$options': 'i'}},\n"
                "    limit=20\n"
                "  )\n\n"

                "User: 'Show chats with video files'\n"
                "→ query_chats(\n"
                "    query_filter={'messages.content': {'$regex': '\\\\.(mp4|mov|avi)', '$options': 'i'}},\n"
                "    limit=10\n"
                "  )\n\n"

                "User: 'Find user messages only'\n"
                "→ query_chats(\n"
                "    query_filter={'messages.role': 'user'},\n"
                "    limit=10\n"
                "  )\n\n"

                "### Time-Based Filtering - ALWAYS use created_since/created_until parameters (NOT query_filter):\n"
                "User: 'Show conversations from today'\n"
                "→ query_chats(\n"
                "    created_since='2025-11-07T00:00:00Z',\n"
                "    limit=20\n"
                "  )\n\n"

                "User: 'Find chats from October 17th'\n"
                "→ query_chats(\n"
                "    created_since='2025-10-17T00:00:00Z',\n"
                "    created_until='2025-10-17T23:59:59Z',\n"
                "    limit=20\n"
                "  )\n\n"

                "User: 'Conversations updated today'\n"
                "→ query_chats(\n"
                "    created_since='2025-11-07T00:00:00Z',\n"
                "    limit=20\n"
                "  )\n\n"

                "### Combining Filters:\n"
                "User: 'Show me today\\'s chats about pizza'\n"
                "→ query_chats(\n"
                "    content_search='pizza',\n"
                "    created_since='2025-11-07T00:00:00Z',\n"
                "    limit=10\n"
                "  )\n\n"

                "User: 'Most recent conversation with a Firebase URL'\n"
                "→ query_chats(\n"
                "    query_filter={'messages.content': {'$regex': 'storage\\\\.googleapis\\\\.com'}},\n"
                "    limit=1\n"
                "  )\n\n"

                "## Parameter Guide:\n\n"
                "**content_search**: Simple text search in messages (case-insensitive)\n"
                "  - Use for: 'find pizza', 'chats about chicken', 'mentions recipe'\n\n"

                "**query_filter**: Advanced MongoDB queries\n"
                "  - Use for: URLs, specific roles, complex patterns\n"
                "  - MongoDB operators: $regex, $options, $gte, $lte\n"
                "  - Nested fields: 'messages.content', 'messages.role'\n\n"

                "**limit**: Max results to return\n"
                "  - 'most recent' → limit=1\n"
                "  - 'last 10' → limit=10\n"
                "  - Always set a reasonable limit for performance\n\n"

                "**created_since/created_until**: ISO timestamp for date filtering\n"
                "  - Format: '2025-11-07T00:00:00Z'\n"
                "  - ALWAYS use these for date queries (NOT query_filter)\n"
                "  - Searches BOTH created_at AND updated_at fields\n"
                "  - 'today' → created_since='2025-11-07T00:00:00Z'\n"
                "  - 'Oct 17' → created_since='2025-10-17T00:00:00Z', created_until='2025-10-17T23:59:59Z'\n\n"

                "**sort_by**: Field to sort by (default: newest first)\n\n"

                "## Data Structure:\n"
                "- Conversation: {_id, chat_session_created_at, last_updated_at, messages: []}\n"
                "- Message: {role: 'user'|'assistant'|'system', content: string}\n\n"

                "## CRITICAL Rules:\n"
                "1. For DATE queries: ALWAYS use created_since/created_until parameters (NOT query_filter)\n"
                "2. Use content_search for simple text queries\n"
                "3. Use query_filter ONLY for: URLs, specific roles, regex patterns\n"
                "4. Always set a reasonable limit (10-20) for performance\n"
                "5. Combine parameters: created_since + content_search + limit together"
            )
        }
    ] + history + [{"role": "user", "content": message}]

    # Ask the AI
    print("→ Calling OpenAI API...", flush=True)
    response = client.chat.completions.create(
        model="gpt-5-2025-08-07",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto"
    )
    
    ai_message = response.choices[0].message
    print("→ Received response from OpenAI")

    # If AI wants to use tools
    if hasattr(ai_message, 'tool_calls') and ai_message.tool_calls:
        print(f"→ Agent wants to call {len(ai_message.tool_calls)} function(s)")
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

            # Print function call
            args_str = ", ".join(f"{k}={repr(v)}" for k, v in args.items())
            print(f"→ {func_name}({args_str})")

            # Call the right function from the modules
            try:
                if func_name == "get_recent_images_from_firebase":
                    result = firebase_manual_agent.get_recent_images_from_firebase(**args)
                    # Remove blob objects (not JSON serializable)
                    if isinstance(result, list):
                        result = [{k: v for k, v in item.items() if k != 'blob'} for item in result]
                elif func_name == "get_specific_image_url":
                    result = firebase_manual_agent.get_specific_image_url(**args)
                    if result:
                        blob, public_url = result
                        result = {"url": public_url, "metadata": blob.metadata}
                elif func_name == "query_chats":
                    result = mongo_simple.query_chats(**args)
                elif func_name == "get_chat_messages":
                    result = mongo_simple.get_chat_messages(**args)
                elif func_name == "analyze_image_url":
                    result = analyze_image_url(**args)
                elif func_name == "store_media_description":
                    result = mongo_media.store_media_description(**args)
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
        
        # Get final response (allow for more tool calls)
        print("→ Getting final answer...", flush=True)
        final = client.chat.completions.create(
            model="gpt-5-2025-08-07",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto"
        )

        final_message = final.choices[0].message

        # Check if agent wants to make more tool calls
        if hasattr(final_message, 'tool_calls') and final_message.tool_calls:
            print(f"→ Agent wants to call {len(final_message.tool_calls)} more function(s)")
            messages.append({
                "role": "assistant",
                "content": final_message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    } for tc in final_message.tool_calls
                ]
            })

            # Execute additional tools
            for tc in final_message.tool_calls:
                func_name = tc.function.name
                args = json.loads(tc.function.arguments)

                args_str = ", ".join(f"{k}={repr(v)}" for k, v in args.items())
                print(f"→ {func_name}({args_str})")

                try:
                    if func_name == "get_recent_images_from_firebase":
                        result = firebase_manual_agent.get_recent_images_from_firebase(**args)
                        if isinstance(result, list):
                            result = [{k: v for k, v in item.items() if k != 'blob'} for item in result]
                    elif func_name == "get_specific_image_url":
                        result = firebase_manual_agent.get_specific_image_url(**args)
                        if result:
                            blob, public_url = result
                            result = {"url": public_url, "metadata": blob.metadata}
                    elif func_name == "query_chats":
                        result = mongo_simple.query_chats(**args)
                    elif func_name == "get_chat_messages":
                        result = mongo_simple.get_chat_messages(**args)
                    elif func_name == "analyze_image_url":
                        result = analyze_image_url(**args)
                    elif func_name == "store_media_description":
                        result = mongo_media.store_media_description(**args)
                    else:
                        result = {"error": "Unknown function"}

                    result = make_json_safe(result)

                except Exception as e:
                    result = {"error": str(e)}

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result)
                })

            # Get the truly final response
            print("→ Getting truly final answer...", flush=True)
            truly_final = client.chat.completions.create(
                model="gpt-5-2025-08-07",
                messages=messages
            )
            return truly_final.choices[0].message.content

        return final_message.content
    
    return ai_message.content


if __name__ == "__main__":
    print("Media Metadata Agent - Using mongo_simple for database queries")
    print("=" * 70)
    print("\nThis agent translates plain language into MongoDB function calls.")
    print("\nExample queries:")
    print("  - 'What was the most recent conversation?'")
    print("  - 'Find conversations about pizza'")
    print("  - 'Show me chats from today'")
    print("  - 'Find conversations with URLs'")
    print("  - 'Check this Firebase URL for metadata: ...'")
    print("  - 'Analyze this image: https://...'")
    print("  - 'Describe this URL and save it: https://...'")
    print("\nType 'quit' to exit.")
    print("-" * 70)
    
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
