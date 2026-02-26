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
- `preferences/`: LLM preference-memory examples and import-ready JSON documents (one document per preference, keyed by `user_id`).
- `insights_general/`: Example documents for short general-chat insight memory and generated preference memory.
- Generated assets: `chat_history_logs/`, `saved_audio/`, `saved_photos/`, `saved_videos/`.
- Node/TS (optional): `package.json`, `tsconfig.json` target `chef/mcp/**/*` → compiled to `dist/`.

## Preference Memory (LLM)
- Mongo collection: `preferences` (top-level collection, one preference document per record).
- Required fields: `_id`, `user_id`, `schema_version`, `type`, `key`, `created_at`, `updated_at`.
- Pairwise format is plain natural language for LLM retrieval, e.g. `pairwise: "animal based over plant based"`.
- For this format, avoid nested option lists for pairwise values; keep the statement flat and human-readable.
- Optional metadata like `constraints`, `reason`, and `example` can be blank strings when unknown.
- `strength` and `status` were intentionally removed from the preference document to keep schema minimal.
- Example file added: `preferences/user_123_example_preference.json`.

## General Memory Backfill (LLM)
- Backfill script: `chef/chefmain/utilities/mongo_general_insights_backfill.py`.
- Trigger behavior: non-blocking subprocess spawned during restart/mode-reset flow in `chef/chefmain/telegram_bot.py` (`_spawn_general_memory_backfill(limit=10)`).
- Source scan: latest unsummarized conversations across all modes by default:
  - `chef_chatbot.chat_sessions` (cheflog)
  - `chef_dietlog.chat_dietlog_sessions` (dietlog)
  - `chat_general.chat_general` (general)
- Done marker: each processed source conversation gets `insight_general_hash` so backfill does not reprocess it.
- Insight destination (default): `chat_general.insights_general`.
- Preference destination (default): `chef_chatbot.preferences`.
- Insight schema includes `principle` (boolean). `true` means an explicit user-defined principle/rule.
- Runtime loader: `chef/chefmain/utilities/insight_memory.py` supports Mongo filter loading (`principle_only=True`).
- `MessageRouter` appends filtered principle insights into system context as anchor reasoning.
- Destination overrides:
  - Insights: `MONGODB_INSIGHTS_DB_NAME`, `MONGODB_INSIGHTS_COLLECTION_NAME`
  - Preferences: `MONGODB_PREFERENCES_DB_NAME`, `MONGODB_PREFERENCES_COLLECTION_NAME`

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
- CRITICAL: instruction-first behavior changes. If behavior is wrong, first update prompt/instruction files and tool descriptions. Do not add new behavioral gating, keyword filters, or routing heuristics in Python code unless the user explicitly asks for code-level logic.
- CRITICAL: never silently replace instruction-driven behavior with hard-coded logic. If a code-level fallback is truly required, call it out first, explain why instruction-only is insufficient, and wait for approval before implementing.
- Prefer prompt/instruction-driven behavior and standard model tool-calling patterns over hard-coded trigger logic whenever feasible.
- Decision order for behavior fixes (must follow in order):
  - 1) Prompt/instruction updates
  - 2) Tool schema/description updates
  - 3) Minimal code logic only with explicit user approval
- When integrating or changing API model/tool behavior, regularly check official provider documentation for current best practices and align implementations to those standards.

## Testing Guidelines
- Framework: pytest. Name files `test_*.py`; keep unit helpers near the code or under `testscripts`.
- Run all: `pytest -q`. Target critical paths in `telegram_bot.py`, `message_router.py`, and utilities.
- Add reproducible fixtures for env-dependent code; mock Telegram/Firebase/OpenAI I/O.
- CRITICAL: final verification must use the real user interfaces (actual Telegram bot + actual web UI) for turn-by-turn flow checks, not only mocked/unit tests.
- CRITICAL: any final test must confirm the run actually saved data to MongoDB (not just logs/UI); include direct Mongo evidence (query result, inserted document id, or saved-record count).
- CRITICAL: before marking a migration/user test complete, explicitly verify all key features in the same run:
  - Web UI load + send/receive flow
  - Streaming start + stop behavior (including `/stop`)
  - Conversation upload/persistence in MongoDB
  - Bot switching behavior (dev bot vs user-facing/main bot)
  - Restart behavior (`/restart`) and session continuity/reset
  - Image processing behavior follows instructions correctly (media analysis/handling matches expected prompts)
  - Function/tool calls to Perplexity path still execute correctly

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
- CRITICAL for migrations: create and keep a separate temporary live migration log file so another agent can continue immediately if the session is interrupted.
- Migration live-log location/pattern: `agentlogs/migration_live_<YYYYMMDD>_<source>-to-<target>.md`.
- Update that migration log after each major step with: timestamp, branch/commit SHA, GitHub Actions run ID/URL, Cloud Run revision/traffic, test evidence paths, and open blockers/next step.
- Keep the migration log updated until rollout is complete and stable, then mark it completed (do not delete active logs mid-migration).

## LiveCook Transfer Bundle
- Transfer-ready LiveCook package lives in `testscripts/livecook_transfer/`.
- This folder must include all top-level files from `testscripts/livecook/` plus `LLM_HANDOFF.txt`.
- Do not include generated runtime directories in transfer bundles (`node_modules/`, `logs/`, `downloads/`).
- Refresh bundle command:
  - `cp testscripts/livecook/{README.md,app.js,e2e_livecook_playwright.mjs,index.html,onboardTranscriber.js,package-lock.json,package.json,run_livecook_tmux.sh,server.js,start_livecook_server.sh,styles.css,verify_with_screenshots.mjs} testscripts/livecook_transfer/`

# Web UI + Common Backend Map

This note is the canonical quick reference for questions about the web UI and shared backend.

## Web UI (Perplexity clone)
- Root folder: `interfacetest/session_switch_lab/perplexity_clone_lab/`
- Frontend app code: `interfacetest/session_switch_lab/perplexity_clone_lab/client/`
- Web server/API facade: `interfacetest/session_switch_lab/perplexity_clone_lab/server/`
- The web UI is the existing Perplexity clone (no separate custom UI).

## Common backend (shared with Telegram)
- Shared backend adapter: `chef/chefmain/perplexity_clone_shared_backend.py`
- It exposes:
  - `POST /api/chat`
  - `GET /api/session/<canonical_user_id>`
  - `GET /health`
- It forwards turns into `MessageRouter` and shared history utilities in `chef/chefmain/`.

## How web acts as frontend
1. Browser sends message to clone server route: `perplexity_clone_lab/server/routes.ts` (`POST /api/chat`).
2. Clone server calls shared backend via `perplexity_clone_lab/server/shared-backend.ts` (`LAB_SHARED_BACKEND_URL`).
3. Shared backend (`perplexity_clone_shared_backend.py`) calls `MessageRouter` and reads/writes shared history.
4. Result is streamed back through clone server to the browser.

## How Telegram uses same backend/session
- Telegram bot runtime: `chef/chefmain/telegram_bot.py`
- Startup/orchestration: `chef/chefmain/main.py`
- Telegram turns and web turns both land in shared history through `MessageRouter` + history utilities.

## Canonical user/session behavior
- `tg_<id>` and numeric `<id>` are normalized to the same canonical ID in:
  - `chef/chefmain/perplexity_clone_shared_backend.py`
  - `interfacetest/session_switch_lab/perplexity_clone_lab/server/routes.ts`
- This keeps Telegram and web on one shared conversation history.

## Ports when running `main.py`
- Telegram bot runtime port: `PORT` (default `8080`)
- Web UI: `PERPLEXITY_WEB_PORT` (default `9001`)
- Shared backend: `PERPLEXITY_SHARED_BACKEND_PORT` (default `9002`)
