import os
from openai import OpenAI

MODEL = "gpt-5"                 # official API model id
REASONING_EFFORT = "high"       # expose more "thinking" (count only)
FORCE_SEARCH = True             # set False to let the model decide

def main():
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    prev_id = None

    print("GPT-5 REPL (Ctrl+C to exit)")
    print(f"(Forced web_search: {FORCE_SEARCH})\n")

    while True:
        try:
            user_msg = input("You: ").strip()
            if not user_msg:
                continue


            # Web search tool definition
            web_search_tool = {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for current information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query"
                            }
                        },
                        "required": ["query"]
                    }
                }
            }

            messages = [
                {"role": "user", "content": user_msg}
            ]

            print("Starting GPT-5 request (streaming)...")
            
            stream = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=[web_search_tool],
                tool_choice="required" if FORCE_SEARCH else "auto",  # force a tool call
                stream=True
            )

            print("Processing stream...")
            chunk_count = 0
            collected_message = {"role": "assistant", "content": "", "tool_calls": []}
            
            # Process streaming chunks
            for chunk in stream:
                chunk_count += 1
                
                if chunk.choices and len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    
                    # Handle reasoning/thinking if available
                    if hasattr(choice, 'reasoning') and choice.reasoning:
                        print(f"THINKING: {choice.reasoning}")
                    
                    if choice.delta:
                        delta = choice.delta
                        
                        # Content streaming
                        if delta.content:
                            print(delta.content, end="", flush=True)
                            collected_message["content"] += delta.content
                        
                        # Tool calls streaming
                        if delta.tool_calls:
                            for tool_call_delta in delta.tool_calls:
                                # Initialize tool call if needed
                                while len(collected_message["tool_calls"]) <= tool_call_delta.index:
                                    collected_message["tool_calls"].append({
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""}
                                    })
                                
                                tool_call = collected_message["tool_calls"][tool_call_delta.index]
                                
                                if tool_call_delta.id:
                                    tool_call["id"] = tool_call_delta.id
                                
                                if tool_call_delta.function:
                                    if tool_call_delta.function.name:
                                        tool_call["function"]["name"] = tool_call_delta.function.name
                                        print(f"\nTool: {tool_call_delta.function.name}")
                                    
                                    if tool_call_delta.function.arguments:
                                        tool_call["function"]["arguments"] += tool_call_delta.function.arguments
                                        print(f"{tool_call_delta.function.arguments}", end="")
                
                # Progress indicator every 20 chunks
                if chunk_count % 20 == 0:
                    print(f"\n{chunk_count} chunks processed...")
            
            print(f"\nStream completed ({chunk_count} chunks)")
            
            message = collected_message
            
            # Handle tool calls if present
            if message.get("tool_calls") and any(tc.get("id") for tc in message["tool_calls"]):
                print("\nExecuting web search tool calls...")
                
                # Add the assistant message with tool calls
                messages.append(message)
                
                # Execute each tool call
                for tool_call in message["tool_calls"]:
                    if tool_call.get("function", {}).get("name") == "web_search":
                        import json
                        args = json.loads(tool_call["function"]["arguments"])
                        search_query = args.get("query", "")
                        
                        print(f"Search: {search_query}")
                        
                        # Simulate web search result
                        search_result = f"Search results for '{search_query}': This is a simulated search result for historical research."
                        
                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": search_result
                        })
                
                # Get final response after tool calls with streaming
                print("\nFinal response...")
                final_stream = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    stream=True
                )
                
                for chunk in final_stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        choice = chunk.choices[0]
                        
                        # Show thinking for final response
                        if hasattr(choice, 'reasoning') and choice.reasoning:
                            print(f"FINAL THINKING: {choice.reasoning}")
                        
                        if choice.delta and choice.delta.content:
                            print(choice.delta.content, end="", flush=True)
                
                print("\n")
                
            else:
                print(f"\nAssistant:\n{message['content']}")

            # Usage info not available in streaming mode
            print(f"\n[Note: Usage tokens not available in streaming mode]\n")

        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break
        except Exception as e:
            print(f"[error] {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
