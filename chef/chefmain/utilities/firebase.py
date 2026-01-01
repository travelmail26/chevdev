import os
import sys
# Before example: sys.path hard-coded to /workspaces/chevdev (Codespaces only).
# After example: sys.path points at the chef/ folder resolved from this file.
chef_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if chef_root not in sys.path:
    sys.path.insert(0, chef_root)
import firebase_admin
from firebase_admin import credentials
from firebase_admin import storage
import json
import time
import datetime
import logging
from chefmain.utilities.mongo_media import create_media_metadata
from google.cloud import storage as gcs_storage 


    

def list_available_buckets():
    """
    List all available bucket names in the Google Cloud project.
    """
    print("DEBUG: Listing available buckets...")
    
    # Create a storage client
    storage_client = gcs_storage.Client.from_service_account_info(cred_dict)

    # List all buckets
    buckets = storage_client.list_buckets()
    bucket_names = [bucket.name for bucket in buckets]
    print("Available buckets:", bucket_names)
    return bucket_names

    # List all buckets
    buckets = client.list_buckets()
    bucket_names = [bucket.name for bucket in buckets]
    print("Available buckets:", bucket_names)
    return bucket_names

def firebase_get_media_url(media_path, media_type: str = "photo"):
    print('DEBUG firebase get media url triggered')

    # Storage bucket constant
    STORAGE_BUCKET = "cheftest-f174c"

    try:
        # Check if Firebase is already initialized
        firebase_admin.get_app()
    except ValueError:
        # Initialize Firebase only if not already initialized
        my_secret = os.environ['FIREBASEJSON']
        cred_dict = json.loads(my_secret)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {
            'storageBucket': STORAGE_BUCKET
        })

    # Get bucket reference
    bucket = storage.bucket()

    # Before example: videos stored under telegram_photos -> mixed media types.
    # After example: media_type selects a folder (photo/video/audio) for clarity.
    folder_map = {
        "photo": "telegram_photos",
        "video": "telegram_videos",
        "audio": "telegram_audio",
        "voice": "telegram_audio",
    }
    storage_folder = folder_map.get(media_type, "telegram_media")

    # Check if file exists before upload
    print(f"Path check - exists: {os.path.exists(media_path)}, absolute path: {os.path.abspath(media_path)}")

    if not os.path.exists(media_path):
        raise FileNotFoundError(f"Media file not found at: {media_path}")

    # Use the original filename for storage
    cloud_storage_filename = os.path.basename(media_path)

    # Upload the image
    blob = bucket.blob(f"{storage_folder}/{cloud_storage_filename}")
    upload_start = time.time()
    blob.upload_from_filename(media_path)
    # Example before/after: no timing log -> "media_timing firebase_upload_ms=2100 file=foo.jpg bytes=12345"
    logging.info(
        "media_timing firebase_upload_ms=%d file=%s bytes=%s",
        int((time.time() - upload_start) * 1000),
        cloud_storage_filename,
        os.path.getsize(media_path) if os.path.exists(media_path) else None,
    )

    # Make the blob publicly accessible
    make_public_start = time.time()
    blob.make_public()
    # Example before/after: no timing log -> "media_timing firebase_make_public_ms=120 file=foo.jpg"
    logging.info(
        "media_timing firebase_make_public_ms=%d file=%s",
        int((time.time() - make_public_start) * 1000),
        cloud_storage_filename,
    )

    # Get the public download URL
    url = blob.public_url
    print(f"Media uploaded to: {url}")
    try:
        metadata_start = time.time()
        create_media_metadata(url=url, indexed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        # Example before/after: no timing log -> "media_timing firebase_metadata_ms=90 file=foo.jpg"
        logging.info(
            "media_timing firebase_metadata_ms=%d file=%s",
            int((time.time() - metadata_start) * 1000),
            cloud_storage_filename,
        )
        print("DEBUG: create_media_metadata succeeded")
    except Exception as e:
        print(f"DEBUG: create_media_metadata failed: {e}")
    return url

if __name__ == "__main__":
    # Initialize Firebase and list buckets at runtime
    print("DEBUG: Running the script...")
    try:
        # Attempt to initialize Firebase if not already done
        my_secret = os.environ['FIREBASEJSON']
        cred_dict = json.loads(my_secret)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    except ValueError:
        print("DEBUG: Firebase already initialized.")

    # List available buckets
    available_buckets = list_available_buckets()
    print("Available buckets during execution:", available_buckets)
