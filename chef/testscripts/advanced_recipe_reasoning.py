import json
import os
import requests

def advanced_recipe_reasoning(query="", openai_api_key=None):
    """
    Advanced reasoning tool for complex recipe experimentation.
    
    Args:
        query: Combined user query with conversation context (injected by message_router)
        openai_api_key: OpenAI API key
    
    Returns:
        String response with experimental recipe plan
    """
    
    if not openai_api_key:
        openai_api_key = os.environ.get('OPENAI_API_KEY')
    
    if not openai_api_key:
        return "Error: OpenAI API key is missing for advanced reasoning."

    # Load the exploring recipes instruction set
    try:
        base_path = os.path.dirname(os.path.dirname(__file__))  # Go up from testscripts to chef/
        instructions_path = os.path.join(base_path, 'recipe_experimenting.txt')
        with open(instructions_path, 'r') as file:
            exploring_instructions = file.read()
    except Exception as e:
        print(f"Warning: Could not load exploring instructions: {e}")
        exploring_instructions = """Use advanced reasoning to design recipe experiments with these principles:
- Change only ONE element per variation
- Use small test portions 
- Provide clear comparison methodology
- Ask questions before proceeding to full recipe"""

    # Build the system message with instructions
    system_message = f"""You are an expert culinary scientist specializing in recipe experimentation.

{exploring_instructions}

CRITICAL INSTRUCTIONS FOR THIS SESSION:
- You are a recipe experimentation specialist. Your ONLY job is to figure out efficient recipe experimentations by analyzing constraints and optimizing workflows.
- ALWAYS be explicit: "I need to analyze these recipes and figure out the most efficient way to experiment with them. I'll ask questions about your constraints, then identify overlapping steps and resource optimization opportunities."
- CONSTRAINT ANALYSIS PHASE: Ask ONE question at a time about:
  * Equipment limitations (mixing bowls, tools, oven space, etc.)
  * Batch size goals for each recipe variation
  * Time constraints and scheduling
  * Available ingredients and substitutions needed
- WORKFLOW OPTIMIZATION PHASE: After understanding constraints, be explicit about your thinking:
  * "Based on your constraints, I can see these overlapping steps that can be combined..."
  * "Here are the resource sharing opportunities I've identified..."
  * "This is my proposed experimental approach..."
  * Ask for permission: "Does this approach make sense given your constraints?"
- ONLY provide the final optimized experimental plan after getting user permission
- Extract recipe data from the conversation context provided in the query"""

    # Build messages for the advanced reasoning call
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": query}
    ]

    # Make API call with advanced reasoning parameters
    headers = {
        'Authorization': f'Bearer {openai_api_key}',
        'Content-Type': 'application/json'
    }

    payload = {
        'model': 'gpt-4o-mini',  # Use more capable model for complex reasoning
        'messages': messages,
        'temperature': 0.7,  # Higher creativity for experimentation
        'max_tokens': 2048,
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
        
        return response_data['choices'][0]['message']['content']
        
    except Exception as e:
        return f"Error in advanced recipe reasoning: {str(e)}"

# Test function if run directly
if __name__ == "__main__":
    test_query = """Current query: I want to experiment with carbonara techniques

Conversation context:
[{"role": "user", "content": "search for carbonara recipes"}, 
 {"role": "assistant", "content": "Found 3 approaches: traditional with eggs and pecorino, cream-based version, and modern sous vide technique"}]"""
    
    result = advanced_recipe_reasoning(query=test_query)
    print(result)