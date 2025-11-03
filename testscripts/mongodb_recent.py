#!/usr/bin/env python3

from pymongo import MongoClient

# Connect to MongoDB (assuming local instance)
client = MongoClient('mongodb://localhost:27017/')

# Specify your database and collection
db = client['your_database_name']  # Replace with your actual database name
collection = db['your_collection_name']  # Replace with your actual collection name

# Find the two most recent documents (sorted by _id descending, as _id contains timestamp)
recent_docs = collection.find().sort('_id', -1).limit(2)

print("Two most recent documents:")
for doc in recent_docs:
    print(doc)