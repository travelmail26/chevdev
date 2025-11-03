# Repository Guidelines

## Agent Defaults
- Default working directory: `chef/chefmain/` unless otherwise specified.
- Scope focus: prioritize `main.py`, `telegram_bot.py`, `message_router.py` and only necessary items under `chef/utilities/`.
- Exceptions: when edits/reads are needed outside `chef/chefmain/`, call it out explicitly first.
- Token minimization: avoid repo‑wide scans; prefer targeted reads within `chef/chefmain/` by default.
- Override: the user can set a different working directory per request.
- Don't change the model in the scripts from gpt-5-2025-08-07 to 4o. this is the latest and real model 

## Project Structure & Module Organization
- `chef/chefmain/`: Telegram bot entrypoint (`main.py`) and runtime code (`telegram_bot.py`, `message_router.py`).
- `chef/utilities/`: Shared helpers (Firebase upload, Sheets, history logging, OpenAI glue).
- `chef/testscripts/`: Test scripts and scenario-based tests (`test_*.py`).
- Generated assets: `chat_history_logs/`, `saved_audio/`, `saved_photos/`, `saved_videos/`.
- Node/TS (optional): `package.json`, `tsconfig.json` target `chef/mcp/**/*` → compiled to `dist/`.

## Build, Test, and Development Commands
- Python deps (uv): `uv sync` in repo root (uses `pyproject.toml`).
- Python deps (pip): `pip install -r chef/chefmain/requirements.txt`.
- Run bot (dev): `ENVIRONMENT=development TELEGRAM_DEV_KEY=... python chef/chefmain/main.py`.
- Run bot (prod webhook): `ENVIRONMENT=production TELEGRAM_KEY=... FIREBASEJSON='{"..."}' python chef/chefmain/main.py`.
- Tests (quick): `pytest chef/testscripts -q` or `python -m pytest chef/testscripts -q`.
- TypeScript (if used): `npm run build` then `npm start` (runs `dist/mcp/gemini-server.js`).

## Transparency with user
- ALWAYS: use print tails or other methods to show the user what you are working on while you are working. You are run in a CLI terminal in a github codespace. You must constantly show the user what you are thinking or coding as you working.

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indent, `snake_case` for functions/vars, `CamelCase` for classes, module names lowercase.
- TypeScript: 2-space indent, `camelCase` for vars/functions, `PascalCase` for classes.
- Logging: prefer `logging` over `print`; use structured, single-line messages.
- Files: keep bot code in `chef/chefmain/`, shared code in `chef/utilities/`, tests in `chef/testscripts/`.

## User preferences for code

- CRITICAL: keep code simple and readable. It is better to create multiple functions that use simple code that something more complex, even if its efficient.
 - NEVER NEVER change major code structure or approach without approval. The user must know exactly how the code works and changing major strategies or variables confuses the user. Do not do without approval. 

- Add inline comments that show concrete before/after examples so the user can follow each step easily.

## Testing Guidelines
- Framework: pytest. Name files `test_*.py`; keep unit helpers near the code or under `testscripts`.
- Run all: `pytest -q`. Target critical paths in `telegram_bot.py`, `message_router.py`, and utilities.
- Add reproducible fixtures for env-dependent code; mock Telegram/Firebase/OpenAI I/O.

## Commit & Pull Request Guidelines
- Commits: imperative mood with scope prefix. Example: `chefmain: route audio to Firebase`.
- Reference issues: `fixes #123` when applicable. Keep changes focused and small.
- PRs: include summary, rationale, test plan (`pytest` output), and any relevant screenshots/log excerpts.

## Security & Configuration
- Required env vars: `TELEGRAM_DEV_KEY` or `TELEGRAM_KEY`, `FIREBASEJSON` (service account JSON string), optional `ENVIRONMENT`.
- Mongo history sync uses `MONGODB_URI` secret; optional overrides `MONGODB_DB_NAME`, `MONGODB_COLLECTION_NAME`, and `MONGODB_TLS_INSECURE` (set to `1` only for local testing).
- Do not commit secrets. Use `.env` locally; keep `chef/.env.production` out of VCS.
- Be cautious with webhook URLs and public file uploads; rotate tokens on leaks.

## Logging

--You will ALWAYS keep notes on what you have changed, as though you were keeping notes for yourself that you can reference later. Keep very brief notes on code has been changes, including any mistakes or feedback you get from the user. If the session closes, the user can tell you to reference this and you can immediately begin where you left off as though you knew everything to start exactly from where you were working. The user will give you the file to take notes from.  
--Append major updates (especially credential or storage changes) to `agentlogs/agentlog010125` right after performing them so the history stays current.
