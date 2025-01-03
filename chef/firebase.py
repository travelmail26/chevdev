
import firebase_admin
from firebase_admin import credentials
from firebase_admin import storage
import os
import json

def firebase_get_media_url(image_path):
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

    # Check if file exists before upload
    print(f"Path check - exists: {os.path.exists(image_path)}, absolute path: {os.path.abspath(image_path)}")

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found at: {image_path}")

    # Use the original filename for storage
    cloud_storage_filename = os.path.basename(image_path)

    # Upload the image
    blob = bucket.blob(f"telegram_photos/{cloud_storage_filename}")
    blob.upload_from_filename(image_path)

    # Make the blob publicly accessible
    blob.make_public()

    # Get the public download URL
    url = blob.public_url
    print(f"Image uploaded to: {url}")
    return url

if __name__ == "__main__":
    main()
    SHELL_IMAGE_PATH = "saved_photos/AgACAgEAAxkBAAIJmWdN6TliC6Bs_SBWl7K-aS3Oyt4tAAIUrzEbDQhxRsQ0OPsGD-V1AQADAgADeQADNgQ.jpg"
