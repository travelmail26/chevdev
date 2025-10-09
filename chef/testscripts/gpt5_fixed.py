#!/usr/bin/env python3
import os
import json
from openai import OpenAI

MODEL = "gpt-5"
FORCE_SEARCH = True

def main():
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    print("GPT-5 REPL (Ctrl+C to exit)")
    print(f"(Forced web_search: {FORCE_SEARCH})\n")
    
    while True:
        try:
            user_msg = input("You: ").strip()
            if not user_msg:
                continue
            
            print("🚀 Starting GPT-5 request (streaming with reasoning)...")
            
            # Try the responses API first (from cookbook)
            try:
                stream = client.responses.create(
                    model=MODEL,
                    input=[{"role": "user", "content": user_msg}],
                    tools=[{"type": "web_search"}],
                    tool_choice="required" if FORCE_SEARCH else "auto",
                    reasoning={"effort": "high"},
                    stream=True
                )
                
                print("📡 Streaming chunks:")
                chunk_count = 0
                collected_content = ""
                
                for chunk in stream:
                    chunk_count += 1
                    
                    # Check for reasoning/thinking content
                    if hasattr(chunk, 'reasoning') and chunk.reasoning:
                        print(f"🧠 THINKING: {chunk.reasoning}")
                    
                    # Check for delta content
                    if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                        choice = chunk.choices[0]
                        
                        if hasattr(choice, 'delta') and choice.delta:
                            if hasattr(choice.delta, 'content') and choice.delta.content:
                                print(choice.delta.content, end="", flush=True)
                                collected_content += choice.delta.content
                            
                            # Check for reasoning in delta
                            if hasattr(choice.delta, 'reasoning') and choice.delta.reasoning:
                                print(f"\n🧠 DELTA THINKING: {choice.delta.reasoning}")
                    
                    # Progress indicator
                    if chunk_count % 10 == 0:
                        print(f"\n⏱️  Processed {chunk_count} chunks...")
                
                print(f"\n\n✅ Stream completed after {chunk_count} chunks")
                
            except Exception as responses_error:
                print(f"Responses API failed: {responses_error}")
                print("Falling back to chat completions API...")
                
                # Fallback to regular chat completions with streaming
                stream = client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": "user", "content": user_msg}],
                    tools=[{
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "description": "Search the web for information",
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
                    }],
                    tool_choice="required" if FORCE_SEARCH else "auto",
                    stream=True
                )
                
                print("📡 Streaming chunks (fallback mode):")
                chunk_count = 0
                collected_message = {"role": "assistant", "content": "", "tool_calls": []}
                
                for chunk in stream:
                    chunk_count += 1
                    
                    if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                        choice = chunk.choices[0]
                        
                        # Handle reasoning if available
                        if hasattr(choice, 'reasoning') and choice.reasoning:
                            print(f"🧠 THINKING: {choice.reasoning}")
                        
                        if hasattr(choice, 'delta') and choice.delta:
                            delta = choice.delta
                            
                            # Content streaming
                            if hasattr(delta, 'content') and delta.content:
                                print(delta.content, end="", flush=True)
                                collected_message["content"] += delta.content
                            
                            # Tool calls streaming
                            if hasattr(delta, 'tool_calls') and delta.tool_calls:
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
                                            print(f"\n🔧 Tool call: {tool_call_delta.function.name}")
                                        
                                        if tool_call_delta.function.arguments:
                                            tool_call["function"]["arguments"] += tool_call_delta.function.arguments
                                            print(f"📝 Args: {tool_call_delta.function.arguments}", end="")
                    
                    # Progress indicator
                    if chunk_count % 20 == 0:
                        print(f"\n⏱️  Processed {chunk_count} chunks...")
                
                print(f"\n\n✅ Fallback stream completed after {chunk_count} chunks")
                
                # Handle tool calls if present
                if collected_message["tool_calls"] and any(tc["id"] for tc in collected_message["tool_calls"]):
                    print("\n🔧 Executing tool calls...")
                    
                    messages = [
                        {"role": "user", "content": user_msg},
                        collected_message
                    ]
                    
                    for tool_call in collected_message["tool_calls"]:
                        if tool_call["function"]["name"] == "web_search":
                            try:
                                args = json.loads(tool_call["function"]["arguments"])
                                search_query = args.get("query", "")
                                
                                print(f"\n🔍 Search: {search_query}")
                                
                                # Simulate search result
                                search_result = f"Search results for '{search_query}': Simulated historical research results."
                                
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call["id"],
                                    "content": search_result
                                })
                            except json.JSONDecodeError as e:
                                print(f"❌ Error parsing tool args: {e}")
                    
                    # Get final response
                    print("\n🔄 Getting final response...")
                    final_response = client.chat.completions.create(
                        model=MODEL,
                        messages=messages,
                        stream=True
                    )
                    
                    for chunk in final_response:
                        if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                            choice = chunk.choices[0]
                            
                            if hasattr(choice, 'reasoning') and choice.reasoning:
                                print(f"🧠 FINAL THINKING: {choice.reasoning}")
                            
                            if hasattr(choice, 'delta') and choice.delta and hasattr(choice.delta, 'content') and choice.delta.content:
                                print(choice.delta.content, end="", flush=True)
                    
                    print("\n")
                
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break
        except Exception as e:
            print(f"[error] {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()