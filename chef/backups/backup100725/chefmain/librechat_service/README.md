# LibreChat Adapter

A self-contained Flask service that presents the existing Chef backend as
an OpenAI-compatible API so LibreChat (or any OpenAI UI) can call your
tools without Telegram.

## Endpoints
- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions` (non-streaming)

## Setup
1. Install the base Chef requirements, then the adapter extras:
   ```bash
   pip install -r chef/chefmain/requirements.txt
   pip install -r chef/chefmain/librechat_service/requirements.txt
   ```
2. Export environment variables:
   - `OPENAI_API_KEY` – same key used by the Telegram bot.
   - `MONGODB_URI` – Atlas URI (optional but recommended for transcript storage).
   - `MONGODB_DATABASE` – overrides the default `Cluster0` database name.
   - `CHEF_MODEL_NAME` – optional model label shown in LibreChat (defaults to `chef-gpt-router`).
   - `FIREBASEJSON` – reuse existing credentials to mirror transcripts to Firestore (optional).
3. Run the service:
   ```bash
   python -m chef.chefmain.librechat_service.app
   ```
4. In `librechat.yaml`, add a custom endpoint pointing to `http://<host>:8080/v1` and select the `chef-gpt-router` model.

## Notes
- Streaming (`"stream": true`) is not yet supported.
- The adapter reuses `MessageRouter`, so all current tool logic, logging,
and Firestore behaviour remain unchanged.
- Mongo persistence is optional; if `MONGODB_URI` is missing the adapter simply skips storage.
