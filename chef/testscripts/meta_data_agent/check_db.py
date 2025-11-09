#!/usr/bin/env python3
"""Check what's in media_metadata collection."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import mongo_media
from pymongo import DESCENDING

# Get all entries
all_entries = list(mongo_media.media_collection.find().sort("indexed_at", DESCENDING))

print(f"Total entries in media_metadata: {len(all_entries)}")
print("\nAll entries:")
for i, entry in enumerate(all_entries, 1):
    print(f"\n{i}. URL: {entry.get('url')}")
    print(f"   Indexed at: {entry.get('indexed_at')}")
    print(f"   Description: {entry.get('description')}")
