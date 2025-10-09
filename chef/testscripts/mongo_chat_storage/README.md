# Mongo Chat Storage Utilities

This folder contains standalone utilities for storing Chef bot chat histories in MongoDB without modifying the production runtime. The helpers reuse existing modules under `chef/chefmain` and `chef/utilities` but live entirely in the testscripts area for experimentation.

## Setup

1. Ensure dependencies are installed:
   ```bash
   python -m pip install "pymongo[srv]" mongomock
   ```
2. Provide Mongo credentials via environment variables:
   - `MONGODB_URI` (preferred secret: e.g., `mongodb+srv://example/chef`).
   Optional overrides: `MONGODB_DB_NAME` and `MONGODB_COLLECTION_NAME`.

## Key Modules

- `config.py` – loads Mongo settings from env or the bundled credential file.
- `client.py` – cached `MongoClient` factory with ping helper.
- `schemas.py` – normalizes chat messages/sessions to the Mongo document shape.
- `repository.py` – CRUD wrapper (`MongoChatRepository`).
- `history_ingestor.py` – CLI to push existing `chat_history_logs/*_history.json` files into Mongo.
- `router_adapter.py` – sample bridge that routes messages through `MessageRouter` and persists the resulting history.
- `manual_runner.py` – CLI that replays canned conversations (e.g., the “make eggs” scenario) into Mongo and verifies the write.

## Usage Examples

### 1. Verify connectivity
```bash
python -c "from chef.testscripts.mongo_chat_storage.client import ping_database; print(ping_database())"
```

### 2. Ingest existing chat logs
```bash
python -m chef.testscripts.mongo_chat_storage.history_ingestor --verbose
```
Add `--dry-run` to preview without writing.

### 3. Replay the egg-cooking scenario
```bash
python -m chef.testscripts.mongo_chat_storage.manual_runner --scenario make_eggs
```
This stores a transcript for the demo user and re-reads it to confirm MongoDB persisted the messages.

### 4. List available scenarios
```bash
python -m chef.testscripts.mongo_chat_storage.manual_runner --scenario list
```

## Testing

Unit tests live under `tests/` in this folder and run with standard pytest:
```bash
python -m pytest chef/testscripts/mongo_chat_storage/tests -q
```
Tests rely on `mongomock` so they do not touch the live database.

## Notes

- These utilities avoid changing existing bot files; they only import and reuse the current helpers.
- Logging is minimal by default. Set `MONGODB_COLLECTION_NAME` to a custom value if you want to isolate experimental runs.
