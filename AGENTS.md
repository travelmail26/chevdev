# Repository Guidelines

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

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indent, `snake_case` for functions/vars, `CamelCase` for classes, module names lowercase.
- TypeScript: 2-space indent, `camelCase` for vars/functions, `PascalCase` for classes.
- Logging: prefer `logging` over `print`; use structured, single-line messages.
- Files: keep bot code in `chef/chefmain/`, shared code in `chef/utilities/`, tests in `chef/testscripts/`.

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
- Do not commit secrets. Use `.env` locally; keep `chef/.env.production` out of VCS.
- Be cautious with webhook URLs and public file uploads; rotate tokens on leaks.

