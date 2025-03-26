import praw
import sys
from urllib.parse import urlparse
from datetime import datetime
import os

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

def scrape_reddit_url(url):
    try:
        # Parse the URL to get the submission ID
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split('/')
        
        # Check if it's a valid Reddit URL
        if 'reddit.com' not in parsed_url.netloc.lower():
            print("Error: Please enter a valid Reddit URL")
            return
        
        # Find submission ID in URL
        submission_id = None
        for i, part in enumerate(path_parts):
            if part == 'comments' and i + 1 < len(path_parts):
                submission_id = path_parts[i + 1]
                break
        
        if not submission_id:
            print("Error: Could not find submission ID in URL")
            return

        # Get submission data
        submission = reddit.submission(id=submission_id)
        
        # Print post information
        print("\nScraped Reddit Post Information:")
        print("=" * 50)
        print(f"Title: {submission.title}")
        print(f"Author: {submission.author}")
        print(f"Subreddit: r/{submission.subreddit}")
        print(f"Score: {submission.score}")
        print(f"Number of Comments: {submission.num_comments}")
        print(f"Created: {datetime.fromtimestamp(submission.created_utc)}")
        print(f"URL: {submission.url}")
        
        # Print full post content if it's a text post
        if submission.is_self and submission.selftext:
            print("\nFull Post Content:")
            print("-" * 50)
            print(submission.selftext)
        
        # Get all comments
        print("\nComments:")
        print("=" * 50)
        
        # Replace MoreComments objects with actual comments
        submission.comments.replace_more(limit=None)
        
        # Counter for comments
        comment_count = 0
        
        # Iterate through all comments
        for comment in submission.comments.list():
            comment_count += 1
            print(f"\nComment #{comment_count}")
            print("-" * 50)
            print(f"Author: {comment.author}")
            print(f"Score: {comment.score}")
            print(f"Created: {datetime.fromtimestamp(comment.created_utc)}")
            print(f"Depth: {comment.depth}")
            print("Body:")
            print(comment.body)
        
        print(f"\nTotal comments found: {comment_count}")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")

def main():
    print("Reddit URL Scraper - Full Post and Comments")
    print("For personal use only")
    print("Developer: International_Carob9")
    print("=" * 50)
    
    while True:
        url = input("\nEnter a Reddit URL (or 'quit' to exit): ")
        
        if url.lower() == 'quit':
            print("Exiting program...")
            break
            
        scrape_reddit_url(url)

if __name__ == "__main__":
    main()