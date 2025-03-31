import praw
import sys
from urllib.parse import urlparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import os
import json

# Reddit API credentials
client_id = "Dt--G6c6Plu1o5bqwZ4AdQ"
client_secret = os.environ.get('REDDIT_CLIENT_SECRET')
user_agent = "scrapetest/1.0 by International_Carob9"

# Initialize Reddit instance
reddit = praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    user_agent=user_agent
)

URLS = ['https://www.reddit.com/r/Baking/comments/11v4d9f/help_me_fix_my_chocolate_chip_cookie_fail/']

def comment_to_dict(comment):
    """Convert a comment and its replies to a dictionary recursively."""
    return {
        "author": str(comment.author),
        "score": comment.score,
        "created": datetime.fromtimestamp(comment.created_utc).isoformat(),
        "body": comment.body,
        "replies": [comment_to_dict(reply) for reply in comment.replies]
    }

def scrape_single_url(url):
    """Scrape a single Reddit URL and return data as a dictionary."""
    try:
        # Parse URL to extract submission ID
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split('/')
        if 'reddit.com' not in parsed_url.netloc.lower():
            raise ValueError("Invalid Reddit URL")
        submission_id = None
        for i, part in enumerate(path_parts):
            if part == 'comments' and i + 1 < len(path_parts):
                submission_id = path_parts[i + 1]
                break
        if not submission_id:
            raise ValueError("Could not find submission ID in URL")

        # Fetch submission data
        submission = reddit.submission(id=submission_id)
        submission.comments.replace_more(limit=None)  # Fetch all comments

        # Structure post and comment data
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
            "comments": [comment_to_dict(comment) for comment in submission.comments]
        }
        return post_data
    except Exception as e:
        return {"error": str(e), "url": url}

def scrape_reddit_urls(urls):
    """Scrape multiple URLs in parallel and return results."""
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(scrape_single_url, urls))
    return results

def main():
    # Scrape the predefined URLs
    results = scrape_reddit_urls(URLS)
    
    # Output results as JSON
    print(len(json.dumps(results, indent=2)))
    # Alternatively, return results for use in another script
    # return results

if __name__ == "__main__":
    main()