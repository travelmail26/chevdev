#!/usr/bin/env python3
"""
dictionary_builder.py

Takes a folder of conversation JSON files and extracts structured cooking events.
Uses parallel LLM calls for speed.

This creates a "dictionary" - a structured list of all cooking experiences
that the main bot can reference without losing track of items.

Usage:
    Called by recipe_bot.py, not directly.
"""

import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI


# -----------------------------
# Configuration
# -----------------------------
EXTRACT_MODEL = "gpt-5-nano-2025-08-07"  # Fast, cheap model for extraction
MAX_WORKERS = 8                # Parallel LLM calls


# -----------------------------
# The extraction prompt
# -----------------------------
# We tell the LLM exactly what to look for and how to format it.

EXTRACTION_PROMPT = """
You are extracting cooking events from a chat conversation.

Look for any mention of:
- Temperatures used for cooking
- Cooking methods (sautéing, roasting, caramelizing, etc.)
- Equipment or setup used (stovetop, water bath, jar-in-pot, sous vide, blender, etc.)
- Ingredients being cooked
- Outcomes or results (browned nicely, burned, etc.)

For each cooking event you find, output a JSON object with these fields:
- date: when it happened (if mentioned)
- temperature: the temperature used (if mentioned)
- method: how it was cooked
- equipment: tools or setup used (if mentioned)
- ingredient: what was cooked
- outcome: how it turned out
- quote: a short excerpt from the conversation as evidence

Equipment guidance:
- If the quote mentions tools or setup (pan, pot, bowl, jar, water bath, stovetop, blender, sous vide),
  fill in equipment even if the user didn't explicitly call it "equipment".

Return a JSON array of events. If no cooking events found, return [].

Example output:
[
  {{
    "date": "2024-03-15",
    "temperature": "325°F",
    "method": "roasted",
    "equipment": "sheet pan in a home oven",
    "ingredient": "onions",
    "outcome": "nicely caramelized",
    "quote": "I roasted the onions at 325 and they came out perfect"
  }}
]

USER'S QUESTION: {question}

CONVERSATION TO ANALYZE:
{conversation}

Return ONLY the JSON array, no other text.
"""


# -----------------------------
# Helper functions
# -----------------------------

def format_conversation(session):
    """
    Turn a session's messages into readable text for the LLM.
    """
    lines = []
    session_id = session.get("session_id", "unknown")
    
    for msg in session.get("messages", []):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        lines.append(f"[{role}]: {content}")
    
    return f"Session ID: {session_id}\n" + "\n".join(lines)


def load_session(session_path):
    """
    Read a single session JSON file from disk.
    """
    with open(session_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def list_session_files(sessions_dir):
    """
    List session JSON files in a folder.
    """
    names = [name for name in os.listdir(sessions_dir) if name.endswith(".json")]
    return [os.path.join(sessions_dir, name) for name in sorted(names)]


def extract_events_from_session(client, session_path, question):
    """
    Send one conversation to the LLM and get back structured events.
    """
    session = load_session(session_path)
    conversation_text = format_conversation(session)
    session_id = session.get("session_id", "unknown")
    
    print(f"  [extractor] Processing session: {session_id}")
    
    try:
        prompt = EXTRACTION_PROMPT.format(
            question=question,
            conversation=conversation_text
        )

        # Before: force temperature=0 for deterministic output.
        # After: omit temperature to use the model default (required by gpt-5-nano).
        response = client.chat.completions.create(
            model=EXTRACT_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Try to parse the JSON
        # Sometimes the LLM wraps it in ```json```, so clean that up
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        
        events = json.loads(result_text)

        # Fill missing equipment from quotes/methods when it's obvious.
        # Before: "pan on heat" -> equipment="" ; After: equipment="pan/stovetop".
        # Before: "jar in water bath" -> equipment="" ; After: equipment="jar in water bath".
        equipment_keywords = [
            ("water bath", "water bath"),
            ("bain", "bain-marie"),
            ("double boiler", "double boiler"),
            ("stovetop", "stovetop"),
            ("pan", "pan"),
            ("saucepan", "saucepan"),
            ("pot", "pot"),
            ("bowl", "bowl"),
            ("jar", "jar"),
            ("blender", "blender"),
            ("immersion blender", "immersion blender"),
            ("sous vide", "sous vide"),
            ("oven", "oven"),
            ("sheet pan", "sheet pan"),
        ]
        for event in events:
            if event.get("equipment"):
                continue
            haystack = " ".join(
                str(event.get(field, "")) for field in ["quote", "method", "outcome"]
            ).lower()
            found = []
            for needle, label in equipment_keywords:
                if needle in haystack:
                    found.append(label)
            if found:
                event["equipment"] = ", ".join(sorted(set(found)))
        
        # Add session_id to each event for traceability
        for event in events:
            event["session_id"] = session_id
        
        print(f"  [extractor] Found {len(events)} events in session {session_id}")
        return events
        
    except Exception as e:
        print(f"  [extractor] Error processing session {session_id}: {e}")
        return []


# -----------------------------
# Main function
# -----------------------------

def build_dictionary(sessions_dir, question):
    """
    Process all sessions in parallel and return a combined list of events.
    
    Args:
        sessions_dir: Temp folder with one JSON file per session
        question: The user's original question (guides what to extract)
    
    Returns:
        List of all extracted cooking events
    """
    if not os.path.isdir(sessions_dir):
        print(f"[dictionary_builder] Missing sessions dir: {sessions_dir}")
        return []

    session_files = list_session_files(sessions_dir)

    print(f"[dictionary_builder] Building dictionary from {len(session_files)} sessions")
    print(f"[dictionary_builder] Question: {question}")
    print(f"[dictionary_builder] Using {MAX_WORKERS} parallel workers")
    
    client = OpenAI()
    all_events = []
    
    # Before: pass session dicts directly to the extractor.
    # After: pass file paths and load each session on demand.
    # Process sessions in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        future_to_session = {
            executor.submit(extract_events_from_session, client, session_path, question): session_path
            for session_path in session_files
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_session):
            events = future.result()
            all_events.extend(events)
    
    print(f"[dictionary_builder] Total events extracted: {len(all_events)}")
    
    # Remove obvious duplicates (same session + same quote)
    seen = set()
    unique_events = []
    for event in all_events:
        key = (event.get("session_id"), event.get("quote", "")[:50])
        if key not in seen:
            seen.add(key)
            unique_events.append(event)
    
    print(f"[dictionary_builder] After deduplication: {len(unique_events)} events")
    
    return unique_events


# -----------------------------
# For testing standalone
# -----------------------------

if __name__ == "__main__":
    # Test with dummy data
    test_sessions = [
        {
            "session_id": "test-1",
            "messages": [
                {"role": "user", "content": "I cooked onions at 350°F today and they turned out great!"},
                {"role": "assistant", "content": "That sounds delicious!"}
            ]
        }
    ]

    temp_dir = tempfile.mkdtemp(prefix="recipebot_test_sessions_")
    test_path = os.path.join(temp_dir, "session_0001_test-1.json")
    with open(test_path, "w", encoding="utf-8") as handle:
        json.dump(test_sessions[0], handle)

    events = build_dictionary(temp_dir, "What temperatures were used to cook onions?")
    print(json.dumps(events, indent=2))
