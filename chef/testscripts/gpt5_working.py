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
            
            print("🚀 Starting GPT-5 request (streaming)...")
            
            # Web search tool definition
            web_search_tool = {
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
            }
            
            messages = [{"role": "user", "content": user_msg}]
            
            # Create streaming response
            stream = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=[web_search_tool],
                tool_choice="required" if FORCE_SEARCH else "auto",
                stream=True
            )
            
            print("📡 Processing stream...")
            chunk_count = 0
            collected_message = {"role": "assistant", "content": "", "tool_calls": []}
            
            # Process streaming chunks
            for chunk in stream:
                chunk_count += 1
                
                if chunk.choices and len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    
                    # Handle reasoning/thinking if available
                    if hasattr(choice, 'reasoning') and choice.reasoning:
                        print(f"🧠 THINKING: {choice.reasoning}")
                    
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
                                        print(f"\n🔧 Tool: {tool_call_delta.function.name}")
                                    
                                    if tool_call_delta.function.arguments:
                                        tool_call["function"]["arguments"] += tool_call_delta.function.arguments
                                        print(f"📝 {tool_call_delta.function.arguments}", end="")
                
                # Progress indicator every 20 chunks
                if chunk_count % 20 == 0:
                    print(f"\n⏱️  {chunk_count} chunks processed...")
            
            print(f"\n✅ Stream completed ({chunk_count} chunks)")
            
            # Handle tool calls if present
            if collected_message["tool_calls"] and any(tc.get("id") for tc in collected_message["tool_calls"]):
                print("\n🔧 Executing tool calls...")
                
                # Add assistant message with tool calls
                messages.append(collected_message)
                
                # Execute each tool call
                for tool_call in collected_message["tool_calls"]:
                    if tool_call.get("function", {}).get("name") == "web_search":
                        try:
                            args = json.loads(tool_call["function"]["arguments"])
                            search_query = args.get("query", "")
                            
                            print(f"\n🔍 Searching: {search_query}")
                            
                            # Simulate search result
                            search_result = f"Historical search results for '{search_query}': Found primary documents and archives."
                            
                            # Add tool result
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "content": search_result
                            })
                        except Exception as e:
                            print(f"❌ Tool error: {e}")
                
                # Get final response with streaming
                print("\n🔄 Final response...")
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
                            print(f"🧠 FINAL THINKING: {choice.reasoning}")
                        
                        if choice.delta and choice.delta.content:
                            print(choice.delta.content, end="", flush=True)
                
                print("\n")
            else:
                print(f"\nAssistant: {collected_message['content']}")
                
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break
        except Exception as e:
            print(f"[error] {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()