import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import firestore as gc_firestore
from datetime import datetime
import csv

# name: projects/cheftest-f174c/databases/cheftestfirestore


cred_dict = json.loads(os.environ['FIREBASEJSON'])

current_time = datetime.now().isoformat()

def parse_date(date_string):
    """
    Parse an incoming date string into a Python datetime object.

    Args:
        date_string (str): A date string in formats like 'YYYY-MM-DD' or ISO 8601.

    Returns:
        datetime: A Python datetime object.
    """
    # Try parsing common date formats
    formats = [
        "%Y-%m-%d",          # Year-Month-Day
        "%Y-%m-%dT%H:%M:%S", # ISO 8601 without timezone
        "%Y-%m-%dT%H:%M:%S.%fZ", # ISO 8601 with fractional seconds and Zulu timezone
        "%Y-%m-%dT%H:%M:%S%z"    # ISO 8601 with timezone
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue

    raise ValueError(f"Unrecognized date format: {date_string}")

def firestore_add_doc(data):
    print('DEBUG Firestore document creation script triggered')

    # Load credentials from dictionary
    cred = credentials.Certificate(cred_dict)

    # Firestore collection name (must exist)
    FIRESTORE_COLLECTION = "firestore_collection_one"

    try:
        # Check if Firebase is already initialized
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred, {
                })

        else:
            print("Firebase already initialized.")
        
        # Get Firestore client
        db = firestore.client()

        data = {
            "date": firestore.SERVER_TIMESTAMP,
            "chatlog": data
        }

        # Add document to Firestore
        collection_ref = db.collection(FIRESTORE_COLLECTION)
        doc_ref = collection_ref.add(data)
        print(f"Document added with ID: {doc_ref[1].id}")

    except Exception as e:
        print(f"Error adding document to Firestore: {e}")




def parse_date(date_string):
    """Convert a date string like 'YYYY-MM-DD' into a Python datetime object."""
    formats = [
        "%Y-%m-%d",          # Year-Month-Day
        "%Y-%m-%dT%H:%M:%S", # ISO 8601 without timezone
        "%Y-%m-%dT%H:%M:%S.%fZ", # ISO 8601 with fractional seconds and Zulu timezone
        "%Y-%m-%dT%H:%M:%SZ",    # ISO 8601 with Zulu timezone
        "%Y-%m-%dT%H:%M:%S%z"    # ISO 8601 with timezone
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue

    raise ValueError(f"Unrecognized date format: {date_string}")
    return datetime.strptime(date_str, "%Y-%m-%d")

def firestore_get_docs_by_date_range(start_date_str=None, end_date_str=None):
    """
    Retrieve documents from the Firestore collection within a date range, 
    optionally filtered by state. If no filters are provided, defaults to 
    the 5 most recent documents.
    """

    FIRESTORE_COLLECTION = "firestore_collection_one"

    try:
        # Parse incoming date strings into Python datetime objects
        print(f"DEBUG: firestore dates passed: start_date_str={start_date_str}, end_date_str={end_date_str}, state={state}")

        # Check if Firebase is initialized
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)

        # Get Firestore client
        db = firestore.client()

    except Exception as e:
        print(f"Error initializing Firestore client: {e}")
        return []

    # Start with the base query (no execution yet)
    query = db.collection(FIRESTORE_COLLECTION)

    # Build a list of filters (field, operator, value)
    filters = []
    if start_date_str:
        start_date = parse_date(start_date_str)
        filters.append(("date", ">=", start_date))
        print("Debug: start_date_str passed", start_date)

    if end_date_str:
        end_date = parse_date(end_date_str)
        filters.append(("date", "<=", end_date))
        print("Debug: end_date passed", end_date)

    # If we have filters, chain them all
    for field, op, value in filters:
        query = query.where(field, op, value)
        print(f"Adding filter: .where('{field}', '{op}', {value})")

    # If no filters at all, do default ordering and limit
    if not filters:
        query = query.order_by("date", direction=firestore.Query.DESCENDING).limit(5)
        print(".order_by('date', direction=firestore.Query.DESCENDING).limit(5)")

    # Now, final single execution
    try:
        print("Final query ready for execution.")
        docs = query.stream()
        results = [doc.to_dict() for doc in docs]
        print(f"Total number of documents returned: {len(results)}")
        #return results
    except Exception as e:
        print(f"Error executing query in Firestore: {e}")
        return []


   

        

def upload_csv_to_firestore(csv_file_path):
    """Uploads data from a CSV file to a Firestore collection.

    Args:
        csv_file_path (str): The path to the CSV file.
        collection_name (str): The name of the Firestore collection.
    """

    # Initialize Firebase if not already initialized
    if not firebase_admin._apps:
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)

        # Get Firestore client
        db = firestore.client()

        # Perform a range query on the 'date' field
        FIRESTORE_COLLECTION = 'uploadedchats'
        collection_ref = db.collection(FIRESTORE_COLLECTION)


    # Open the CSV file
    with open(csv_file_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)

        # Get the header row for column names
        column_names = reader.fieldnames

        # Iterate through each row in the CSV
        for row in reader:
            # Create a document with the data from the row
            doc_data = {column_name: row[column_name] for column_name in column_names}

            # Check if the 'date' column exists and replace it with a server timestamp
            if 'date' in doc_data:
                doc_data['date'] = firestore.SERVER_TIMESTAMP

            # Add the document to the Firestore collection
            db.collection(collection_name).add(doc_data)

    print(f"CSV data uploaded to Firestore collection '{collection_name}'")

if __name__ == "__main__":
    # Replace with your actual CSV file path and collection name
    #csv_file_path = '/workspaces/chevdev/misc/chefdatabase - chatlog (2).csv'
    #collection_name = 'your_collection_name'
    #upload_csv_to_firestore(csv_file_path)

    data = {
        "date": current_time,
        "chatlog": "This is a test chat zxcv"
    }
    firestore_add_doc(data)