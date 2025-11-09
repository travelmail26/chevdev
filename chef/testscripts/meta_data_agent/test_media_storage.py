#!/usr/bin/env python3
"""Test script to retrieve recent photo, analyze it, and store description."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from media_metadata_agent import talk_to_agent

def main():
    print("=" * 70)
    print("Testing Media Metadata Storage")
    print("=" * 70)

    conversation = []

    # Step 1: Get the most recent photo
    print("\n[Step 1] Retrieving most recent photo from Firebase...")
    print("-" * 70)
    response1 = talk_to_agent("Get the most recent photo from Firebase", conversation)
    print(f"\nAgent Response:\n{response1}\n")
    conversation.append({"role": "user", "content": "Get the most recent photo from Firebase"})
    conversation.append({"role": "assistant", "content": response1})

    # Step 2: Analyze and store the description
    print("\n[Step 2] Analyzing the image and storing description...")
    print("-" * 70)
    response2 = talk_to_agent(
        "Analyze that image URL and save the description to the media_metadata collection",
        conversation
    )
    print(f"\nAgent Response:\n{response2}\n")
    conversation.append({"role": "user", "content": "Analyze that image URL and save the description to the media_metadata collection"})
    conversation.append({"role": "assistant", "content": response2})

    # Step 3: Verify it was stored
    print("\n[Step 3] Verifying the description was stored...")
    print("-" * 70)

    # Import mongo_media to check directly
    import mongo_media
    from pymongo import DESCENDING

    # Get the most recent entry from media_metadata
    latest = mongo_media.media_collection.find_one(sort=[("indexed_at", DESCENDING)])

    if latest:
        print("\nMost recent entry in media_metadata collection:")
        print(f"  URL: {latest.get('url')}")
        print(f"  Indexed at: {latest.get('indexed_at')}")
        print(f"  Description: {latest.get('description')}")
        print("\n✓ Description successfully stored!")
    else:
        print("\n✗ No entries found in media_metadata collection")

    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)

if __name__ == "__main__":
    main()
