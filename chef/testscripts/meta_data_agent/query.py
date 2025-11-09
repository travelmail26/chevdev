#!/usr/bin/env python3
"""
Simple query interface for the media metadata agent.
Just run this script and ask questions in plain language.
"""

import sys
from media_metadata_agent import talk_to_agent

def main():
    print("Media Metadata Agent Query Interface")
    print("=" * 70)
    print("\nAsk questions in plain language. The agent will translate them into")
    print("MongoDB queries using mongo_simple.")
    print("\nExamples:")
    print("  - What was the most recent conversation?")
    print("  - Find conversations about pizza")
    print("  - Show me chats from today")
    print("  - Find conversations with URLs")
    print("\nType 'quit' or 'exit' to stop.")
    print("-" * 70)

    conversation_history = []

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye!")
                break

            response = talk_to_agent(user_input, conversation_history)
            print(f"\n{response}")

            # Update conversation history
            conversation_history.append({"role": "user", "content": user_input})
            conversation_history.append({"role": "assistant", "content": response})

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            continue

if __name__ == "__main__":
    main()
