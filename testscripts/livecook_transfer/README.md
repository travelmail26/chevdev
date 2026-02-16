# LiveCook Recorder (Firebase + Mongo Metadata)

Browser recorder that keeps local clip downloads, transcodes finalized clips to MP4, uploads to Firebase Storage, then writes clip metadata (including Firebase URL + transcript) to MongoDB.

## What changed

- Low-res rolling clips still appear in **Saved clips**.
- High-res wake clips still appear in **Saved clips**.
- Both clip types are posted to `POST /api/clips`.
- Server transcodes each clip to MP4 and uploads to Firebase Storage.
- Server writes clip metadata into MongoDB collection `livecook`.
- Server requests transcript text from OpenAI audio transcription (`gpt-4o-mini-transcribe` by default).

## Run

```bash
cd /workspaces/chevdev/testscripts/livecook
npm install
MONGODB_URI='mongodb+srv://<user>:<pass>@<cluster>/' MONGODB_DB_NAME='chef' npm start
```

Open: `http://127.0.0.1:4173`

## Mongo target

- Database: `MONGODB_DB_NAME` (default: `chef`)
- Collection: `livecook` (fixed in server code)

## Stored document shape

Each uploaded clip is inserted with fields like:

- `sessionId`
- `clipName`
- `clipType` (`low-res` or `high-res`)
- `reason`
- `mimeType`
- `mimeTypeOriginal`
- `sizeBytes`
- `sizeBytesOriginal`
- `sizeBytesEncoded`
- `capturedAt`
- `clipStartedAt`
- `clipEndedAt`
- `uploadedAt`
- `indexed_at`
- `source` (`livecook`)
- `url` (Firebase public URL)
- `firebase.bucket`
- `firebase.path`
- `transcript_full_text`
- `transcript_source`
- `transcript_model`

## Health check

```bash
curl http://127.0.0.1:4173/health
```

Expected response includes `collection: "livecook"`.
