# Codespace Gemini Browser Demo

Beginner-friendly example for this exact flow:

1. Browser captures webcam on your laptop.
2. Browser streams frames to your Codespace backend over WebSocket.
3. Backend relays text + video frames to Gemini Live API.
4. You watch logs in the Codespace terminal.

## 1) Install dependencies

```bash
cd /workspaces/chevdev/codespace_gemini_browser_demo
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) Set API key (optional but recommended)

```bash
export GEMINI_API_KEY="your_key_here"
```

If you skip the key, the app still runs in local echo mode so you can test camera + websocket + terminal logs.

## 3) Run backend

```bash
. .venv/bin/activate
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

In Codespaces, open the forwarded port URL for `8000`.

## 4) Use the app

1. Click `Start Camera`.
2. Click `Connect Backend`.
3. Type a prompt and click `Send`.

## What you should see

- Browser log panel:
  - websocket status messages
  - your text prompt
  - Gemini text responses
- Codespace terminal:
  - connection/disconnection logs
  - frame counter updates
  - Gemini response text logs

## Notes

- Webcam access always happens in your laptop browser, not inside the remote Codespace VM.
- Keep `GEMINI_API_KEY` only on backend/server side.
