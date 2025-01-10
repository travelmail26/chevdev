import json
import os
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials


##logging
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
# Path to your service account JSON file
SERVICE_ACCOUNT_FILE = os.environ['SERVICE_ACCOUNT_FILE_PH']
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


def sheets_call(tab='database'):
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_FILE)
        creds = Credentials.from_service_account_info(service_account_info,
                                                      scopes=SCOPES)
        client = gspread.authorize(creds)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error with credentials: {e}")
        return None
    except Exception as e:
        print(f"Unexpected credential error: {e}")
        return None

    try:
        spreadsheet_id = '1RsNekDFNwk67j66g57VN3WOUM2I-4yXGfVtWUg56C20'
        sheet_name = tab
        # print(f"Attempting to open the spreadsheet with ID: {spreadsheet_id}")
        spreadsheet = client.open_by_key(spreadsheet_id)
        sheet = spreadsheet.worksheet(sheet_name)
        data = sheet.get_all_values()
    except gspread.exceptions.APIError as e:
        print(f"Google Sheets API error: {e}")
        return None
    except gspread.exceptions.WorksheetNotFound:
        print(f"Worksheet '{sheet_name}' not found")
        return None
    except Exception as e:
        print(f"Error accessing spreadsheet: {e}")
        return None
    #print('json format', json.dumps(data))

    # print ('get all values', sheet.get_all_values())
    # print ('get A value', sheet.acell('A1').value)

    ## turn data into json format
    headers = data[0]
    # Initialize a list to hold all row dictionaries
    all_rows = []

    # Loop through each row (skipping the header row)
    for row in data[1:]:
        row_dict = {}  # Initialize an empty dictionary for each row
        for i in range(len(headers)):
            print(headers[i])
            print(row[i])
            row_dict[headers[i]] = row[
                i]  # Assign each header as a key and the corresponding row value as the value
        all_rows.append(row_dict)

    json_data = all_rows
    return json_data


def add_chatlog_entry(entry):
    print('DEBUG: chatlog entry triggered')
    logging.info("DEBUG: chatlog entry triggered")
    if not entry:  # This checks if entry is None, empty string, or any falsy value
        print("No entry provided. Skipping chatlog update.")
        return
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_FILE)
        creds = Credentials.from_service_account_info(service_account_info,
                                                      scopes=SCOPES)
        client = gspread.authorize(creds)
    except FileNotFoundError:
        print(
            f"Error: Service account file not found at path: {SERVICE_ACCOUNT_FILE}"
        )
        return

    spreadsheet_id = '1RsNekDFNwk67j66g57VN3WOUM2I-4yXGfVtWUg56C20'
    chatlog_sheet_name = 'chatlog'
    spreadsheet = client.open_by_key(spreadsheet_id)
    chatlog_sheet = spreadsheet.worksheet(chatlog_sheet_name)

    # Create new_row with current timestamp and entry
    current_time = datetime.now().isoformat()
    new_row = [current_time, str(entry)]
        
    try:
        chatlog_sheet.append_row(new_row)
        return True
        #print(f"Added new row to 'chatlog': {new_row}")
    except gspread.exceptions.APIError as e:
        print(f"Google Sheets API error occurred: {e}")
    except gspread.exceptions.GSpreadException as e:
        print(f"An unspecified error occurred with gspread: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def fetch_chatlog(entry=None, timestamp=None):
    print('DEBUG: fetch chatlog entry triggered')
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_FILE)
        creds = Credentials.from_service_account_info(service_account_info,
                                                      scopes=SCOPES)
        client = gspread.authorize(creds)
    except FileNotFoundError:
        print(
            f"Error: Service account file not found at path: {SERVICE_ACCOUNT_FILE}"
        )
        return
    #spreadsheet_id = '1HiSZNWimhPHUW7CuXc-rBNLR55tYhbagQa0EgF8nHn8'
    spreadsheet_id = '1RsNekDFNwk67j66g57VN3WOUM2I-4yXGfVtWUg56C20'
    chatlog_sheet_name = 'chatlog'
    spreadsheet = client.open_by_key(spreadsheet_id)
    chatlog_sheet = spreadsheet.worksheet(chatlog_sheet_name)
    try:
        data = chatlog_sheet.get_all_values()
    except gspread.exceptions.APIError as e:
        print(f"Google Sheets API error occurred: {e}")
        return None  # Return None to indicate an error
    except gspread.exceptions.GSpreadException as e:
        print(f"An unspecified error occurred with gspread: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

    headers = data[0]
    # Initialize a list to hold all row dictionaries
    all_rows = []

    # Loop through each row (skipping the header row)
    for row in data[1:]:
        row_dict = {}  # Initialize an empty dictionary for each row
        for i in range(len(headers)):
            row_dict[headers[i]] = row[
                i]  # Assign each header as a key and the corresponding row value as the value
        all_rows.append(row_dict)

    json_data = all_rows
    #print('***DEBUG JSON BEGINING', json_data[25], "***END JSON DATA")
    return json_data[25:30]

def task_create(id, date, title, description, notes=None):
    print('DEBUG: task create triggered')
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_FILE)
        creds = Credentials.from_service_account_info(service_account_info,
                                                      scopes=SCOPES)
        client = gspread.authorize(creds)
    except FileNotFoundError:
        print(f"Error: Service account file not found")
        return

    spreadsheet_id = '1RsNekDFNwk67j66g57VN3WOUM2I-4yXGfVtWUg56C20'  # Use your spreadsheet ID
    tasks_sheet_name = 'tasks'  # Name of your tasks sheet

    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        tasks_sheet = spreadsheet.worksheet(tasks_sheet_name)

        # Create new row with the task data
        new_row = [str(id), str(date), str(title), str(description), str(notes)]

        tasks_sheet.append_row(new_row)
        print(f"Added new task: {new_row}")
        return True

    except Exception as e:
        print(f"An error occurred while creating task: {e}")
        return False

def fetch_preferences():
    print('DEBUG: fetch preferences triggered')
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_FILE)
        creds = Credentials.from_service_account_info(service_account_info,
                                                      scopes=SCOPES)
        client = gspread.authorize(creds)
    except FileNotFoundError:
        print(f"Error: Service account file not found")
        return None

    spreadsheet_id = '1RsNekDFNwk67j66g57VN3WOUM2I-4yXGfVtWUg56C20'
    SHEET_NAMES = {
        'preferences': 'preferences',
        'conditions': 'conditions'
    }

    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        preferences_sheet = spreadsheet.worksheet(SHEET_NAMES['preferences'])
        conditions_sheet = spreadsheet.worksheet(SHEET_NAMES['conditions'])

        # Get all values from the preferences sheet
        preferences_data = preferences_sheet.get_all_values()

        # Extract headers and convert preferences data into dictionary
        headers = preferences_data[0]
        preferences_rows = []
        for row in preferences_data[1:]:
            row_dict = {}
            for i in range(len(headers)):
                row_dict[headers[i]] = row[i]
            preferences_rows.append(row_dict)

        # Get all values from the conditions sheet
        conditions_data = conditions_sheet.get_all_values()

        # Extract headers and convert conditions data into dictionary
        headers = conditions_data[0]
        conditions_rows = []
        for row in conditions_data[1:]:
            row_dict = {}
            for i in range(len(headers)):
                row_dict[headers[i]] = row[i]
            conditions_rows.append(row_dict)

        # Return both dictionaries
        return preferences_rows, conditions_rows

    except gspread.exceptions.APIError as e:
        print(f"Google Sheets API error occurred: {e}")
        return None, None
    except gspread.exceptions.GSpreadException as e:
        print(f"An unspecified error occurred with gspread: {e}")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None, None

def fetch_chatlog_time(beginning=None, end=None):
    print('DEBUG: fetch chatlog entry triggered')
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_FILE)
        creds = Credentials.from_service_account_info(service_account_info,
                                                      scopes=SCOPES)
        client = gspread.authorize(creds)
    except FileNotFoundError:
        print(
            f"Error: Service account file not found at path: {SERVICE_ACCOUNT_FILE}"
        )
        return

    spreadsheet_id = '1RsNekDFNwk67j66g57VN3WOUM2I-4yXGfVtWUg56C20'
    chatlog_sheet_name = 'chatlog'
    spreadsheet = client.open_by_key(spreadsheet_id)
    chatlog_sheet = spreadsheet.worksheet(chatlog_sheet_name)

    try:
        data = chatlog_sheet.get_all_values()
    except gspread.exceptions.APIError as e:
        print(f"Google Sheets API error occurred: {e}")
        return None
    except gspread.exceptions.GSpreadException as e:
        print(f"An unspecified error occurred with gspread: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

    headers = data[0]
    all_rows = []

    # Convert ISO format datetime strings to datetime objects
    start_date = datetime.fromisoformat(beginning) if beginning else None
    end_date = datetime.fromisoformat(end) if end else None

    # If neither start nor end date is specified, return the last row with data
    if not start_date and not end_date:
        if len(data) > 1:  # There is data beyond header row
            headers = data[0]
            last_row = data[-1]
            return [{headers[i]: last_row[i] for i in range(len(headers))}]
        return []  # In case there is no data at all

    # Loop through each row (skipping the header row)
    for row in data[1:]:
        try:
            # Parse the ISO format datetime from the first column
            row_datetime = datetime.fromisoformat(row[0])

            # Check if the row datetime is within the specified range
            if ((not start_date or row_datetime >= start_date) and 
                (not end_date or row_datetime <= end_date)):
                row_dict = {}
                for i in range(len(headers)):
                    row_dict[headers[i]] = row[i]
                all_rows.append(row_dict)
        except ValueError as e:
            # Skip rows with invalid datetime format
            print(f"Skipping row with invalid datetime: {row[0]}, error: {e}")
            continue

    #print('***DEBUG JSON BEGINING', all_rows[0] if all_rows else "No matching rows", "***END JSON DATA")
    return all_rows

def fetch_recipes():
    print('DEBUG: fetch recipes triggered')
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_FILE)
        creds = Credentials.from_service_account_info(service_account_info,
                                                      scopes=SCOPES)
        client = gspread.authorize(creds)
    except FileNotFoundError:
        print(f"Error: Service account file not found")
        return None

    spreadsheet_id = '1RsNekDFNwk67j66g57VN3WOUM2I-4yXGfVtWUg56C20'
    recipes_sheet_name = 'recipes'

    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        recipes_sheet = spreadsheet.worksheet(recipes_sheet_name)

        # Get all values from the recipes sheet
        recipes_data = recipes_sheet.get_all_values()

        # Extract headers and convert recipes data into dictionary
        headers = recipes_data[0]
        recipes_rows = []
        for row in recipes_data[1:]:
            row_dict = {}
            for i in range(len(headers)):
                row_dict[headers[i]] = row[i]
            recipes_rows.append(row_dict)

        print (f"DEBUG: recipes rows: {recipes_rows[0:2]}")
        return recipes_rows

    except gspread.exceptions.APIError as e:
        print(f"Google Sheets API error occurred: {e}")
        return None
    except gspread.exceptions.GSpreadException as e:
        print(f"An unspecified error occurred with gspread: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def add_insight(entry):
    print('DEBUG: insight entry triggered')
    if not entry:  # This checks if entry is None, empty string, or any falsy value
        print("No entry provided. Skipping chatlog update.")
        return
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_FILE)
        creds = Credentials.from_service_account_info(service_account_info,
                                                      scopes=SCOPES)
        client = gspread.authorize(creds)
    except FileNotFoundError:
        print(
            f"Error: Service account file not found at path: {SERVICE_ACCOUNT_FILE}"
        )
        return

    spreadsheet_id = '1RsNekDFNwk67j66g57VN3WOUM2I-4yXGfVtWUg56C20'
    chatlog_sheet_name = 'insights'
    spreadsheet = client.open_by_key(spreadsheet_id)
    chatlog_sheet = spreadsheet.worksheet(chatlog_sheet_name)

    # Create new_row with current timestamp and entry
    current_time = datetime.now().isoformat()
    new_row = [current_time, str(entry)]

    try:
        chatlog_sheet.append_row(new_row)
        #print(f"Added new row to 'chatlog': {new_row}")
    except gspread.exceptions.APIError as e:
        print(f"Google Sheets API error occurred: {e}")
    except gspread.exceptions.GSpreadException as e:
        print(f"An unspecified error occurred with gspread: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def update_task(task_id, updates):
    """
    Update specific columns of a task by ID.
    Args:
        task_id (str): The ID of the task to update
        updates (dict): Dictionary of column names and new values to update
    Returns:
        bool: True if successful, False otherwise
    """
    print('DEBUG: update task triggered')
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_FILE)
        creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        client = gspread.authorize(creds)
    except FileNotFoundError:
        print(f"Error: Service account file not found")
        return False

    spreadsheet_id = '1RsNekDFNwk67j66g57VN3WOUM2I-4yXGfVtWUg56C20'
    tasks_sheet_name = 'tasks'

    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        tasks_sheet = spreadsheet.worksheet(tasks_sheet_name)

        # Get all data and find row with matching ID
        data = tasks_sheet.get_all_values()
        headers = data[0]

        # Find ID column index
        id_col = headers.index('id')

        # Find row with matching ID
        row_idx = None
        for idx, row in enumerate(data[1:], start=2):  # start=2 because sheets are 1-indexed and we skip header
            if row[id_col] == str(task_id):
                row_idx = idx
                break

        if not row_idx:
            print(f"Task with ID {task_id} not found")
            return False

        # Update specified columns
        for col_name, new_value in updates.items():
            if col_name in headers:
                col_idx = headers.index(col_name) + 1  # Convert to A1 notation
                tasks_sheet.update_cell(row_idx, col_idx, str(new_value))

        return True

    except Exception as e:
        print(f"An error occurred while updating task: {e}")
        return False

def fetch_sheet_data_rows(tab_name, start_row=None, end_row=None):
    """
    Fetches specific rows from a sheet tab efficiently using batch_get

    Args:
        tab_name (str): Name of the sheet tab to fetch from
        start_row (int, optional): Starting row number (1-based indexing)
        end_row (int, optional): Ending row number (1-based indexing)

    Returns:
        list: List of dictionaries containing the row data with headers as keys
    """
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_FILE)
        creds = Credentials.from_service_account_info(service_account_info,
                                                      scopes=SCOPES)
        client = gspread.authorize(creds)
    except FileNotFoundError:
        print(f"Error: Service account file not found")
        return None

    spreadsheet_id = '1RsNekDFNwk67j66g57VN3WOUM2I-4yXGfVtWUg56C20'

    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        sheet = spreadsheet.worksheet(tab_name)

        # First, get just the headers
        headers = sheet.row_values(1)

        # Calculate range
        start = start_row if start_row else 2
        end = end_row if end_row else sheet.row_count

        # Fetch specified rows
        rows = sheet.batch_get([f'A{start}:Z{end}'])[0]

        # Convert to list of dicts
        return [dict(zip(headers, row)) for row in rows]

        return result_rows

    except gspread.exceptions.WorksheetNotFound:
        print(f"Sheet tab '{tab_name}' not found")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

if __name__ == "__main__":
    sheets_call()
    add_chatlog_entry(entry=None)
    fetch_chatlog()
    task_create(id=None, date=None, title=None, description=None, notes=None)
    fetch_preferences()
    fetch_chatlog_time(beginning=None, end=None)
