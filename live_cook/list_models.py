
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get("GOOGLE_API_KEY")

client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1alpha'})

try:
    print("Listing models...")
    for model in client.models.list(config={"page_size": 100}):
        if "generateContent" in model.supported_actions:
            print(f"- {model.name} (Methods: {model.supported_actions})")
except Exception as e:
    print(f"Error: {e}")
