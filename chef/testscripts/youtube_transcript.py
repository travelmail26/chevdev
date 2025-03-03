from youtube_transcript_api import YouTubeTranscriptApi
import re

def extract_video_id(url):
    """Extract the video ID from a YouTube URL."""
    # Look for patterns like ?v= or /v/
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([^&\n?]*)',  # Standard YouTube URLs
        r'youtube.com/shorts/([^&\n?]*)',     # Shorts URLs
    ]

    for pattern in patterns:
        video_id_match = re.search(pattern, url)
        if video_id_match:
            return video_id_match.group(1)
    return None

def get_youtube_transcript(url):
    try:
        # Extract video ID from URL
        video_id = extract_video_id(url)
        if not video_id:
            return "Invalid YouTube URL"

        # Get transcript
        transcript = YouTubeTranscriptApi.get_transcript(video_id)

        # Combine all text parts
        full_transcript = ""
        for entry in transcript:
            full_transcript += entry['text'] + " "

        return full_transcript.strip()

    except Exception as e:
        return f"Error getting transcript: {str(e)}"

if __name__ == "__main__":
    # Manual URL input
    url = input("Enter YouTube URL: ")

    # Get and print transcript
    transcript = get_youtube_transcript(url)
    print("\nTranscript:")
    print(transcript)