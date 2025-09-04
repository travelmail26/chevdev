import os
import sys
import json as json_module


class _FakeResp:
    def __init__(self, payload, json_body=None):
        self._payload = payload
        self._json_body = json_body or {"ok": True, "result": {}}
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._json_body


def test_route_message_advanced_reasoning_sends_telegram(monkeypatch, tmp_path):
    # Arrange environment
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    monkeypatch.setenv('PERPLEXITY_KEY', 'dummy')

    # Ensure history dir exists for persistence
    os.makedirs('chat_history_logs', exist_ok=True)

    # Create application token file so process_message_object can extract it
    user_id = 'router_adv_tg_user'
    token_file = f"application_data_for_{user_id}.txt"
    with open(token_file, 'w', encoding='utf-8') as f:
        # Minimal string that matches token=... regex
        f.write("Application[bot=ExtBot[token='123456:TEST_TOKEN']]")

    # Capture outgoing requests
    calls = []

    def fake_post(url, headers=None, json=None, data=None, timeout=None, stream=False):
        # Record call
        calls.append({
            'url': url,
            'headers': headers,
            'json': json,
            'data': data,
        })

        # Router first OpenAI call: tool selection (has tools)
        if 'openai.com' in url and isinstance(json, dict) and 'tools' in json:
            return _FakeResp(json, json_body={
                'choices': [{
                    'message': {
                        'content': '',
                        'tool_calls': [{
                            'id': 'call_1',
                            'type': 'function',
                            'function': {
                                'name': 'advanced_recipe_reasoning',
                                'arguments': json_module.dumps({"query": "ignored"})
                            }
                        }]
                    }
                }]
            })

        # Advanced tool call: utilities.advanced_recipe_reasoning (model gpt-4o-mini)
        if 'openai.com' in url and isinstance(json, dict) and json.get('model') == 'gpt-4o-mini':
            return _FakeResp(json, json_body={'choices': [{'message': {'content': 'TOOL-OUTPUT: plan here'}}]})

        # Router second OpenAI call: pass-through of tool output (no tools)
        if 'openai.com' in url and isinstance(json, dict) and 'tools' not in json:
            return _FakeResp(json, json_body={'choices': [{'message': {'content': 'FINAL: plan here'}}]})

        # Telegram send
        if 'api.telegram.org' in url:
            return _FakeResp(None, json_body={'ok': True, 'result': {'message_id': 1}})

        raise AssertionError(f"Unexpected POST url={url}")

    # Patch requests.post
    monkeypatch.setattr('requests.post', fake_post)

    # Load router and run a message through it
    sys.path.append(os.path.join(os.getcwd(), 'chef'))
    sys.path.append(os.path.join(os.getcwd(), 'chef', 'chefmain'))
    from message_router import MessageRouter

    router = MessageRouter()

    message_object = {
        'user_id': user_id,
        'session_info': {
            'user_id': user_id,
            'chat_id': 123456789,  # triggers Telegram send
        },
        'user_message': 'i want to explore two croissant recipes at the same time',
    }

    # Act
    output = router.route_message(message_object=message_object)

    # Assert: final assistant content returned
    assert output == 'FINAL: plan here'

    # Verify calls included: first OpenAI (tool selection), advanced tool call, second OpenAI, Telegram
    urls = [c['url'] for c in calls]
    assert any('openai.com' in u for u in urls)
    assert any('api.telegram.org' in u for u in urls)

    # Verify advanced tool payload contained a system message followed by our user message in history
    adv_payloads = [c['json'] for c in calls if c['json'] and c['json'].get('model') == 'gpt-4o-mini']
    assert adv_payloads, 'Advanced tool payload not captured'
    adv_messages = adv_payloads[0]['messages']
    assert adv_messages[0]['role'] == 'system'
    # One of the user/assistant messages after system should contain the user input we sent
    assert any(m.get('role') == 'user' and 'croissant' in m.get('content', '').lower() for m in adv_messages[1:])
