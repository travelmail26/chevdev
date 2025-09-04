import os
import sys
import json


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "FAKE-ADV-RESPONSE"}}]}


def test_direct_advanced_reasoning_uses_instructions_and_history(monkeypatch):
    # Arrange: stub OpenAI call and capture payload
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured['url'] = url
        captured['json'] = json
        return _FakeResponse(json)

    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    monkeypatch.setattr('requests.post', fake_post)

    # Import the current advanced reasoning implementation used by the router (testscripts module)
    # Add repo root to path so 'chef' package resolves as a namespace package
    sys.path.append(os.getcwd())
    from chef.testscripts.advanced_recipe_reasoning import advanced_recipe_reasoning

    history = [
        {"role": "user", "content": "we found two croissant recipes"},
        {"role": "assistant", "content": "what equipment do you have?"},
        {"role": "user", "content": "stand mixer, oven; short on time"},
    ]

    # Act
    result = advanced_recipe_reasoning(conversation_history=history)

    # Assert: payload structure and that a system instruction was injected
    assert result == "FAKE-ADV-RESPONSE"
    assert captured['url'].endswith('/v1/chat/completions')
    payload = captured['json']
    assert payload['model'] == 'gpt-4o-mini'
    assert isinstance(payload['messages'], list)
    assert payload['messages'][0]['role'] == 'system'
    # System instruction present (may be fallback when testscripts/instructions is missing)
    assert isinstance(payload['messages'][0]['content'], str) and len(payload['messages'][0]['content']) > 0
    # History preserved after system
    assert [m['role'] for m in payload['messages'][1:4]] == ['user', 'assistant', 'user']


def test_router_injects_full_history_into_advanced_reasoning(monkeypatch, tmp_path):
    # Arrange
    # Ensure required env vars are set before importing router
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    monkeypatch.setenv('PERPLEXITY_KEY', 'dummy')

    # Stub OpenAI post to capture advanced tool payload
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        # Only intercept OpenAI calls; router may make two calls in general flow,
        # but here we only exercise execute_tool -> advanced tool.
        if 'openai.com' in url:
            captured['url'] = url
            captured['json'] = json
            return _FakeResponse(json)
        raise AssertionError('Unexpected non-OpenAI POST')

    monkeypatch.setattr('requests.post', fake_post)

    # Use real history persistence under repo root chat_history_logs/
    os.makedirs('chat_history_logs', exist_ok=True)
    sys.path.append(os.path.join(os.getcwd(), 'chef'))
    from utilities.history_messages import message_history_process

    user_id = 'offline_user_1'
    base_obj = {'user_id': user_id, 'session_info': {'user_id': user_id}, 'user_message': ''}
    # Seed a few messages into persistent history
    message_history_process(base_obj, {"role": "user", "content": "search results: two croissant recipes"})
    message_history_process(base_obj, {"role": "assistant", "content": "what equipment do you have?"})
    message_history_process(base_obj, {"role": "user", "content": "oven + mixer"})

    # Import router after env is set
    sys.path.append(os.path.join(os.getcwd(), 'chef', 'chefmain'))
    from message_router import MessageRouter

    router = MessageRouter()

    # Build a tool_call directly to execute_tool to avoid tool selection path
    tool_call = {
        'id': 'tool_1',
        'function': {
            'name': 'advanced_recipe_reasoning',
            'arguments': json.dumps({"query": "ignore me"})  # router should replace with conversation_history
        }
    }

    # Act
    result = router.execute_tool(tool_call, user_id=user_id)

    # Assert: advanced tool was called with full history (system + 3 messages)
    assert result == "FAKE-ADV-RESPONSE"
    payload = captured['json']
    assert payload['messages'][0]['role'] == 'system'
    # Expect the three messages we persisted
    roles_after_system = [m['role'] for m in payload['messages'][1:]]
    # Expect the last three roles to match our seeded messages
    assert roles_after_system[-3:] == ['user', 'assistant', 'user']
