## Migration Live Log: dev -> main (temporary handoff)

- Started: 2026-02-23
- Source branch: `dev`
- Target branch: `main`
- Scope: UI/streaming updates, Cloud Run deploy continuity, user-facing bot path

### Timeline

- 2026-02-23T18:46Z
  - Merge commit pushed to `main`: `8c6ceb3` (Merge branch dev into main).
  - GitHub Actions run `22320039526` failed at deploy.
  - Cloud Run revision `chef-bot-00067-fuz` failed with `HealthCheckContainerError` (container did not listen on `PORT=8080` in time).

- 2026-02-23T18:50Z
  - Hotfix commit pushed to `main`: `52cfeab` (`chefmain: do not fail Cloud Run when optional perplexity clone is unavailable`).
  - GitHub Actions run `22320154950` failed with `ContainerImageImportFailed`.
  - Cloud Run revision `chef-bot-00068-zoc` initially failed/import issue.

- 2026-02-23T19:11Z
  - Redeploy trigger commit pushed to `main`: `518cba5` (`chore: trigger redeploy after cloud run import failure`).
  - GitHub Actions run `22320902022` succeeded.
  - Run URL: `https://github.com/travelmail26/chevdev/actions/runs/22320902022`

- 2026-02-23T19:14Z
  - Cloud Run service `chef-bot` (project `cheftest-f174c`, region `us-central1`) now serving:
    - latest created/ready revision: `chef-bot-00069-quq`
    - traffic: `100%` on `chef-bot-00069-quq`
  - Previous failed revisions are not serving traffic.

### Current State

- `origin/main` head: `518cba5`
- Migration deployment path recovered and currently healthy at rollout level (revision ready + traffic shifted).

### Post-redeploy Validation (new)

- 2026-02-23T19:22Z
  - Direct Cloud Run webhook smoke run executed against live service URL (`chef-bot-00069-quq`):
    - `/general`
    - `/restart`
    - search prompt with marker `saffron-main-rev69-1771874563`
    - `/stop`
    - follow-up recall (`what marker did i ask for?`)
  - All webhook calls returned `200`.
  - Mongo evidence confirms persistence and recall in active general session:
    - marker found in assistant content tail
    - follow-up assistant response correctly echoed marker
  - Cloud Run logs show relevant runtime markers for this flow (including `xai_tool_round start`, restart handling, and stream start).
  - Evidence artifacts:
    - `/workspaces/chevdev/chef/testscripts/output/cloud_run_main_bot_verify_20260223/evidence.json`
    - `/workspaces/chevdev/chef/testscripts/output/cloud_run_main_bot_verify_20260223/summary.txt`

- 2026-02-23T19:28Z
  - Re-verified right-bot Cloud Run path with explicit token mapping evidence:
    - `TELEGRAM_KEY -> cheftest22bot` (user-facing bot)
    - `TELEGRAM_DEV_KEY -> cheftestdevbot`
  - Executed webhook smoke against live `chef-bot` revision `chef-bot-00069-quq` with marker `saffron-rightbot-1771874851`:
    - `/general`, `/restart`, long search, `/stop`, marker recall
    - all statuses `200`
    - marker persisted in Mongo tail
    - Cloud Run logs include stream/restart/tool markers and bot response entries for `cheftest22bot`
  - Evidence artifacts:
    - `/workspaces/chevdev/chef/testscripts/output/cloud_run_main_bot_verify_20260223b/evidence.json`
    - `/workspaces/chevdev/chef/testscripts/output/cloud_run_main_bot_verify_20260223b/summary.txt`
    - `/workspaces/chevdev/chef/testscripts/output/cloud_run_main_bot_verify_20260223b/cloud_run_logs_tail.txt`

- 2026-02-23T19:30Z
  - UI stop-button verification executed on local Perplexity clone UI path (`thread` page):
    - sent message, observed stop button become visible during streaming
    - clicked stop and confirmed button transitioned to hidden
    - no UI error state shown
  - Evidence artifacts:
    - `/workspaces/chevdev/chef/testscripts/output/ui_stream_stop_verify_20260223/evidence.json`
    - `/workspaces/chevdev/chef/testscripts/output/ui_stream_stop_verify_20260223/summary.txt`
    - `/workspaces/chevdev/chef/testscripts/output/ui_stream_stop_verify_20260223/01_before_stop.png`
    - `/workspaces/chevdev/chef/testscripts/output/ui_stream_stop_verify_20260223/02_after_stop.png`

### Required Follow-up Verification (do before closing migration)

- Real user-facing Telegram bot conversation run (not dev-gated bot).
- Web UI turn-by-turn test with streaming and stop behavior (`/stop`).
- `/restart` behavior verification.
- Confirm conversation persistence in MongoDB (direct evidence: ids/count/query).
- Confirm Perplexity function/tool calls still execute in the user-facing flow.

### Handoff Note

- If session is interrupted, resume from this file first, then verify GitHub run history + Cloud Run revision state before new pushes.
