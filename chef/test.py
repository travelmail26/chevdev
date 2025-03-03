
import os


import logging

import requests

# Target video
VIDEO_ID = "mQvQaDuqIvM"

# Setup session
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/98.0.4758.102 Safari/537.36',
})

def debug_transcript_api():
    # Try different API endpoints and parameters
    apis = [
        # Standard timedtext API
        f"https://www.youtube.com/api/timedtext?v={VIDEO_ID}&lang=en",
        
        # List available captions
        f"https://www.youtube.com/api/timedtext?v={VIDEO_ID}&type=list",
        
        # Try auto-generated captions
        f"https://www.youtube.com/api/timedtext?v={VIDEO_ID}&lang=en&kind=asr",
        
        # Try with different language
        f"https://www.youtube.com/api/timedtext?v={VIDEO_ID}&lang=en-US"
    ]
    
    for i, api_url in enumerate(apis):
        print(f"\n--- Test {i+1}: {api_url} ---")
        response = session.get(api_url)
        
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'unknown')}")
        print(f"Content length: {len(response.text)} bytes")
        
        # Print full response content for detailed inspection
        print(f"Response content: {repr(response.text[:200])}...")
        
        # Save response to file
        with open(f"response_{i+1}.txt", "w", encoding="utf-8") as f:
            f.write(response.text)

if __name__ == "__main__":
    print(f"Debugging transcript APIs for video: {VIDEO_ID}\n")
    debug_transcript_api()
    
    # Also check if video exists
    print("\n--- Checking if video exists ---")
    video_info_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={VIDEO_ID}&format=json"
    response = session.get(video_info_url)
    
    if response.status_code == 200:
        print(f"Video exists: {response.json().get('title', 'Unknown title')}")
    else:
        print(f"Video might not exist or be private: Status {response.status_code}")

# from google.oauth2.credentials import Credentials
# from googleapiclient.discovery import build
# import gspread
# import json
# from datetime import datetime

# import gspread
# from google.oauth2.service_account import Credentials


# ##logging
# import logging

# # Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s - %(message)s",
#     handlers=[logging.StreamHandler()]
# )
# # Path to your service account JSON file
# SERVICE_ACCOUNT_FILE = os.environ['SERVICE_ACCOUNT_FILE_PH']
# SCOPES = [
#     'https://www.googleapis.com/auth/spreadsheets',
#     'https://www.googleapis.com/auth/drive'
# ]

# from google.oauth2.service_account import Credentials
# from googleapiclient.discovery import build
# import json
# from datetime import datetime

# from google.oauth2.service_account import Credentials
# from googleapiclient.discovery import build
# import json
# from datetime import datetime

# from google.oauth2.service_account import Credentials
# from googleapiclient.discovery import build
# import json
# from datetime import datetime

# from google.oauth2.service_account import Credentials
# from googleapiclient.discovery import build
# import json
# from datetime import datetime

# from google.oauth2.service_account import Credentials
# from googleapiclient.discovery import build
# import json
# from datetime import datetime

# def fetch_chatlog_time(beginning=None, end=None):
#     print('DEBUG: fetch chatlog entry triggered')

#     try:
#         # Load credentials and initialize the Sheets API client
#         service_account_info = json.loads(SERVICE_ACCOUNT_FILE)
#         creds = Credentials.from_service_account_info(
#             service_account_info, scopes=SCOPES
#         )
#         sheets_service = build('sheets', 'v4', credentials=creds, cache_discovery=False)
#     except FileNotFoundError:
#         print(f"Error: Service account file not found.")
#         return None

#     # Google Sheets details
#     spreadsheet_id = '1RsNekDFNwk67j66g57VN3WOUM2I-4yXGfVtWUg56C20'
#     date_column_a1 = 'chatlog!A:C'  # Assuming the date is in column A and more data is in B and C

#     # Parse the provided beginning and end dates into datetime objects
#     try:
#         start_date = datetime.strptime(beginning, '%Y-%m-%d') if beginning else None
#         end_date = datetime.strptime(end, '%Y-%m-%d') if end else None
#     except ValueError as e:
#         print(f"Error: Invalid date format. Please use 'YYYY-MM-DD'. Details: {e}")
#         return None

#     # Prepare the DataFilters
#     data_filters = [
#         {
#             "a1Range": date_column_a1  # Specify the range to fetch
#         }
#     ]

#     try:
#         # Make the request to the Sheets API
#         response = sheets_service.spreadsheets().values().batchGetByDataFilter(
#             spreadsheetId=spreadsheet_id,
#             body={
#                 "dataFilters": data_filters,
#                 "majorDimension": "ROWS",  # Data is returned in rows
#                 "valueRenderOption": "FORMATTED_VALUE",  # Default formatted value
#                 "dateTimeRenderOption": "FORMATTED_STRING"  # Ensure dates are strings
#             }
#         ).execute()

#         # Extract values from the response
#         value_ranges = response.get('valueRanges', [])
#         if not value_ranges or 'values' not in value_ranges[0]['valueRange']:
#             print("No matching rows found.")
#             return []

#         # Process rows to filter by date range
#         rows = value_ranges[0]['valueRange']['values']
#         headers = rows[0]  # First row is the header
#         filtered_rows = []

#         for row in rows[1:]:  # Skip the header row
#             try:
#                 # Parse the date in the first column
#                 row_date = datetime.strptime(row[0], '%Y-%m-%d')
#                 if ((not start_date or row_date >= start_date) and
#                     (not end_date or row_date <= end_date)):
#                     filtered_rows.append({headers[i]: row[i] for i in range(len(headers))})
#             except ValueError:
#                 print(f"Skipping row with invalid date: {row[0]}")

#         return filtered_rows

#     except Exception as e:
#         print(f"Error fetching filtered data: {e}")
#         return None







# print(fetch_chatlog_time(beginning='2025-1-15', end='2025-1-17'))

# script_dir = os.path.dirname(__file__)

# with open(os.path.join(script_dir, 'instructions_base.txt'), 'r') as file:
#     content = file.read()
#     print(content[:10])
    #system_content_parts.append("=== BASE DEFAULT INSTRUCTIONS ===\n" + content)

#from telegram_bot import setup_bot

# def test_setup_bot():
#     try:
#         # Call the setup_bot function
#         app = setup_bot()
#         print("setup_bot executed successfully.")
#     except Exception as e:
#         # Catch and log any exceptions
#         logging.error(f"Error in setup_bot: {e}")
#         print(f"Error in setup_bot: {e}")

# if __name__ == "__main__":
#     test_setup_bot()


# value = os.environ.get('PRODUCTION_OR_DEVELOPMENT')

# print (value)


#print(fetch_sheet_data_rows('recipe_hummus'))

