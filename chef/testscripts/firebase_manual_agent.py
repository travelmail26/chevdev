from openai import OpenAI
import os
import json
from pymongo import MongoClient
import gridfs
from datetime import datetime, timezone
from urllib.parse import urlparse
import firebase_admin
from firebase_admin import credentials, storage

DEFAULT_DB_NAME = "chef_chatbot"
DEFAULT_GRIDFS_COLLECTION = "chat_media"

def get_recent_images_from_firebase(limit=10, since=None):
    """
    Get recent images from Firebase Storage.

    Args:
        limit: Maximum number of images to return
        since: ISO timestamp string (e.g., "2025-10-27T12:00:00Z") - only return images uploaded after this time

    Returns:
        List of dicts with 'blob', 'url', 'uploaded', and 'metadata'
    """
    STORAGE_BUCKET = "cheftest-f174c"
    try:
        firebase_admin.get_app()
    except ValueError:
        my_secret = os.environ["FIREBASEJSON"]
        cred_dict = json.loads(my_secret)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {'storageBucket': STORAGE_BUCKET})

    bucket = storage.bucket()

    # Parse cutoff time if provided
    cutoff_time = None
    if since:
        try:
            cutoff_time = datetime.fromisoformat(since.replace('Z', '+00:00'))
        except:
            print(f"Warning: Could not parse 'since' time: {since}")

    # List all blobs in telegram_photos/
    blobs = list(bucket.list_blobs(prefix="telegram_photos/"))

    # Filter for images and apply time filter
    image_blobs = []
    for blob in blobs:
        if not blob.content_type or not blob.content_type.startswith("image/"):
            continue

        # Check time filter
        if cutoff_time:
            blob_time = blob.updated or blob.time_created
            if blob_time and blob_time < cutoff_time:
                continue

        image_blobs.append(blob)

    # Sort by most recent
    image_blobs.sort(key=lambda b: b.updated or b.time_created, reverse=True)

    # Limit results
    image_blobs = image_blobs[:limit]

    # Build results with metadata
    results = []
    for blob in image_blobs:
        blob.make_public()
        results.append({
            'blob': blob,
            'url': blob.public_url,
            'uploaded': (blob.updated or blob.time_created).isoformat(),
            'metadata': blob.metadata or {}
        })

    return results

def get_recent_images_from_mongodb(limit=10, since=None):
    """
    Get recent images from MongoDB GridFS.

    Args:
        limit: Maximum number of images to return
        since: ISO timestamp string - only return images uploaded after this time

    Returns:
        List of dicts with 'file', 'id', 'uploaded', and 'metadata'
    """
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("MONGODB_URI not set")
        return []

    client = MongoClient(uri)
    db_name = os.environ.get("MONGODB_DB_NAME", DEFAULT_DB_NAME)
    bucket_name = os.environ.get("MONGODB_GRIDFS_COLLECTION", DEFAULT_GRIDFS_COLLECTION)
    db = client[db_name]
    bucket = gridfs.GridFS(db, collection=bucket_name)

    # Build query
    query = {"metadata.media_type": "photo"}

    # Add time filter
    if since:
        try:
            cutoff = datetime.fromisoformat(since.replace('Z', '+00:00'))
            query["uploadDate"] = {"$gte": cutoff}
        except:
            print(f"Warning: Could not parse 'since' time: {since}")

    try:
        files = bucket.find(query).sort("uploadDate", -1).limit(limit)
        results = []
        for file_doc in files:
            gridfs_file = bucket.get(file_doc._id)
            results.append({
                'file': gridfs_file,
                'id': str(file_doc._id),
                'uploaded': file_doc.uploadDate.isoformat(),
                'metadata': file_doc.metadata or {}
            })
        return results
    except Exception as exc:
        print(f"Failed to get images from GridFS: {exc}")
        return []

def get_most_recent_image_url():
    """Get the single most recent image from MongoDB (for backwards compatibility)"""
    results = get_recent_images_from_mongodb(limit=1)
    if not results:
        print("No image files found in GridFS")
        return None

    result = results[0]
    # Return in old format for compatibility
    url = f"gridfs://{result['id']}"
    return result['file'], url

def get_specific_image_url(full_url):
    """Get a specific image from Firebase by URL"""
    parsed = urlparse(full_url)
    if 'telegram_photos' in parsed.path:
        blob_name = parsed.path.split('/telegram_photos/')[1]
    else:
        print("Invalid URL.")
        return None

    print(f"Getting specific image URL for {full_url}")
    STORAGE_BUCKET = "cheftest-f174c"
    try:
        firebase_admin.get_app()
    except ValueError:
        my_secret = os.environ["FIREBASEJSON"]
        cred_dict = json.loads(my_secret)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {'storageBucket': STORAGE_BUCKET})

    bucket = storage.bucket()
    blob = bucket.blob(f"telegram_photos/{blob_name}")
    if not blob.exists():
        print(f"Blob {blob_name} does not exist.")
        return None

    blob.make_public()
    url = blob.public_url
    print(f"Image URL: {url}")
    return blob, url

if __name__ == "__main__":
    choice = input("Enter 1 for most recent (mongo), 2 for specific URL (firebase), 3 for recent from firebase: ").strip()

    if choice == "1":
        result = get_most_recent_image_url()
        if not result:
            print("No image found.")
            exit(1)
        _, image_url = result
    elif choice == "2":
        full_url = input("Enter URL: ").strip()
        result = get_specific_image_url(full_url)
        if not result:
            print("Image not found.")
            exit(1)
        _, image_url = result
    elif choice == "3":
        limit = int(input("How many? ").strip() or "5")
        results = get_recent_images_from_firebase(limit=limit)
        if not results:
            print("No images found.")
            exit(1)
        print(f"Found {len(results)} images:")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['url']} (uploaded: {r['uploaded']})")
        exit(0)
    else:
        print("Invalid.")
        exit(1)

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-5-2025-08-07",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "what's in this image?"},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }],
    )
    print(response.choices[0].message.content)
