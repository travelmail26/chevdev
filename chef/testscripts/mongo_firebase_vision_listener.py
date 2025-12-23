#!/usr/bin/env python3
"""Fetch the most recent media_metadata image and store an OpenAI vision summary."""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

from openai import OpenAI
from pymongo import MongoClient
import requests


def get_media_collection():
    """Return the MongoDB collection that stores media metadata."""
    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        raise SystemExit("Set MONGODB_URI before running this script.")

    # Before example: collection name hard-coded in multiple places.
    # After example:  collection name is read once and reused.
    db_name = os.environ.get("MONGODB_DB_NAME", "chef_chatbot")
    collection_name = os.environ.get("MONGODB_MEDIA_COLLECTION", "media_metadata")
    client = MongoClient(mongo_uri)
    return client[db_name][collection_name]


def is_image_url(url: str) -> bool:
    """Best-effort check for common image URL extensions."""
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    return path.endswith((".jpg", ".jpeg", ".png", ".webp"))


def extract_response_text(response) -> str:
    """Extract the first text block from an OpenAI Responses API payload."""
    # Before example: response printed as a raw object with no readable text.
    # After example:  response text is extracted and logged.
    if hasattr(response, "output_text") and response.output_text:
        return response.output_text.strip()

    payload = response
    if hasattr(response, "model_dump"):
        payload = response.model_dump()

    output_items = payload.get("output", []) if isinstance(payload, dict) else []
    if not output_items:
        return ""

    for item in output_items:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for content_item in content:
            if not isinstance(content_item, dict):
                continue
            if content_item.get("type") in ("output_text", "text"):
                text = str(content_item.get("text", "")).strip()
                if text:
                    return text
    return ""


def analyze_image_url(client: OpenAI, image_url: str, model: str) -> str:
    """Send a Firebase image URL through the vision model for analysis."""
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Analyze this image and summarize what you see in 2-4 sentences. "
                            "Focus on food or cooking, including ingredients, color, shape, "
                            "equipment, texture, doneness, and measurements if available."
                        ),
                    },
                    {"type": "input_image", "image_url": image_url},
                ],
            }
        ],
    }

    if hasattr(client, "responses"):
        response = client.responses.create(**payload)
        analysis = extract_response_text(response)
        if not analysis:
            if hasattr(response, "model_dump"):
                print(f"DEBUG: Empty vision response payload: {response.model_dump()}")
        return analysis

    # Before example: older SDK raises AttributeError for client.responses.
    # After example:  we post the same Responses payload via HTTP.
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Set OPENAI_API_KEY before running this script.")

    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    response_payload = response.json()
    analysis = extract_response_text(response_payload)
    if not analysis:
        print(f"DEBUG: Empty vision response payload: {response_payload}")
    return analysis


def fetch_latest_image_doc(collection):
    """Return the most recent document with a usable URL."""
    # Before example: we skipped non-extension URLs and returned None.
    # After example:  we prefer image extensions but fall back to any URL.
    fallback_doc = None
    for doc in collection.find().sort("_id", -1).limit(50):
        url = doc.get("url")
        if not url:
            continue
        if is_image_url(url):
            return doc
        if fallback_doc is None:
            fallback_doc = doc
    return fallback_doc


def analyze_latest_image(model: str) -> None:
    """Analyze the latest image URL in MongoDB and write ai_description."""
    collection = get_media_collection()
    client = OpenAI()
    overwrite = os.environ.get("VISION_OVERWRITE", "0") == "1"

    doc = fetch_latest_image_doc(collection)
    if not doc:
        logging.info("No media URLs found in media_metadata.")
        return

    url = doc.get("url")
    if not url:
        logging.info("Latest doc has no url field.")
        return

    if doc.get("ai_description") and not overwrite:
        logging.info("ai_description already set for %s; set VISION_OVERWRITE=1 to replace.", url)
        return

    # Before example: URL stored without any AI summary attached.
    # After example:  ai_description is stored on the same document.
    analysis = analyze_image_url(client, url, model)
    if not analysis:
        logging.warning("Vision returned empty text for %s; not updating ai_description.", url)
        print("AI description: [empty]")
        return

    collection.update_one(
        {"_id": doc["_id"]},
        {"$set": {"ai_description": analysis}},
    )
    logging.info("Stored ai_description for %s", url)
    print(f"AI description: {analysis}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    model = os.environ.get("VISION_MODEL", "gpt-5-nano-2025-08-07")

    # Before example: model value drifted between scripts.
    # After example:  model is centralized and defaults to gpt-5-nano-2025-08-07.
    analyze_latest_image(model=model)


if __name__ == "__main__":
    main()
