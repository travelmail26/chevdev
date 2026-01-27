#!/usr/bin/env python3
"""
recipe_bot.py

A cooking history bot that answers questions about past cooking experiences
by searching conversations and extracting structured data.

Environment variables needed:
    MONGODB_URI    - Your MongoDB connection string
    OPENAI_API_KEY - Your OpenAI API key

Usage:
    python recipe_bot.py "List all temperatures where onions were caramelized"
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone

from pymongo import MongoClient
from openai import OpenAI

from dictionary_builder import build_dictionary


# =============================================================================
# BOT CONFIGURATION
# =============================================================================

BOT_MODEL = "gpt-5-2025-08-07"  # The model that runs the bot logic
QUERY_STOPWORDS = {
    "temperature",
    "temperatures",
    "temp",
    "degree",
    "degrees",
    "heat",
    "heating",
    "cook",
    "cooking",
    "method",
    "methods"
}

CACHE_DB_NAME = "chef_chatbot"
CACHE_COLLECTION_NAME = "cook_events_cache"
CACHE_TTL_HOURS = 12
EMBEDDING_LIMIT = 25

LAST_SEARCH_QUERY = None
CACHE_INDEX_READY = False


# =============================================================================
# BOT INSTRUCTIONS
# =============================================================================
# This is the system prompt that tells the LLM what it is and how to behave.
# It's written TO the LLM, explaining its identity, tools, and workflow.

BOT_INSTRUCTIONS = """
You are RecipeBot, a cooking history assistant.

## What You Are

You help users answer questions about their past cooking experiences. The user
has had many conversations about cooking (temperatures, methods, outcomes, etc.)
stored in a MongoDB database. Your job is to search those conversations, extract
the relevant information, and provide complete answers.

## Why You Exist

Users often ask things like "What temperature did I cook onions at?" but the
answer might be scattered across dozens of conversations. A simple search isn't
enough because:
1. Conversations are long and contain lots of irrelevant text
2. The same topic might come up in many different conversations
3. LLMs (including you) can lose track of items in very long lists

So we use a two-step approach:
1. First, search for relevant conversations
2. Then, extract structured data from each conversation into a "dictionary"
3. Finally, compile the complete answer from the dictionary

This ensures we never miss anything.

## Your Tools

You have 3 tools available:

### 1. search_conversations
Searches MongoDB for conversations matching a text query.
It always runs a $text search first, then a vector search with the SAME single-word query.

Parameters:
- query (string): A MongoDB $text search query
  - Words are ORed together (more words = more results)
  - Use ONE keyword only (single word)
  - Prefix with minus to exclude: "-soup" excludes soup

Returns: A JSON object with a temp folder path of matching conversation sessions

Example:
  search_conversations(query="onions -soup")

### 2. build_dictionary
Takes the search results and extracts structured cooking events from each
conversation using parallel LLM calls.

Parameters:
- sessions_dir (string): Path to a temp folder of session JSON files
- question (string): The user's original question (guides what to extract)

Returns: A JSON object with:
- cache_id: saved events for follow-up questions
- count: number of extracted events
- summary: short, readable summary for the user

Example:
  build_dictionary(sessions_dir="/tmp/recipebot_sessions_abc", question="What temps for onions?")

### 3. load_dictionary
Loads cached events by cache_id for follow-up questions.

Parameters:
- cache_id (string): The cache_id from build_dictionary
- contains (string, optional): Filter to events containing a keyword

Returns: A JSON object with matching cached events

## Your Workflow

For EVERY user question, follow these steps IN ORDER:

### Step 1: Convert the question to a search query
Think about what keywords would appear in relevant conversations.
- Use ONE keyword only (single word)
- Avoid generic words like temperature/degree unless nothing else works
- Note any exclusions the user mentioned

### Step 2: Call search_conversations
Use your search query to find relevant conversations.
This tool always runs lexical search first, then embedding search with the same word.
If no results, try broader terms.

### Step 3: Call build_dictionary
Pass the temp folder path and the original question.
This extracts structured events from all conversations in parallel and saves them.

### Step 4: Compile your answer
Use the summary from build_dictionary.
- Keep it short; do NOT list every event by default
- Mention the cache_id so follow-up questions can load details

### Step 4a: Match solution type to the user's question
Map the answer to what the user is asking about:
- If the question is about ingredients, emphasize ingredient-based results.
- If the question is about equipment or setup, emphasize equipment/technique.
- If the question is about cooking technique, emphasize method/steps.

Search keywords are often ingredient-based when an ingredient is mentioned.
Then, use the extracted dictionary to map the solution to the user's actual need.

Example (not related to eggs/onions/hollandaise):
User: "I want crispy salmon skin but only have a microwave. Can I do it?"
You should: search for "salmon", then answer with the technique/equipment angle
(e.g., microwave limitations, alternative stovetop steps from past notes).

If equipment isn't explicitly structured, look at evidence quotes and method text
to infer the setup (pan, pot, bowl, jar, water bath, stovetop, etc.).

### Step 5: Follow-up questions
If the user asks for details, call load_dictionary(cache_id, contains=keyword) and answer from those events.

## Example Interaction

User: "List all temperatures where onions were caramelized; exclude soup"

Your thinking:
- Keywords: onions
- Exclude: soup
- Search query: "onions -soup"

You call: search_conversations(query="onions -soup")
Result: 8 conversations found

You call: build_dictionary(sessions_dir="/tmp/recipebot_sessions_abc", question="List all temperatures...")
Result: 12 cooking events extracted + cache_id saved

Your answer:
"I found 12 caramelization events. Common temps are 300°F, 325°F, and medium-low.
Cache ID: abc123 (ask for details or specific ranges)."

## Important Rules

1. ALWAYS use tools - never try to answer from memory
2. ALWAYS call search_conversations first, then build_dictionary
3. Keep search queries to 1 keyword only (single word, no phrases)
4. If search returns nothing, try broader search terms before giving up
5. Do NOT dump all events by default; summarize and provide cache_id
"""


# =============================================================================
# TOOL DEFINITIONS (OpenAI Function Calling Format)
# =============================================================================
# These define what tools the LLM can call and their parameters.

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_conversations",
            "description": "Search MongoDB for conversations matching a text query. Runs lexical then embedding search with the same word.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "MongoDB $text search query. Words are ORed. Use 1 keyword only. Use -word to exclude. Example: 'onions -soup'"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "build_dictionary",
            "description": "Extract structured cooking events from conversations. Call this AFTER search_conversations to get detailed event data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sessions_dir": {
                        "type": "string",
                        "description": "Path to a temp folder of session JSON files returned by search_conversations"
                    },
                    "question": {
                        "type": "string",
                        "description": "The user's original question - guides what information to extract"
                    }
                },
                "required": ["sessions_dir", "question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "load_dictionary",
            "description": "Load cached cooking events by cache_id for follow-up questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cache_id": {
                        "type": "string",
                        "description": "cache_id returned by build_dictionary"
                    },
                    "contains": {
                        "type": "string",
                        "description": "Optional keyword filter (case-insensitive substring match)"
                    }
                },
                "required": ["cache_id"]
            }
        }
    }
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def normalize_search_query(raw_query):
    """
    Reduce a search query to 1 keyword to avoid OR explosion.
    Example before/after:
      "onion caramelized temperature -soup" -> "onion -soup"
    """
    query = (raw_query or "").strip()
    if not query:
        return ""

    exclusions = re.findall(r"-(\S+)", query)
    tokens = [tok for tok in re.split(r"\s+", query) if tok]
    fallback = ""
    core = ""

    for token in tokens:
        if token.startswith("-"):
            continue
        cleaned = token.strip("\"").strip()
        if not cleaned:
            continue
        if cleaned.lower() in QUERY_STOPWORDS and not re.search(r"[\d°]", cleaned):
            if not fallback:
                fallback = cleaned
            continue
        core = cleaned
        break

    if not core and fallback:
        core = fallback

    if core and exclusions:
        return f"{core} " + " ".join(f"-{word}" for word in exclusions)
    if core:
        return core
    if exclusions:
        return " ".join(f"-{word}" for word in exclusions)
    return query


def get_cache_collection():
    """
    Get the Mongo collection for cached events.
    """
    global CACHE_INDEX_READY

    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        return None

    client = MongoClient(mongo_uri)
    collection = client[CACHE_DB_NAME][CACHE_COLLECTION_NAME]

    if not CACHE_INDEX_READY:
        ttl_seconds = int(CACHE_TTL_HOURS * 3600)
        collection.create_index("cache_id", unique=True)
        collection.create_index("created_at", expireAfterSeconds=ttl_seconds)
        CACHE_INDEX_READY = True

    return collection


def save_events_to_cache(events, question, search_query):
    """
    Save extracted events so follow-up questions can reuse them.
    """
    collection = get_cache_collection()
    if collection is None:
        print("  [cache] Missing MONGODB_URI; skipping cache")
        return None

    cache_id = str(uuid.uuid4())
    doc = {
        "cache_id": cache_id,
        "created_at": datetime.now(timezone.utc),
        "question": question,
        "search_query": search_query,
        "event_count": len(events),
        "events": events
    }
    collection.insert_one(doc)
    return cache_id


def load_events_from_cache(cache_id, contains=None):
    """
    Load cached events, optionally filtered by a keyword.
    """
    collection = get_cache_collection()
    if collection is None:
        return []

    doc = collection.find_one({"cache_id": cache_id})
    if not doc:
        return []

    events = doc.get("events", [])
    if not contains:
        return events

    keyword = str(contains).lower()
    filtered = []
    for event in events:
        haystack = " ".join(
            str(event.get(field, "")) for field in [
                "date",
                "temperature",
                "method",
                "ingredient",
                "outcome",
                "quote"
            ]
        ).lower()
        if keyword in haystack:
            filtered.append(event)

    return filtered


def build_events_summary(events):
    """
    Build a short summary so we don't dump full lists by default.
    """
    temperatures = []
    methods = []
    equipment = []
    ingredients = []

    for event in events:
        temperature = event.get("temperature")
        method = event.get("method")
        tool_used = event.get("equipment")
        ingredient = event.get("ingredient")
        if temperature:
            temperatures.append(str(temperature))
        if method:
            methods.append(str(method))
        if tool_used:
            equipment.append(str(tool_used))
        if ingredient:
            ingredients.append(str(ingredient))

    unique_temperatures = sorted(set(temperatures))
    unique_methods = sorted(set(methods))
    unique_equipment = sorted(set(equipment))
    unique_ingredients = sorted(set(ingredients))

    # Prefer sample events that show equipment/technique in quotes or method.
    # Before: first 5 events could miss setup; After: pick up to 5 with setup clues.
    sample_events = []
    hint_keywords = [
        "double boiler", "bain", "water bath", "stovetop", "pan",
        "pot", "bowl", "jar", "blender", "sous vide", "oven"
    ]
    for event in events:
        quote = str(event.get("quote") or "")
        method = str(event.get("method") or "")
        equipment_text = str(event.get("equipment") or "")
        haystack = f"{quote} {method} {equipment_text}".lower()
        if any(word in haystack for word in hint_keywords):
            sample_events.append(event)
        if len(sample_events) >= 5:
            break

    if len(sample_events) < 5:
        for event in events:
            if event in sample_events:
                continue
            sample_events.append(event)
            if len(sample_events) >= 5:
                break

    return {
        "event_count": len(events),
        "unique_temperatures_count": len(unique_temperatures),
        "unique_temperatures_sample": unique_temperatures[:10],
        "unique_methods_sample": unique_methods[:8],
        "unique_equipment_sample": unique_equipment[:8],
        "unique_ingredients_sample": unique_ingredients[:8],
        "sample_events": sample_events
    }


def merge_session_dirs(session_dirs):
    """
    Merge session JSON files by session_id into a new temp folder.
    Example before/after:
      two dirs with duplicate session_id -> one dir with unique session files
    """
    merged_dir = tempfile.mkdtemp(prefix="recipebot_sessions_merged_")
    seen = set()
    count = 0

    for sessions_dir in session_dirs:
        if not sessions_dir or not os.path.isdir(sessions_dir):
            continue
        for name in sorted(os.listdir(sessions_dir)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(sessions_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    session = json.load(handle)
            except Exception:
                continue

            session_id = str(session.get("session_id") or session.get("_id") or "")
            if not session_id or session_id in seen:
                continue

            safe_id = session_id.replace("/", "_").replace("\\", "_")
            out_name = f"session_{count:04d}_{safe_id}.json"
            out_path = os.path.join(merged_dir, out_name)
            with open(out_path, "w", encoding="utf-8") as handle:
                json.dump(session, handle)

            seen.add(session_id)
            count += 1

    return merged_dir, count


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================
# These are the actual Python functions that execute when the LLM calls a tool.

def tool_search_conversations(query):
    """
    Search MongoDB for relevant conversations.
    Calls mongo_worker.py, then mongo_worker_embedding.py (mandatory sequence).
    """
    global LAST_SEARCH_QUERY

    print(f"\n[TOOL] search_conversations")

    trimmed_query = normalize_search_query(query)
    if trimmed_query and trimmed_query != query:
        print(f"  Raw Query: {query}")
        print(f"  Trimmed Query: {trimmed_query}")
        query = trimmed_query
    else:
        print(f"  Query: {query}")
    
    # Call the worker script (use this folder so relative paths work)
    script_dir = os.path.dirname(__file__)
    worker_path = os.path.join(script_dir, "mongo_worker.py")
    embedding_worker_path = os.path.join(script_dir, "mongo_worker_embedding.py")
    payload = json.dumps({"query": query})
    result = subprocess.run(
        ["python", worker_path],
        input=payload,
        capture_output=True,
        text=True,
        cwd=script_dir
    )
    
    if result.returncode != 0:
        error_msg = f"MongoDB search failed: {result.stderr}"
        print(f"  Error: {error_msg}")
        return {"error": error_msg, "sessions": []}
    
    data = json.loads(result.stdout)
    
    if "error" in data:
        print(f"  Error: {data['error']}")
        return data
    
    sessions_dir = data.get("sessions_dir")
    count = data.get("count", 0)
    LAST_SEARCH_QUERY = query
    print(f"  Lexical found: {count} conversations")
    print(f"  Lexical dir: {sessions_dir}")

    embed_dir = None
    embed_count = 0

    # Mandatory embedding step with the same single-word query.
    embed_result = subprocess.run(
        ["python", embedding_worker_path],
        input=json.dumps({"query": query, "limit": EMBEDDING_LIMIT}),
        capture_output=True,
        text=True,
        cwd=script_dir
    )

    if embed_result.returncode != 0:
        print(f"  Embedding error: {embed_result.stderr}")
    else:
        try:
            embed_data = json.loads(embed_result.stdout)
        except json.JSONDecodeError as e:
            print(f"  Embedding error: invalid JSON ({e})")
            embed_data = {}

        if "error" in embed_data:
            print(f"  Embedding error: {embed_data['error']}")
        else:
            embed_dir = embed_data.get("sessions_dir")
            embed_count = embed_data.get("count", 0)
            print(f"  Embedding found: {embed_count} conversations")
            print(f"  Embedding dir: {embed_dir}")

    merged_dir, merged_count = merge_session_dirs([sessions_dir, embed_dir])
    print(f"  Merged: {merged_count} unique conversations")
    print(f"  Merged dir: {merged_dir}")

    # Before: pass full sessions JSON to the LLM in tool args.
    # After: pass a folder path to the on-disk sessions to save tokens.
    return {
        "sessions_dir": merged_dir,
        "count": merged_count,
        "lexical_count": count,
        "embedding_count": embed_count,
        "query": query
    }


def tool_build_dictionary(sessions_dir, question):
    """
    Extract structured cooking events from conversations.
    Uses parallel LLM calls via dictionary_builder.py.
    """
    print(f"\n[TOOL] build_dictionary")
    print(f"  Question: {question}")
    
    if not sessions_dir:
        error_msg = "Missing sessions_dir"
        print(f"  Error: {error_msg}")
        return {"error": error_msg, "events": []}

    print(f"  Sessions dir: {sessions_dir}")

    # Call the dictionary builder
    events = build_dictionary(sessions_dir, question)
    
    print(f"  Extracted: {len(events)} cooking events")

    cache_id = save_events_to_cache(events, question, LAST_SEARCH_QUERY)
    if cache_id:
        print(f"  Cached: {cache_id}")
    else:
        print("  Cached: skipped")

    summary = build_events_summary(events)

    return {
        "cache_id": cache_id,
        "count": len(events),
        "summary": summary
    }


def tool_load_dictionary(cache_id, contains=None):
    """
    Load cached events for follow-up questions.
    """
    print(f"\n[TOOL] load_dictionary")
    print(f"  Cache ID: {cache_id}")
    if contains:
        print(f"  Filter: {contains}")

    events = load_events_from_cache(cache_id, contains=contains)
    print(f"  Loaded: {len(events)} events")

    return {
        "cache_id": cache_id,
        "count": len(events),
        "events": events
    }


# Map tool names to functions
TOOL_FUNCTIONS = {
    "search_conversations": tool_search_conversations,
    "build_dictionary": tool_build_dictionary,
    "load_dictionary": tool_load_dictionary
}


# =============================================================================
# BOT RUNNER
# =============================================================================
# This handles the conversation loop, calling tools when the LLM requests them.

def run_bot(question):
    """
    Run the bot with a user question.
    Handles the tool-calling loop until the LLM provides a final answer.
    """
    print("\n" + "=" * 70)
    print("RECIPE BOT")
    print("=" * 70)
    print(f"User Question: {question}")
    print("=" * 70)
    
    client = OpenAI()
    
    # Start the conversation
    messages = [
        {"role": "system", "content": BOT_INSTRUCTIONS},
        {"role": "user", "content": question}
    ]
    
    # Tool-calling loop
    max_iterations = 10  # Safety limit
    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration + 1} ---")
        
        # Call the LLM
        response = client.chat.completions.create(
            model=BOT_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto"  # Let the LLM decide when to use tools
        )
        
        assistant_message = response.choices[0].message
        
        # Check if the LLM wants to call tools
        if assistant_message.tool_calls:
            # Add the assistant's message (with tool calls) to history
            messages.append(assistant_message)
            
            # Execute each tool call
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                print(f"\n[BOT] Calling tool: {function_name}")
                print(f"  Arguments: {json.dumps(function_args, indent=2)[:200]}...")
                
                # Execute the tool
                if function_name in TOOL_FUNCTIONS:
                    result = TOOL_FUNCTIONS[function_name](**function_args)
                else:
                    result = {"error": f"Unknown tool: {function_name}"}
                
                # Add the tool result to the conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })
        
        else:
            # No tool calls - the LLM is providing its final answer
            final_answer = assistant_message.content
            print("\n" + "=" * 70)
            print("FINAL ANSWER")
            print("=" * 70)
            return final_answer
    
    return "Error: Maximum iterations reached without a final answer."


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    # Get question from command line or use default
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = "I want to make hollandaise, but don't have a double boiler. Can I do that? How?"
    
    answer = run_bot(question)
    print(answer)


if __name__ == "__main__":
    main()
