#!/usr/bin/env python3
import os
import json
from openai import OpenAI

def main():
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
    
    print("GPT-5 Research Query:")
    print(query)
    print("\n" + "="*80 + "\n")
    
    try:
        # Create response with GPT-5 and forced tool use - STREAMING
        print("Making initial request with forced tool use (streaming)...")
        stream = client.chat.completions.create(
            model="gpt-5",
            messages=messages,
            tools=[web_search_tool],
            tool_choice="required",  # Force tool use
            stream=True
        )
        
        message = response.choices[0].message
        
        # Handle tool calls
        if message.tool_calls:
            print("Assistant is using web search tool...")
            
            # Add the assistant message with tool calls
            messages.append(message)
            
            # Process each tool call
            for tool_call in message.tool_calls:
                if tool_call.function.name == "web_search":
                    args = json.loads(tool_call.function.arguments)
                    search_query = args.get("query", "")
                    
                    print(f"\nSearch Query: {search_query}")
                    
                    # Simulate web search result
                    search_result = f"""Search results for '{search_query}':

SIMULATED SEARCH RESULTS:
1. Archives.org - Jewish Historical Society Records (1880-1920)
2. Library of Congress Manuscript Division - Eastern European Immigration Records
3. YIVO Institute Archives - Pre-1920 Community Documents
4. New York Public Library - Dorot Jewish Division Historical Collections
5. American Jewish Historical Society Archives - 19th Century Documents

Note: This is a simulated search. In a real implementation, you would get actual search results from historical archives and databases specializing in pre-1920 documentation."""
                    
                    print(f"\nSearch Results:\n{search_result}")
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool", 
                        "tool_call_id": tool_call.id,
                        "content": search_result
                    })
            
            # Get final response after tool calls
            print("\nGenerating final response...")
            final_response = client.chat.completions.create(
                model="gpt-5",
                messages=messages
            )
            
            final_message = final_response.choices[0].message
            print(f"\nAssistant Response:\n{final_message.content}")
            
        else:
            print(f"Assistant Response: {message.content}")
            
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure your OPENAI_API_KEY environment variable is set.")

if __name__ == "__main__":
    main()