#!/usr/bin/env python3
import os
import json
import time
import signal
import sys
from openai import OpenAI

def timeout_handler(signum, frame):
    print("\n⏰ Request timed out after 5 minutes")
    sys.exit(1)

def main():
    # Set 5-minute timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(300)  # 5 minutes
    
    # Initialize OpenAI client
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
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
    
    # The research query
    query = "Research archives prior to 1920 for primary documentation referencing jews and their preference for brisket. Do not use modern interpretations. It must be a primary document. Modern blogs or books may use a primary document if they provide an image or a direct quote with citation"
    
    # Conversation messages
    messages = [
        {"role": "system", "content": "You are a helpful research assistant with access to web search. Use the web_search tool to find historical documents and archives. Focus on primary sources from before 1920."},
        {"role": "user", "content": query}
    ]
    
    print("🔍 GPT-5 Research Query (Streaming with Reasoning):")
    print(query)
    print("\n" + "="*80 + "\n")
    
    try:
        # Create streaming response with GPT-5 and forced tool use
        print("🚀 Starting GPT-5 streaming request with high reasoning effort...")
        print("⏳ This may take several minutes for complex reasoning...\n")
        
        stream = client.chat.completions.create(
            model="gpt-5",
            messages=messages,
            tools=[web_search_tool],
            tool_choice="required",  # Force tool use
            stream=True
        )
        
        # Variables to collect the response
        collected_chunks = []
        collected_message = {"role": "assistant", "content": "", "tool_calls": []}
        thinking_content = ""
        
        print("📡 Streaming response chunks:")
        chunk_count = 0
        
        # Process streaming chunks
        for chunk in stream:
            chunk_count += 1
            
            if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                choice = chunk.choices[0]
                
                # Handle thinking/reasoning tokens if available
                if hasattr(choice, 'reasoning') and choice.reasoning:
                    if choice.reasoning != thinking_content:
                        print(f"🧠 THINKING: {choice.reasoning}")
                        thinking_content = choice.reasoning
                
                # Handle delta content
                if hasattr(choice, 'delta') and choice.delta:
                    delta = choice.delta
                    
                    # Content streaming
                    if hasattr(delta, 'content') and delta.content:
                        print(f"💬 Content chunk {chunk_count}: {delta.content}")
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
                                    print(f"🔧 Tool call: {tool_call_delta.function.name}")
                                
                                if tool_call_delta.function.arguments:
                                    tool_call["function"]["arguments"] += tool_call_delta.function.arguments
                                    print(f"📝 Tool args chunk: {tool_call_delta.function.arguments}")
            
            # Show progress
            if chunk_count % 10 == 0:
                print(f"⏱️  Processed {chunk_count} chunks...")
        
        print(f"\n✅ Stream completed after {chunk_count} chunks")
        
        # Handle tool calls if present
        if collected_message["tool_calls"] and any(tc["id"] for tc in collected_message["tool_calls"]):
            print("\n🔧 Processing tool calls...")
            
            # Add the assistant message with tool calls
            messages.append(collected_message)
            
            # Execute each tool call
            for tool_call in collected_message["tool_calls"]:
                if tool_call["function"]["name"] == "web_search":
                    try:
                        args = json.loads(tool_call["function"]["arguments"])
                        search_query = args.get("query", "")
                        
                        print(f"\n🔍 Executing search: {search_query}")
                        
                        # Simulate web search result
                        search_result = f"""🔍 Search Results for: '{search_query}'

📚 HISTORICAL ARCHIVES & PRIMARY SOURCES:
1. Internet Archive - Jewish Cookbooks Collection (1850-1920)
2. Library of Congress - Manuscript Division: Eastern European Jewish Immigration
3. YIVO Institute Archives - Pre-1920 Community Records
4. New York Public Library - Dorot Jewish Division Historical Collections
5. American Jewish Historical Society - 19th Century Documentation
6. HathiTrust Digital Library - Jewish Community Publications
7. Chronicling America - Jewish Newspaper Archives (1900-1920)

📝 POTENTIAL PRIMARY DOCUMENTS:
- "Aunt Babette's" Cook Book (1889) - Bertha F. Kramer
- "The Jewish Manual" (1846) - Lady Judith Montefiore  
- "The Jewish Cookery Book" (1871) - Esther Levy
- Yiddish newspapers: Forverts, Tageblatt (1900-1920)
- Community cookbook collections from Jewish settlements

⚠️  NOTE: This is a simulated search. Real implementation would query actual historical databases."""
                        
                        print(search_result)
                        
                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": search_result
                        })
                    
                    except json.JSONDecodeError as e:
                        print(f"❌ Error parsing tool arguments: {e}")
            
            # Get final response after tool calls - also streaming
            print(f"\n🔄 Getting final response (streaming)...")
            
            final_stream = client.chat.completions.create(
                model="gpt-5",
                messages=messages,
                stream=True
            )
            
            final_content = ""
            final_thinking = ""
            final_chunk_count = 0
            
            for chunk in final_stream:
                final_chunk_count += 1
                
                if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    
                    # Handle thinking tokens
                    if hasattr(choice, 'reasoning') and choice.reasoning:
                        if choice.reasoning != final_thinking:
                            print(f"🧠 FINAL THINKING: {choice.reasoning}")
                            final_thinking = choice.reasoning
                    
                    # Handle content
                    if hasattr(choice, 'delta') and choice.delta and hasattr(choice.delta, 'content') and choice.delta.content:
                        print(choice.delta.content, end="", flush=True)
                        final_content += choice.delta.content
            
            print(f"\n\n✅ Final response completed after {final_chunk_count} chunks")
            
        else:
            # No tool calls, just print collected content
            print(f"\n💬 Assistant Response:\n{collected_message['content']}")
        
        # Cancel timeout
        signal.alarm(0)
        
    except Exception as e:
        signal.alarm(0)  # Cancel timeout
        print(f"❌ Error: {e}")
        print("Make sure your OPENAI_API_KEY environment variable is set.")

if __name__ == "__main__":
    main()