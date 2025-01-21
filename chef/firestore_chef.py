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



def firestore_get_docs_by_date_range(start_date_str=None, end_date_str=None):
    """
    Retrieve all documents from a Firestore collection where the 'date' field is within the specified range.

    Args:
        start_date_str (str): Start date as a string in various formats (e.g., 'YYYY-MM-DD').
        end_date_str (str): End date as a string in various formats (e.g., 'YYYY-MM-DD').

    Returns:
        list: A list of documents matching the query.
    """
    print('DEBUG: Firestore date range query triggered')

    # Firestore collection name
    FIRESTORE_COLLECTION = "firestore_collection_one"

    try:
        # Parse incoming date strings into Python datetime objects
        print(f"DEBUG: firestore dates passed from parameters: start_date_str: {start_date_str}, end_date_str: {end_date_str}")
       

        # Check if Firebase is initialized
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)

        # Get Firestore client
        db = firestore.client()

        # Perform a range query on the 'date' field
        collection_ref = db.collection(FIRESTORE_COLLECTION)
        #query = collection_ref.where('date', '>=', start_date).where('date', '<=', end_date)
        
        # Initialize a list to store the query parts
        # Start with the base query as a string
        query_base = "db.collection(FIRESTORE_COLLECTION)"

        # Initialize a list to store the query parts
        query_parts = []

        # Add conditions dynamically
        if start_date_str:
            start_date = parse_date(start_date_str)
            start_timestamp = gc_firestore.Timestamp.from_datetime(start_date)
            query_parts.append(f'.where("date", ">=", {start_timestamp})')

        if end_date_str:
            end_date = parse_date(end_date_str)
            end_timestamp = gc_firestore.Timestamp.from_datetime(end_date)
            query_parts.append(f'.where("date", "<=", {end_timestamp})')

        if not start_date_str and not end_date_str:
            query_parts.append('.order_by("date", direction=firestore.Query.DESCENDING)')
            query_parts.append('.limit(5)')

        # Combine all parts into a final query
        query = eval(query_base + "".join(query_parts))

        # # Convert to Firestore-compatible timestamp
        # start_timestamp = gc_firestore.Timestamp.from_datetime(start_date)
        # end_timestamp = gc_firestore.Timestamp.from_datetime(end_date)

        # Perform a range query on the 'date' field
    #     query = db.collection(FIRESTORE_COLLECTION).where('date', '>=', start_timestamp).where('date', '<=', end_timestamp)
    # else:
    #     # Retrieve the most recent document if no date range is provided
    #     query = db.collection(FIRESTORE_COLLECTION).order_by('date', direction=firestore.Query.DESCENDING).limit(1)

    #     query = collection_ref.where('date', '>=', start_date)
    #     print (f"DEBUG: firestore chat logs by time Query: {query}")
        results = query.stream()

        # Extract and return results
        documents = []
        for doc in results:
            doc_data = doc.to_dict()
            documents.append(doc_data)
            #print(f"Document ID: {doc.id}, Data: {doc_data}")

        return documents

    except ValueError as ve:
        print(f"Date parsing error: {ve}")
        return []
    except Exception as e:
        print(f"Error querying documents by date range: {e}")
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