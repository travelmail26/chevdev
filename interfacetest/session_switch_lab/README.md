# Session Switch Lab (Throwaway)

This lab demonstrates one shared session used by:
- a Perplexity-style web UI (`perplexity_clone_lab`)
- the real Telegram dev bot (`cheftestdev`)

It is isolated and safe to delete later.

Default behavior:
- Web research uses live Perplexity API calls (`LAB_ENABLE_REAL_WEB_RESEARCH=1` by default).
- Telegram bridge uses live xAI generic replies by default (`LAB_ENABLE_REAL_TELEGRAM_GENERIC=1`).
- Both paths share one canonical session store in `runtime/session_store.json`.

## Run end-to-end validation

```bash
cd /workspaces/chevdev/interfacetest/session_switch_lab
./run_lab_validation.sh
```

## Single entrypoint (what you asked for)

Run one file:

```bash
cd /workspaces/chevdev/interfacetest/session_switch_lab
python main.py
```

Then cycle interfaces in one session:
- Open `cheftestdev` in Telegram and send `/start`.
- Tap the `/web` link the bot sends (it includes your user-specific `uid`).
- Ask a research question in web UI.
- Go back to Telegram and ask for recap or generic follow-ups.
- Return to web and continue from Telegram context.

Default ports in `main.py` are now:
- Web UI: `9001` (Codespaces URL like `...-9001.app.github.dev`)
- Backend API: `9002`

## Outputs

- Backend logs: `runtime/logs/backend.log`
- Web logs: `runtime/logs/web.log`
- Screenshots: `runtime/screenshots/`
- Shared session store: `runtime/session_store.json`

## Manual quick test

Use the single entrypoint only:
```bash
python main.py
```

By default, `main.py` clears shared-session memory on startup for a fresh run.
If you want to keep memory:
```bash
python main.py --keep-memory
```

## Optional toggles

- Force deterministic web replies:
```bash
LAB_ENABLE_REAL_WEB_RESEARCH=0 ./run_lab_validation.sh
```

- Use live xAI generic replies for telegram adapter:
```bash
python main.py
```

- Disable live Telegram model and use simple fallback:
```bash
python main.py --no-real-telegram
```
