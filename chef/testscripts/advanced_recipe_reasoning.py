import json
import os
import requests

def advanced_recipe_reasoning(conversation_history=None, openai_api_key=None):
    """
    Advanced reasoning tool for recipe experimentation and workflow optimization.
    
    Args:
        conversation_history: List of message objects with role and content
        openai_api_key: OpenAI API key
    
    Returns:
        String response with helpful recipe guidance
    """
    
    print(f"**DEBUG: advanced_recipe_reasoning called with conversation_history type: {type(conversation_history)}**")
    if conversation_history:
        print(f"**DEBUG: conversation_history has {len(conversation_history)} messages**")
        for i, msg in enumerate(conversation_history[-3:]):  # Show last 3 messages
            print(f"**DEBUG: Message {i}: {msg.get('role')} - {msg.get('content', '')[:100]}...**")
    else:
        print(f"**DEBUG: No conversation_history provided**")
    
    if not openai_api_key:
        openai_api_key = os.environ.get('OPENAI_API_KEY')
    
    if not openai_api_key:
        return "Error: OpenAI API key is missing for advanced reasoning."

    # Load instructions from file
    try:
        base_path = os.path.dirname(__file__)
        instructions_path = os.path.join(base_path, 'instructions', 'recipe_experimenting.txt')
        with open(instructions_path, 'r') as file:
            system_message = file.read()
        print(f"**DEBUG: Loaded instructions from {instructions_path}**")
    except Exception as e:
        print(f"Warning: Could not load instructions: {e}")
        system_message = "You are an expert culinary assistant. Help users with their cooking questions and recipe experiments. Be conversational and responsive to what the user is actually asking."

    # Build messages: system instructions + conversation history
    messages = [{"role": "system", "content": system_message}]
    
    if conversation_history:
        messages.extend(conversation_history)
    
    print(f"**DEBUG: Sending {len(messages)} total messages to LLM (1 system + {len(conversation_history or [])} conversation)**")

    # Make API call
    headers = {
        'Authorization': f'Bearer {openai_api_key}',
        'Content-Type': 'application/json'
    }

    payload = {
        'model': 'gpt-5-mini-2025-08-07',
        'messages': messages,
        'temperature': 1.0,  # Fixed: gpt-5-mini only supports default temperature of 1.0
        'max_tokens': 1500,
        'presence_penalty': 0.1,
        'frequency_penalty': 0.1
    }

    try:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        response_data = response.json()
        result = response_data['choices'][0]['message']['content']
        print(f"**DEBUG: Got response: {result[:100]}...**")
        return result
    except Exception as e:
        print(f"**DEBUG: API call failed: {e}**")
        return f"Error in advanced recipe reasoning: {str(e)}"