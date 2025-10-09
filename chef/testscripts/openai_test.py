#!/usr/bin/env python3
import os
from openai import OpenAI

def main():
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    try:
        # Test basic completion
        response = client.chat.completions.create(
            model="gpt-4o",  # Use a known working model first
            messages=[{"role": "user", "content": "Hello, can you confirm this is working?"}]
        )
        print("Basic API test successful!")
        print(f"Response: {response.choices[0].message.content}")
        
        # Now try GPT-5
        print("\nTesting GPT-5...")
        response = client.chat.completions.create(
            model="gpt-5",
            messages=[{"role": "user", "content": "Hello from GPT-5!"}]
        )
        print("GPT-5 test successful!")
        print(f"Response: {response.choices[0].message.content}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()