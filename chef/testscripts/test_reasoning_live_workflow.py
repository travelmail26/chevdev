#!/usr/bin/env python3

"""
Live workflow test for advanced reasoning using real APIs.

This test drives MessageRouter end-to-end with:
- Perplexity search for croissant recipes
- Advanced reasoning to explore making multiple recipes
- Constraint collection (equipment, oven, mixer)
- Next-step guidance

It purposefully uses message_object (with only user_id in session_info) so that:
- Conversation history persists to chat_history_logs/<user>_history.json
- advanced_recipe_reasoning receives the full conversation history
- Telegram sending is skipped (no chat_id, so process_message_object returns early)

Requirements:
- Set environment variables OPENAI_API_KEY and PERPLEXITY_KEY.
- Network access must be available to reach OpenAI and Perplexity APIs.

Safeguards:
- If keys are missing, the test will skip.

Run:
- python chef/testscripts/test_reasoning_live_workflow.py
- or: pytest -q chef/testscripts/test_reasoning_live_workflow.py
"""

import os
import sys
import json
import time
from datetime import datetime


def _ensure_paths():
    # Add repo paths so we can import router and utilities consistently
    root = "/workspaces/chevdev/chef"
    chefmain = os.path.join(root, "chefmain")
    if root not in sys.path:
        sys.path.append(root)
    if chefmain not in sys.path:
        sys.path.append(chefmain)


_ensure_paths()

try:
    import pytest  # type: ignore
except Exception:  # pragma: no cover - pytest may not be installed in some environments
    pytest = None

from message_router import MessageRouter
from utilities.history_messages import get_full_history_message_object


def _skip_if_no_keys():
    missing = []
    if not os.environ.get("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if not os.environ.get("PERPLEXITY_KEY"):
        missing.append("PERPLEXITY_KEY")
    if missing:
        msg = f"Skipping live test; missing env vars: {', '.join(missing)}"
        if pytest:
            pytest.skip(msg)
        else:
            print(msg)
            sys.exit(0)


def _ensure_history_dir():
    # Ensure chat history directory exists (message_history_process does not create it)
    os.makedirs("chat_history_logs", exist_ok=True)


def _unique_user_id(prefix: str = "test_reasoning_live") -> str:
    return f"{prefix}_{int(time.time())}"


def _last_tool_name(history_messages):
    # Find most recent assistant message that contains a tool call
    for m in reversed(history_messages or []):
        if m.get("role") == "assistant" and m.get("tool_calls"):
            tc = m["tool_calls"][0]
            return tc.get("function", {}).get("name")
    return None


def _print_step(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80 + "\n")


def _trim(s: str, n: int = 600) -> str:
    return s if len(s) <= n else s[:n] + "..."


def _route(router: MessageRouter, user_id: str, user_message: str) -> str:
    message_object = {
        "user_id": user_id,
        # Intentionally omit chat_id to prevent Telegram sends in process_message_object
        "session_info": {"user_id": user_id},
        "user_message": user_message,
    }
    return router.route_message(message_object=message_object)


def test_reasoning_live_workflow():
    _skip_if_no_keys()
    _ensure_history_dir()

    router = MessageRouter()
    user_id = _unique_user_id()

    # Step 1: Search for croissant recipes (should choose search_perplexity)
    _print_step("STEP 1: Search for croissant recipes (Perplexity)")
    resp1 = _route(router, user_id, "search perplexity for croissant recipes for 2 different types of flour")
    print(_trim(resp1))
    history = get_full_history_message_object(user_id)
    tool1 = _last_tool_name(history.get("messages", []))
    print(f"Last tool used: {tool1}")

    # Expectations: non-empty response; tool is search_perplexity
    assert isinstance(resp1, str) and len(resp1.strip()) > 0, "Empty response for Step 1"
    assert tool1 == "search_perplexity", f"Expected search_perplexity, got {tool1}"

    # Step 2: Explore making both at the same time (should choose advanced_recipe_reasoning)
    _print_step("STEP 2: Explore making both at the same time (Advanced Reasoning)")
    resp2 = _route(router, user_id, "i'd like to explore making both of these at the same time")
    print(_trim(resp2))
    history = get_full_history_message_object(user_id)
    tool2 = _last_tool_name(history.get("messages", []))
    print(f"Last tool used: {tool2}")

    # Expectations: advanced reasoning engaged; context keywords present or reasonable follow-up
    assert isinstance(resp2, str) and len(resp2.strip()) > 0, "Empty response for Step 2"
    assert tool2 == "advanced_recipe_reasoning", f"Expected advanced_recipe_reasoning, got {tool2}"

    # Step 3: Ask equipment (should continue with advanced reasoning due to continuity)
    _print_step("STEP 3: Ask equipment (Continuity with Advanced Reasoning)")
    resp3 = _route(router, user_id, "what equipment will i need?")
    print(_trim(resp3))
    history = get_full_history_message_object(user_id)
    tool3 = _last_tool_name(history.get("messages", []))
    print(f"Last tool used: {tool3}")

    assert isinstance(resp3, str) and len(resp3.strip()) > 0, "Empty response for Step 3"
    assert tool3 == "advanced_recipe_reasoning", f"Expected advanced_recipe_reasoning on continuity, got {tool3}"

    # Step 4: Provide constraints
    _print_step("STEP 4: Provide constraints (one oven, no stand mixer)")
    resp4 = _route(router, user_id, "i only have one oven and no stand mixer")
    print(_trim(resp4))
    history = get_full_history_message_object(user_id)
    tool4 = _last_tool_name(history.get("messages", []))
    print(f"Last tool used: {tool4}")

    assert isinstance(resp4, str) and len(resp4.strip()) > 0, "Empty response for Step 4"
    assert tool4 == "advanced_recipe_reasoning", f"Expected advanced_recipe_reasoning for constraints, got {tool4}"

    # Step 5: Ask for next steps
    _print_step("STEP 5: Ask for next steps")
    resp5 = _route(router, user_id, "what should i do next?")
    print(_trim(resp5))
    history = get_full_history_message_object(user_id)
    tool5 = _last_tool_name(history.get("messages", []))
    print(f"Last tool used: {tool5}")

    assert isinstance(resp5, str) and len(resp5.strip()) > 0, "Empty response for Step 5"
    assert tool5 == "advanced_recipe_reasoning", f"Expected advanced_recipe_reasoning for next steps, got {tool5}"

    # Light semantic checks for context awareness across steps
    combined = "\n".join([resp2, resp3, resp4, resp5]).lower()
    context_hits = any(k in combined for k in ["croissant", "flour", "equipment", "oven", "mixer", "schedule", "plan", "next"])
    assert context_hits, "Responses do not appear context-aware (keywords missing)"

    print("\nSUMMARY:")
    print("- ✓ Perplexity search executed with real API")
    print("- ✓ Advanced reasoning engaged and maintained via continuity")
    print("- ✓ Constraints incorporated and next steps provided")


if __name__ == "__main__":
    # Allow running directly without pytest
    try:
        test_reasoning_live_workflow()
    except SystemExit:
        pass
