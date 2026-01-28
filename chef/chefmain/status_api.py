import logging
import os
from datetime import datetime

from flask import Flask, jsonify, request
from pymongo import MongoClient, DESCENDING

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)

API_KEY = os.getenv("STATUS_API_KEY", "")
MONGODB_URI = os.getenv("MONGODB_URI", "")
DB_NAME = os.getenv("MONGODB_DB_NAME", "chef_chatbot")
COLLECTION_NAME = os.getenv("MONGODB_COLLECTION_NAME", "user_recipe_status")

# Before: GET /latest_status?user_id=123 with header x-api-key: mysecret
# After:  {"user_id":"123","latest_step":"chop onions","updated_at":"2026-01-28T18:42:00Z"}


def _extract_api_key(req):
    header_key = req.headers.get("x-api-key", "").strip()
    if header_key:
        return header_key

    auth_header = req.headers.get("authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    return ""


@app.get("/latest_status")
def latest_status():
    if not API_KEY:
        return jsonify({"error": "STATUS_API_KEY not set"}), 500

    if not MONGODB_URI:
        return jsonify({"error": "MONGODB_URI not set"}), 500

    provided_key = _extract_api_key(request)
    if not provided_key or provided_key != API_KEY:
        return jsonify({"error": "unauthorized"}), 401

    user_id = request.args.get("user_id", "").strip()
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    # Before: doc={"user_id":"123","latest_step":"whisk eggs","updated_at": datetime}
    # After:  response={"user_id":"123","latest_step":"whisk eggs","updated_at":"2026-01-28T18:42:00Z"}
    client = MongoClient(MONGODB_URI)
    try:
        collection = client[DB_NAME][COLLECTION_NAME]
        doc = collection.find_one({"user_id": user_id}, sort=[("updated_at", DESCENDING)])
    finally:
        client.close()

    if not doc:
        return jsonify({"user_id": user_id, "latest_step": None, "updated_at": None}), 200

    latest_step = doc.get("latest_step") or doc.get("step") or doc.get("status")
    updated_at = doc.get("updated_at") or doc.get("created_at")
    if isinstance(updated_at, datetime):
        updated_at = updated_at.isoformat()

    return jsonify({"user_id": user_id, "latest_step": latest_step, "updated_at": updated_at}), 200


if __name__ == "__main__":
    # Before: STATUS_API_KEY=mysecret MONGODB_URI=... python status_api.py
    # After:  Server runs on http://127.0.0.1:5000
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
