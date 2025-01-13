import json
import os

import requests
from datetime import datetime
import pytz
from perplexity import perplexitycall
from sheetscall import add_chatlog_entry, sheets_call, fetch_chatlog, task_create, fetch_preferences, fetch_recipes, update_task
#from loggerbackup import ConversationLogger

#from postprocess import auto_postprocess
#from alarm import append_alarm
#from serpapirecipes import search_recipes_serpapi

# Note for LLM agents: this is how the token secret is getting
openai_api_key = os.environ['OPENAI_API_KEY']

##logging
import logging

logger = logging.getLogger(__name__)

#print("DEBUG: openai_api_key: ", openai_api_key)

sheets_call_data = fetch_chatlog()

extended_context = f"Here is the extended context data to prioritize for your answer: \n{sheets_call_data}"


def get_current_time():
    eastern = pytz.timezone('America/New_York')
    print('DEBUG: get_current_time triggered',
          datetime.now(eastern).strftime('%Y-%m-%d %H:%M:%S %Z'))
    return datetime.now(eastern).strftime('%Y-%m-%d %H:%M:%S %Z')


class AIHandler:

    def __init__(self, user_id, openai_key=None):
        self.openai_key = openai_key or openai_api_key
        #self.logger = ConversationLogger()
        self.user_id = user_id
        self.messages = self.initialize_messages()

        self.conversation_info = {
            "messages": self.messages,
            "user_id": self.user_id
        }

    def initialize_messages(self):
        current_time = datetime.now().isoformat()
        # Initialize a list to hold parts of the system content
        system_content_parts = []

        # Add current time context as the first instruction

        # Add system instruction to record conversation with user id
        system_content_parts.append(
            '=== SYSTEM INSTRUCTION ===\nConversation with User ID: ' +
            str(self.user_id) + '\n=== END SYSTEM INSTRUCTION ===\n')

        system_content_parts.append(
            f"=== CURRENT TIME CONTEXT ===\nCurrent time: {current_time} ==END CURRENT TIME CONTEXT==\n"
        )

        # Load and append contents from each file
        with open('chef/instructions_base.txt', 'r') as file:
            system_content_parts.append("=== BASE DEFAULT INSTRUCTIONS ===\n" +
                                        file.read())
        with open('chef/instructions_recipe.txt', 'r') as file:
            system_content_parts.append("=== BASE DEFAULT INSTRUCTIONS ===\n" +
                                        file.read())
        # with open('reporter/chef/instructions_diet_logistics.txt','r') as file:
        #     system_content_parts.append(
        #         "=== DIET LOGISTICS INSTRUCTIONS ===\n" + file.read())
        with open('chef/instructions_brainstorm.txt', 'r') as file:
            system_content_parts.append("=== BRAINSTORM INSTRUCTIONS ===\n" +
                                        file.read())
        # with open('reporter/chef/exploring_additional_instructions.txt',
        #           'r') as file:
        #     system_content_parts.append(
        #         "=== EXPLORING ADDITIONAL INSTRUCTIONS ===\n" + file.read())
        with open('chef/instructions_log.txt', 'r') as file:
            system_content_parts.append(
                "=== LOGGING ADDITIONAL INSTRUCTIONS ===\n" + file.read())
        # with open('reporter/chef/instructions_mealplan.txt', 'r') as file:
        #     system_content_parts.append(
        #         "=== MEAL PLAN ADDITIONAL INSTRUCTIONS ===\n" + file.read())
        # with open('reporter/chef/instructions_spiritual.txt', 'r') as file:
        #     system_content_parts.append("=== SPIRITUAL INSTRUCTIONS ===\n" + file.read())

        combined_content = "\n\n".join(system_content_parts)

        # Return the full message content as a single system message
        return [{"role": "system", "content": combined_content}]

    def openai_request(self):
        if not self.openai_key:
            return "OpenAI API key is missing."

        headers = {
            'Authorization': f'Bearer {self.openai_key}',
            'Content-Type': 'application/json'
        }

        #TOOLS
        tools = [

            # Add this in the tools definition section
            # {
            #     "type": "function",
            #     "function": {
            #         "name": "search_recipes_serpapi",
            #         "description": "Search for recipes. The user will explicit calls ' google search recipes for <query>''. DO NOT MISTAKE this for the browsing function call.'",
            #         "parameters": {
            #             "type": "object",
            #             "properties": {
            #                 "query": {
            #                     "type": "string",
            #                     "description": "Search term for recipes"
            #                 }
            #             },
            #             "required": ["query"],
            #             "additionalProperties": False
            #         },
            #         "strict": False
            #     }
            # },
            
            {
                "type": "function",
                "function": {
                    "name": "fetch_hummus",
                    "description":
                    "Fetch hummus recipes when user specifically asks for a hummus recipe.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            
            {
                "type": "function",
                "function": {
                    "name": "append_alarm",
                    "description":
                    "Creates an alarm with a trigger time and message. Examples: 'set an alarm for 7 minutes' or 'reminder to flip the steak in 3 minutes' ",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "trigger_time": {
                                "type":
                                "string",
                                "description":
                                "Number of seconds from now when alarm should trigger. For example, if the user mentions 5 minutes, fill in '300"
                            },
                            "message": {
                                "type":
                                "string",
                                "description":
                                "Message to send when alarm triggers. everything in the user message but the trigger time"
                            }
                        },
                        "required": ["trigger_time", "message"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            #tasks update
            {
                "type": "function",
                "function": {
                    "name": "update_task",
                    "description":
                    "Update specific columns of a task by its ID. Can update any combination of: date, title, description, completed, notes columns. If completed, fill in 'yes' ",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {
                                "type": "string",
                                "description": "The ID of the task to update"
                            },
                            "updates": {
                                "type": "object",
                                "description":
                                "Key-value pairs of columns to update. Keys must be: date, title, description, completed, or notes",
                                "properties": {
                                    "date": {
                                        "type": "string"
                                    },
                                    "title": {
                                        "type": "string"
                                    },
                                    "description": {
                                        "type": "string"
                                    },
                                    "completed": {
                                        "type": "string"
                                    },
                                    "notes": {
                                        "type": "string"
                                    }
                                },
                                "additionalProperties": False
                            }
                        },
                        "required": ["task_id", "updates"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            # reciple fetch tool
            {
                "type": "function",
                "function": {
                    "name": "fetch_recipes",
                    "description":
                    "Fetch all recipes from the recipes database",
                    "parameters": {
                        "type": "object",
                        "properties":
                        {},  # No parameters needed as we're fetching all recipes
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_preferences",
                    "description": "get preferences for user greg."
                    # "parameters": {
                    #     "type": "object",
                    #     "properties": {
                    #         "tab": {
                    #             "type": "string",
                    #             "description": "fill it verbatim with string 'preferences' "
                    #         }
                    #     },
                    #     "required": ["query"],
                    #     "additionalProperties": False
                },
                "strict": False
            },
            {
                "type": "function",
                "function": {
                    "name": "sheets_call",
                    "description":
                    "return database of tasks. User will ask to review tasks. Whenever you talk about a task or display a task to a user, display the unique id in paratheses. Whenever you speak about more than one task, enumerate them as well so that the user can identify tasks by number",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tab": {
                                "type":
                                "string",
                                "description":
                                "fill it verbatim with string 'tasks' "
                            }
                        },
                        "required": ["query"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "perplexitycall",
                    "description":
                    "Trigger when a user asks to Browse for an answer. Keyword browse should trigger this function. Then fill in the parameter with the user's query vebatim.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The user's query to search for"
                            }
                        },
                        "required": ["query"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            },
            # Task_create tool
            {
                "type": "function",
                "function": {
                    "name": "task_create",
                    "description":
                    "Use ONLY when specifically instructed to create a new task. Avoid use for general communication or suggestions. Ensure task details are explicit and clear. This function sreates a new entry in the spreadsheet with the following fields: ID, date, title, description, and notes. Trigger only if instructed by user to create a task.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type":
                                "string",
                                "description":
                                "Unique identifier. Should be 12 digits from current time year month day hour minute second"
                            },
                            "date": {
                                "type":
                                "string",
                                "description":
                                "Date of task creation in ISO format"
                            },
                            "title": {
                                "type":
                                "string",
                                "description":
                                "Summarize 2-4 word title from description"
                            },
                            "description": {
                                "type":
                                "string",
                                "description":
                                "1-5 sentence description of the task"
                            },
                            "notes": {
                                "type": "string",
                                "description": "Do not fill this in ever"
                            }
                        },
                        "required": ["id", "date", "title", "description"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
            }
        ]

        data = {
            'model': 'gpt-4o-mini',
            'messages': self.messages,
            'temperature': 0.5,
            'max_tokens': 4096,
            'stream': False,
            'tools': tools
        }

        try:
            # First API call
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=data)
            response.raise_for_status()
            response_json = response.json()

            # Extract the assistant's message
            assistant_message = response_json['choices'][0]['message']

            # TOOLS Check if the assistant wants to call a function (tool)
            if 'tool_calls' in assistant_message:
                print(f"DEBUG: tool_calls in assistant_message")
                tool_calls = assistant_message['tool_calls']
                for tool_call in tool_calls:
                    function_name = tool_call['function']['name']
                    function_args = json.loads(tool_call['function'].get(
                        'arguments', '{}'))
                    tool_call_id = tool_call['id']

                    #perplexity call function
                    if function_name == 'perplexitycall':
                        query = function_args.get('query')
                        if query:
                            print("Agent is searching the internet for an answer...")
                            # Prepare the conversation history for perplexitycall
                            structured_message = []

                            # Include user and assistant messages from the conversation
                            for msg in self.messages:
                                if msg['role'] in ['user', 'assistant']:
                                    if msg['content'] is None:
                                        msg['content'] = 'empty'
                                    structured_message.append(msg)

                            # No need to append the query again if it's already in self.messages
                            def filter_messages(messages):
                                filtered = []
                                for i, msg in enumerate(messages):
                                    if msg['role'] == 'assistant' and 'tool_calls' in msg:
                                        continue  # Skip this message
                                    if i > 0 and msg['role'] == filtered[-1][
                                            'role']:
                                        # Combine with previous message of same role
                                        filtered[-1][
                                            'content'] += "\n" + msg['content']
                                    else:
                                        filtered.append(msg)
                                return filtered

                            # Use this function before sending messages to Perplexity
                            perplexity_messages_filtered = filter_messages(
                                structured_message)
                            # Call Perplexity with the conversation history
                            perplexity_response_content = perplexitycall(
                                perplexity_messages_filtered)

                            # Ensure response_content is a string
                            if isinstance(perplexity_response_content, dict):
                                perplexity_response_content = json.dumps(perplexity_response_content)

                            #print ('DEBUG: perplexity_response_content', perplexity_response_content)
                            # Properly format and send the function result back to the model
                            function_call_result_message = {
                                "role": "tool",
                                "content": perplexity_response_content,
                                "tool_call_id": tool_call_id
                            }

                            # Add the assistant's message and function result to the conversation
                            self.messages.append(assistant_message)
                            # print('DEBUG: assistant_message: ',
                            #       assistant_message)
                            self.messages.append(function_call_result_message)
                            # print('DEBUG: function_call_result_message: ',
                            #       function_call_result_message)

                            #system message not to truncate perplexity output
                            self.messages.append({
                                "role": "system",
                                "content": "Do not truncate or summarize this function call result. Return the text as is. It will include both text and citations. It is from another agent, perplexity. Do not make an exceptions to this system instruction. In your response, start with 'result from perplexity:' and then return the exact result, which may urls, citations or special characters."
                            })
                            # Prepare the payload for the second API call
                            completion_payload = {
                                "model": 'gpt-4o-mini',
                                "messages": self.messages
                            }

                            # Make the second API call
                            second_response = requests.post(
                                'https://api.openai.com/v1/chat/completions',
                                headers=headers,
                                json=completion_payload)
                            second_response.raise_for_status()

                            # Process the final response after the function call
                            second_response_json = second_response.json()
                            final_assistant_message = second_response_json[
                                'choices'][0]['message']

                            # Add the assistant's final response to the conversation
                            self.messages.append(final_assistant_message)

                            # Return the assistant's final response content
                            return final_assistant_message.get(
                                'content', 'No content in the response.')
                        else:
                            return "Error: No query provided for browsing."

                    #search google recipes

                    # elif function_name == 'search_recipes_serpapi':
                    #     print("DEBUG: triggered tool search recipes")

                    #     query = function_args.get('query')
                    #     try:
                    #         result_data = search_recipes_serpapi(query)
                    #     except Exception as e:
                    #         print(f"ERROR: fetching recipes: {e}")
                    #         return "Failed to fetch recipes"

                    #     # First add the tool response message
                    #     function_call_result_message = {
                    #         "role": "tool",
                    #         "content": str(result_data),
                    #         "tool_call_id": tool_call_id
                    #     }

                    #     # Create database context message
                    #     database_recipe_context = {
                    #         "role":
                    #         "system",
                    #         "content":
                    #         f"""This is a search result of recipes. THe user requested search results and this was the result

                    #         *RECIPE CONTENT FOLLOWS*:
                    #         {str(result_data)} ~~*END RECIPE API CALL CONTENT*~~

                    #         """
                    #     }

                    #     # Update messages in correct sequence
                    #     self.messages.append(assistant_message)
                    #     self.messages.append(function_call_result_message
                    #                          )  # Required tool response
                    #     self.messages.append(database_recipe_context)

                    #     # Second API call
                    #     completion_payload = {
                    #         "model": 'gpt-4o-mini',
                    #         "messages": self.messages
                    #     }

                    #     # DEBUG: Print a slice of the API call payload
                    #     print(
                    #         f"DEBUG: first few recipe messages: {self.messages[:1]}"
                    #     )

                    #     # Second API call
                    #     try:
                    #         second_response = requests.post(
                    #             'https://api.openai.com/v1/chat/completions',
                    #             headers=headers,
                    #             json=completion_payload)
                    #         second_response.raise_for_status()
                    #     except requests.exceptions.RequestException as e:
                    #         print(f"ERROR: API call failed: {e}")
                    #         return "Failed to fetch completion"

                    #     # Process final response
                    #     second_response_json = second_response.json()
                    #     final_assistant_message = second_response_json[
                    #         'choices'][0]['message']

                    #     # Add final response to conversation
                    #     self.messages.append(final_assistant_message)

                    #     return final_assistant_message.get(
                    #         'content', 'No content in response.')



                    ###hummus tool call

                    elif function_name == 'fetch_hummus':
                        print("DEBUG: triggered tool hummus")
                        try:
                            result_data = fetch_sheet_data_rows(
                                'recipe_hummus')
                        except Exception as e:
                            print(f"ERROR: fetching hummus recipes: {e}")
                            return "Failed to fetch hummus recipes"
    
                        function_call_result_message = {
                            "role": "tool",
                            "content": str(result_data),
                            "tool_call_id": tool_call_id
                        }
    
                        database_hummus_context = {
                            "role":
                            "system",
                            "content":
                            f"""Here is the hummus recipes from our database
    
                            *HUMMUS RECIPES FOLLOW*:
                            {str(result_data)} ~~*END HUMMUS RECIPES*~~
                            """
                        }
    
                        self.messages.append(assistant_message)
                        self.messages.append(function_call_result_message)
                        self.messages.append(database_hummus_context)
    
                        completion_payload = {
                            "model": 'gpt-4o-mini',
                            "messages": self.messages
                        }
    
                        try:
                            second_response = requests.post(
                                'https://api.openai.com/v1/chat/completions',
                                headers=headers,
                                json=completion_payload)
                            second_response.raise_for_status()
                        except requests.exceptions.RequestException as e:
                            print(f"ERROR: API call failed: {e}")
                            return "Failed to fetch completion"
    
                        second_response_json = second_response.json()
                        final_assistant_message = second_response_json[
                            'choices'][0]['message']
                        self.messages.append(final_assistant_message)
                        return final_assistant_message.get(
                            'content', 'No content in response.')
                    
                    #recipes fetch
                    elif function_name == 'fetch_recipes':
                        print("DEBUG: triggered tool recipes")

                        try:
                            result_data = fetch_recipes()
                        except Exception as e:
                            print(f"ERROR: fetching recipes: {e}")
                            return "Failed to fetch recipes"

                        # First add the tool response message
                        function_call_result_message = {
                            "role": "tool",
                            "content": str(result_data),
                            "tool_call_id": tool_call_id
                        }

                        # Create database context message
                        database_recipe_context = {
                            "role":
                            "system",
                            "content":
                            f"""This is a database of recipes. Prioritize them when making recommendations. After the function, just tell me "recipes loaded into memory"

                            *RECIPE CONTENT FOLLOWS*:
                            {str(result_data)} ~~*END RECIPE DATABASE CONTENT*~~

                            """
                        }

                        # Update messages in correct sequence
                        self.messages.append(assistant_message)
                        self.messages.append(function_call_result_message
                                             )  # Required tool response
                        self.messages.append(database_recipe_context)

                        # Second API call
                        completion_payload = {
                            "model": 'gpt-4o-mini',
                            "messages": self.messages
                        }

                        # DEBUG: Print a slice of the API call payload
                        print(
                            f"DEBUG: first few recipe messages: {self.messages[:1]}"
                        )

                        # Second API call
                        try:
                            second_response = requests.post(
                                'https://api.openai.com/v1/chat/completions',
                                headers=headers,
                                json=completion_payload)
                            second_response.raise_for_status()
                        except requests.exceptions.RequestException as e:
                            print(f"ERROR: API call failed: {e}")
                            return "Failed to fetch completion"

                        # Process final response
                        second_response_json = second_response.json()
                        final_assistant_message = second_response_json[
                            'choices'][0]['message']

                        # Add final response to conversation
                        self.messages.append(final_assistant_message)

                        return final_assistant_message.get(
                            'content', 'No content in response.')

                    #alarm

                    elif function_name == 'append_alarm':
                        print("DEBUG: alarm tool")

                        # Parse arguments from the function call
                        function_args = json.loads(
                            tool_call['function']['arguments'])
                        trigger_time = function_args.get('trigger_time')
                        message = function_args.get('message')

                        try:
                            result_data = append_alarm(
                                trigger_time=trigger_time, message=message)
                        except Exception as e:
                            print(f"ERROR: triggering alarm: {e}")
                            return "Failed to trigger alarm"
                        # First add the tool response message
                        function_call_result_message = {
                            "role": "tool",
                            "content": str(result_data),
                            "tool_call_id": tool_call_id
                        }

                        # Create database context message
                        database_recipe_context = {
                            "role":
                            "system",
                            "content":
                            f"""alarm notifiation message: {str(result_data)}"""
                        }

                        # Update messages in correct sequence
                        self.messages.append(assistant_message)
                        self.messages.append(function_call_result_message
                                             )  # Required tool response
                        self.messages.append(database_recipe_context)

                        # Second API call
                        completion_payload = {
                            "model": 'gpt-4o-mini',
                            "messages": self.messages
                        }

                        # DEBUG: Print a slice of the API call payload
                        print(f"DEBUG: alarm after second api call")

                        # Second API call
                        try:
                            second_response = requests.post(
                                'https://api.openai.com/v1/chat/completions',
                                headers=headers,
                                json=completion_payload)
                            second_response.raise_for_status()
                        except requests.exceptions.RequestException as e:
                            print(f"ERROR: API call failed: {e}")
                            return "Failed to alarm completion"

                        # Process final response
                        second_response_json = second_response.json()
                        final_assistant_message = second_response_json[
                            'choices'][0]['message']

                        # Add final response to conversation
                        self.messages.append(final_assistant_message)

                        return final_assistant_message.get(
                            'content', 'No content in response.')

                    #update task
                    elif function_name == 'update_task':
                        print("DEBUG: triggered tool function update task")

                        # Extract parameters from function_args and ensure updates is a dictionary
                        task_id = function_args.get('task_id')
                        updates = {}

                        # Extract each possible update field
                        for key, value in function_args['updates'].items():
                            if key in [
                                    'date', 'title', 'description',
                                    'completed', 'notes'
                            ]:
                                updates[key] = value

                        # Call update_task function
                        result = update_task(task_id, updates)

                        # Format the response
                        function_call_result_message = {
                            "role": "tool",
                            "content": str(result),
                            "tool_call_id": tool_call_id
                        }

                        # Add messages to conversation
                        self.messages.append(assistant_message)
                        self.messages.append(function_call_result_message)

                        return "Task updated successfully" if result else "Failed to update task"

                    # Handle the task_create function call
                    elif function_name == 'task_create':
                        print(
                            f"DEBUG: triggered tool function called task creation"
                        )
                        # Extract parameters from function_args
                        id = function_args.get('id')
                        date = function_args.get('date')
                        title = function_args.get('title')
                        description = function_args.get('description')
                        notes = function_args.get('notes')

                        # Call task_create function
                        result = task_create(id, date, title, description,
                                             notes)

                        # Format the response
                        function_call_result_message = {
                            "role": "tool",
                            "content": str(result),
                            "tool_call_id": tool_call_id
                        }

                        # Add messages to conversation
                        self.messages.append(assistant_message)
                        self.messages.append(function_call_result_message)

                        return "Task created successfully" if result else "Failed to create task"

                # When sheets_call is triggered in tool_calls
                    elif function_name == 'sheets_call':
                        print("DEBUG: triggered tool sheetscall")
                        tab = function_args.get('tab')
                        result = sheets_call(tab)

                        # First add the tool response message
                        function_call_result_message = {
                            "role": "tool",
                            "content": str(result),
                            "tool_call_id": tool_call_id
                        }

                        # Create database context message
                        database_context = {
                            "role":
                            "system",
                            "content":
                            f"""Review the following cooking task database.
                            For each task you should:
                            1. Check if it was attempted
                            2. Ask specific questions about:
                               - What worked/didn't work
                               - Any modifications made
                               - Taste and texture results
                               - Why it wasn't attempted (if not done)
                            Keep questions focused and brief.
            
                            DATABASE CONTENT FOLLOWS: {str(result)} ~~END DATABASE CONTENT~~
                            """
                        }

                        # Update messages in correct sequence
                        self.messages.append(assistant_message)
                        self.messages.append(function_call_result_message
                                             )  # Required tool response
                        self.messages.append(database_context)

                        # Second API call
                        completion_payload = {
                            "model": 'gpt-4o-mini',
                            "messages": self.messages
                        }

                        # Second API call
                        second_response = requests.post(
                            'https://api.openai.com/v1/chat/completions',
                            headers=headers,
                            json=completion_payload)
                        second_response.raise_for_status()

                        # Process final response
                        second_response_json = second_response.json()
                        final_assistant_message = second_response_json[
                            'choices'][0]['message']

                        # Add final response to conversation
                        self.messages.append(final_assistant_message)

                        return final_assistant_message.get(
                            'content', 'No content in response.')

                    #user preferences function call
                    elif function_name == 'fetch_preferences':
                        print("DEBUG: triggered tool preferences")
                        tab = function_args.get('tab')
                        prefs, conditions = fetch_preferences()

                        result_data = {
                            "preferences": prefs,
                            "conditions": conditions
                        }
                        # First add the tool response message
                        function_call_result_message = {
                            "role": "tool",
                            "content": str(result_data),
                            "tool_call_id": tool_call_id
                        }

                        # Create database context message
                        database_context = {
                            "role":
                            "system",
                            "content":
                            f"""This is food preferences and conditions for user Greg.
                            --when giving recommendation, prioritize preferences and conditions
                            --Some preferences have an associated 'constraints'. Only use these rules if the constraints are present. When in doubt, as about any conditions present. User will likely tell you if conditions are present. 
                            --The conditions list has additional context on logistical rules related to preferences. They be related to time equipment that may effect how a user will be able to cook a certain meal
                            --Once you have preferences and or conditions, tell the user you have uploaded the preferences into your system.
                            --Preferences are pairwise comparisons. Rank preferences based on all pairwise comparisons before giving answers
                            --"Reasoning" column is context. Weight your attention based on this column appropriateness.
                            --"Example" column is additional logic context with specific templates. They are just logic templates and your answers should be agnostic to the food or processes described in the examples. Weight your attention based on this column appropriateness.
    
                            *PREFERENCES AND CONDITIONS DATABASE CONTENT FOLLOWS*:
                            {str(prefs)} ~~*END PREFERENCES CONTENT*~~
                            
                            *CONDITIONS DATABASE CONTENT FOLLOWS*:
                            {str(conditions)} ~~*END CONDITIONS DATABASE CONTENT*~~
                            
                            
                            """
                        }

                        # Update messages in correct sequence
                        self.messages.append(assistant_message)
                        self.messages.append(function_call_result_message
                                             )  # Required tool response
                        self.messages.append(database_context)

                        # Second API call
                        completion_payload = {
                            "model": 'gpt-4o-mini',
                            "messages": self.messages
                        }

                        # DEBUG: Print a slice of the API call payload
                        print(
                            f"DEBUG: first few messages: {self.messages[:10]}")

                        # Second API call
                        second_response = requests.post(
                            'https://api.openai.com/v1/chat/completions',
                            headers=headers,
                            json=completion_payload)
                        second_response.raise_for_status()

                        # Process final response
                        second_response_json = second_response.json()
                        final_assistant_message = second_response_json[
                            'choices'][0]['message']

                        # Add final response to conversation
                        self.messages.append(final_assistant_message)

                        return final_assistant_message.get(
                            'content', 'No content in response.')

                    else:
                        return f"Unknown function called: {function_name}"

            else:
                # If no function call, add the assistant's message to the conversation
                self.messages.append(assistant_message)
                return assistant_message.get('content',
                                             'No content in the response.')

        except requests.RequestException as e:
            error_message = f"Error in OpenAI request: {str(e)}"
            # Add more detailed information about the error
            if hasattr(e, 'response') and e.response is not None:
                error_message += f"\nResponse Status: {e.response.status_code}"
                error_message += f"\nResponse Body: {e.response.text}"
            return error_message

    def agentchat(self, prompt=None):
        print('DEBUG: agent chat triggered')
        print(f"DEBUG: user_id {self.user_id}")

        # Add user input to messages

        self.messages.append({"role": "user", "content": prompt})

        # Get response from OpenAI
        response = self.openai_request()

        #function: add chats to google sheets
        try:
            #print (f"DEBUG: attempt chatlog entry:")
            #self.logger.log_conversation(str(self.messages))
            add_chatlog_entry(self.messages)

        except:
            print("Error adding chatlog entry agentchat")
            logger.info(f"Error adding chatlog entry agentchat")

        # try:
        #     #print (f"DEBUG: attempt chatlog entry:")
        #     auto_postprocess(self.messages)
        # except:
        #     print("Error adding summary")
        return response


# Example usage
if __name__ == "__main__":
    import sys
    handler = AIHandler()

    if sys.stdin.isatty() and not os.environ.get('REPLIT_DEPLOYMENT'):
        while True:
            try:
                user_input = input("Enter your prompt (or 'quit' to exit): ")
                if user_input.lower() == 'quit':
                    break
                response = handler.agentchat(user_input)
                print("\nResponse:", response, "\n")
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")
