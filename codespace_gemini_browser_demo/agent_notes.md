2026-02-08
- Created isolated top-level demo folder: `codespace_gemini_browser_demo`.
- Added beginner-friendly FastAPI websocket backend in `app.py`.
- Added browser capture UI in `static/index.html` (camera capture + websocket send + chat log).
- Added `requirements.txt` and quick-start `README.md`.
- Included local echo fallback when `GEMINI_API_KEY` is missing.
- Updated setup to use local `.venv` to avoid dependency conflicts with the main workspace.
- Verified app import inside `.venv` (`app_import_ok`) and verified `uvicorn` serves `/` successfully.
- Added safe fallback when Gemini Live connection/receive fails, so websocket stays active in local echo mode.
