#!/usr/bin/env python3
"""
Test script to collect the latest storage items from the Telegram folder
in Firebase/GCS and check for metadata.
"""

import firebase_admin
from firebase_admin import credentials
from google.cloud import storage
import os
import json

def main():
    # Bucket name from URLs
    bucket_name = 'cheftest-f174c'
    prefix = 'telegram_photos/'

    # Initialize Firebase if not already done (from firebase.py)
    try:
        firebase_admin.get_app()
    except ValueError:
        my_secret = os.environ['FIREBASEJSON']
        cred_dict = json.loads(my_secret)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {
            'storageBucket': bucket_name
        })

    # Use GCS client with the same creds
    client = storage.Client.from_service_account_info(cred_dict)
    bucket = client.get_bucket(bucket_name)
    blobs = list(bucket.list_blobs(prefix=prefix))
    if not blobs:
        print("No blobs found in telegram_photos/")
        return

    # Sort by updated time descending
    blobs.sort(key=lambda b: b.updated, reverse=False)

    # Take latest 10
    oldest_blobs = blobs[:10]

    print(f"Found {len(oldest_blobs)} oldest blobs:")
    for blob in oldest_blobs:
        metadata = blob.metadata or {}
        has_metadata = bool(metadata)
        print(f"- {blob.name}: Updated {blob.updated}, Size {blob.size}, Has metadata: {has_metadata}")
        if has_metadata:
            print(f"  Metadata: {metadata}")

    # Add test metadata to the oldest blob (last in the list, since sorted descending by updated)
    if oldest_blobs:
        oldest_blob = oldest_blobs[0]
        print(f"Adding test metadata to oldest blob: {oldest_blob.name}")
        oldest_blob.metadata = {'test_caption': 'This is a test caption for the oldest image'}
        oldest_blob.patch()
        print("Metadata added successfully. Please check in Firebase console or re-run the script to verify.")

if __name__ == "__main__":
    main()
