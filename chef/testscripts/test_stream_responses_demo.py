import json
import os
from openai import OpenAI


def run_stream_demo():
    """Run a minimal Responses API streaming demo."""
    # Before: you had to paste a key in code. After example: read OPENAI_API_KEY from env.
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("Missing OPENAI_API_KEY. Example: export OPENAI_API_KEY='sk-...'")
        return

    client = OpenAI(api_key=api_key)
    if not hasattr(client, "responses"):
        print("OpenAI SDK too old for Responses API. Upgrade: pip install -U openai")
        return

    def get_weather(location):
        """Fake tool response for demo purposes."""
        # Before: you would call an API here. After example: return a simple static string.
        return f"Sunny and 72F in {location}."

    stream = client.responses.create(
        model="gpt-5-nano-2025-08-07",
        input="Weather in NYC?",
        tools=[{
            "type": "function",
            "name": "get_weather",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string"
                    }
                },
                "required": ["location"]
            }
        }],
        stream=True,
        reasoning={"effort": "low"},
        text={"verbosity": "low"}
    )

    tool_result = None
    tool_call_id = None
    response_id = None
    args_buffer = ""
    for event in stream:
        print("event type:", event.type)
        if event.type == "response.created":
            response_id = event.response.id
        if event.type == "response.output_text.delta":
            print(event.delta, end="", flush=True)
        elif event.type == "response.output_item.added" and event.item.type == "function_call":
            tool_call_id = event.item.call_id
        elif event.type == "response.function_call_arguments.delta":
            # Before: deltas come as fragments like '{"loc'. After example: append until complete.
            args_buffer += event.delta
        elif event.type == "response.function_call_arguments.done":
            args_buffer = event.arguments
        elif event.type == "response.done":
            break

    if tool_call_id and args_buffer:
        args = json.loads(args_buffer)
        tool_result = get_weather(args["location"])

    if tool_result and tool_call_id:
        stream2 = client.responses.create(
            model="gpt-5-nano-2025-08-07",
            input=[
                {"role": "user", "content": "Weather in NYC?"},
                {"type": "function_call_output", "call_id": tool_call_id, "output": tool_result}
            ],
            previous_response_id=response_id,
            stream=True,
            reasoning={"effort": "low"},
            text={"verbosity": "low"}
        )
        for event in stream2:
            #print("event2 type:", event.type)
            if event.type == "response.output_text.delta":
                print(event.delta, end="", flush=True)
            elif event.type == "response.done":
                break


if __name__ == "__main__":
    run_stream_demo()
