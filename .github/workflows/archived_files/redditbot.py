import os
import json
import praw
from openai import OpenAI
from urllib.parse import urlparse
from datetime import datetime

# --- Reddit API Setup (from original redditapi.py) ---
reddit_client_id = "Dt--G6c6Plu1o5bqwZ4AdQ"
reddit_client_secret = os.environ.get('REDDIT_CLIENT_SECRET')
reddit_user_agent = "scrapetest/1.0 by International_Carob9"

# Initialize Reddit instance
try:
    reddit = praw.Reddit(
        client_id=reddit_client_id,
        client_secret=reddit_client_secret,
        user_agent=reddit_user_agent
    )
    reddit.user.me() # Test authentication
    print("Reddit API connection successful.")
except Exception as e:
    print(f"Error initializing PRAW Reddit instance: {e}")
    print("Please ensure your REDDIT_CLIENT_SECRET environment variable is set.")
    # Consider exiting if Reddit connection is essential
    # exit(1)

# --- OpenAI Configuration (from searchbot.py) ---
openai_api_key = os.environ.get('OPENAI_API_KEY')
MODEL = "gpt-4o-mini"
MAX_INTERACTIONS = 5 # Keep interaction limit

if not openai_api_key:
    print("Warning: OPENAI_API_KEY environment variable not found.")
    # exit(1) # Optional: exit if key is missing

system_instruction = """You are a helpful assistant that scrapes Reddit. \
You can retrieve and process information from specific Reddit posts using their URLs. \
Use the available function to fetch the post and comment data when asked about a Reddit URL. \ 
You must attach a reddit user name and url to each summary point to prove it is real and can be inspected. \
Only return information scrapped from Reddit. Never use your own internal knowledge \
     You are called in a function loop and may search multiple times. \
     Always ensure that once you have finished scraping the original urls, stop and return results to the user """

# --- Tool Function Definitions (from redditapi.py) ---

def comment_to_dict(comment):
    """Convert a comment and its replies to a dictionary recursively."""
    # Limit recursion depth or comment count if needed
    replies = []
    try:
        # Accessing replies can sometimes cause issues, wrap in try/except
        replies = [comment_to_dict(reply) for reply in comment.replies]
    except Exception as e:
        print(f"Warning: Could not process replies for comment {comment.id}: {e}")
    return {
        "author": str(comment.author),
        "score": comment.score,
        "created": datetime.fromtimestamp(comment.created_utc).isoformat(),
        "body": comment.body,
        "replies": replies # Include processed replies
    }

def search_reddit_with_url(urls):
    """
    Scrapes Reddit post URLs provided by the user.
    Fetches the post content and top-level comments.
    Returns structured data for each URL.
    """
    if isinstance(urls, str):
        urls = [urls] # Ensure it's a list

    results = []
    for url in urls:
        print(f"Processing Reddit URL: {url}")
        try:
            # Parse URL
            parsed_url = urlparse(url)
            path_parts = parsed_url.path.strip('/').split('/')
            if 'reddit.com' not in parsed_url.netloc.lower() or 'comments' not in path_parts:
                 raise ValueError(f"Invalid or non-post Reddit URL: {url}")

            submission_id = None
            for i, part in enumerate(path_parts):
                if part == 'comments' and i + 1 < len(path_parts):
                    submission_id = path_parts[i + 1]
                    break
            if not submission_id:
                raise ValueError(f"Could not extract submission ID from URL: {url}")

            # Fetch submission
            submission = reddit.submission(id=submission_id)
            # Fetch limited comments to avoid context overflow
            submission.comment_sort = 'top' # or 'best'
            submission.comments.replace_more(limit=0) # Fetch only top-level comments, limit further if needed

            # Limit the number of comments processed
            MAX_COMMENTS = 10
            comments_data = []
            for i, top_level_comment in enumerate(submission.comments):
                if i >= MAX_COMMENTS:
                    break
                comments_data.append(comment_to_dict(top_level_comment))


            post_data = {
                "post": {
                    "title": submission.title,
                    "author": str(submission.author),
                    "subreddit": str(submission.subreddit),
                    "score": submission.score,
                    "created": datetime.fromtimestamp(submission.created_utc).isoformat(),
                    "url": submission.url,
                    "selftext": submission.selftext if submission.is_self else None
                },
                "comments_summary": f"Top {len(comments_data)} comments fetched.", # Indicate truncation
                "comments": comments_data # Return limited comments
            }
            results.append(post_data)
            print(f"Successfully processed: {url}")

        except praw.exceptions.PRAWException as pe:
             print(f"PRAW error processing {url}: {pe}")
             results.append({"error": f"Reddit API/PRAW error: {str(pe)}", "url": url})
        except ValueError as ve:
             print(f"URL error processing {url}: {ve}")
             results.append({"error": f"Invalid URL format: {str(ve)}", "url": url})
        except Exception as e:
            print(f"Unexpected error processing {url}: {e}")
            results.append({"error": f"An unexpected error occurred: {str(e)}", "url": url})

    # Return JSON string to ensure it's easily passable to the LLM
    return json.dumps(results, indent=2)


# --- Agent Tools Definition ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_reddit_with_url",
            "description": "Fetches the content and comments for one or more given Reddit post URLs. You must provide a list of URLs as the parameter",
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array", # Expecting a list of URLs now
                        "items": {
                            "type": "string",
                            "description": "A single, full Reddit post URL."
                        },
                        "description": "A list containing one or more full Reddit post URLs to scrape.",
                    }
                },
                "required": ["urls"]
            },
        }
    }
]

# --- Available Functions Mapping ---
AVAILABLE_FUNCTIONS = {
    "search_reddit_with_url": search_reddit_with_url
}

# --- Agent Loop (adapted from searchbot.py) ---
def reddit_agent(user_instruction: str, urls: list = ''):
    try:
        client = OpenAI(api_key=openai_api_key)
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")
        return

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f'{user_instruction} {urls}'}
    ]

    print(f"\nStarting Reddit agent loop with instruction: '{user_instruction}'")
    print(f"Max interactions set to: {MAX_INTERACTIONS}")

    for i in range(MAX_INTERACTIONS):
        print(f"\n--- Interaction from reddditbot.py {i + 1} ---")
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            if tool_calls:
                messages.append(response_message) # Add assistant's request
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_to_call = AVAILABLE_FUNCTIONS.get(function_name)
                    if not function_to_call:
                        print(f"Error: Unknown function '{function_name}' requested.")
                        messages.append({
                            "tool_call_id": tool_call.id, "role": "tool", "name": function_name,
                            "content": f"Error: Function '{function_name}' not found."
                        })
                        continue

                    try:
                        function_args = json.loads(tool_call.function.arguments)
                        print(f"Requesting call: {function_name} with args: {function_args}")
                        # Ensure 'urls' argument is passed correctly
                        function_response = function_to_call(urls=function_args.get("urls"))

                        messages.append({
                            "tool_call_id": tool_call.id, "role": "tool", "name": function_name,
                            "content": str(function_response) # Ensure response is string
                        })
                    except Exception as e:
                        print(f"Error calling function {function_name}: {e}")
                        messages.append({
                            "tool_call_id": tool_call.id, "role": "tool", "name": function_name,
                            "content": f"Error executing function {function_name}: {str(e)}"
                        })
            else:
                final_response = response_message.content
                print(f"\n--- Final Response from Reddit Agent ---")
                print(final_response)
                messages.append(response_message)
                return final_response # Exit loop on final answer

        except Exception as e:
            print(f"An error occurred during the API call or processing: {e}")
            break
    else:
        print("\n--- Reddit agent loop finished: Max interactions reached. ---")
        last_message = messages[-1]
        if last_message['role'] == 'assistant':
             print("Last message:", last_message.get('content', 'No content'))
        else:
             print("Loop ended without final assistant message.")
             return "Loop ended without final assistant message."


# --- Main Execution ---
if __name__ == "__main__":
    if not os.getenv("REDDIT_CLIENT_SECRET"):
         print("Warning: REDDIT_CLIENT_SECRET environment variable not found.")
         # exit(1) # Optional

    # Test instruction - replace with your desired test
    searruction = "Summarize this post: https://www.reddit.com/r/Baking/comments/14meyc0/whats_your_best_cookie_recipe/"
    result = reddit_agent(test_instruction)
    print("Test Result:", result)


    """
    scrape the urls for practical tips from comments. summarize for the user with commenter names urls and their tip"""