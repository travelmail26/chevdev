# Migration Live Log

Use this temporary handoff file during migrations/deployments. Keep entries brief and append-only.

- 2026-02-23T20:37:58Z | branch=main(redeploy-main-20260223b) | commit=pending | service=chef-bot(us-central1) | result=patched per-turn mode persistence + /restart media backfill always-on | next=commit, deploy, and verify Cloud Run logs while user tests in Telegram
- 2026-02-23T22:21:25Z | branch=hotfix-image-latency | commit=pending | service=chef-bot(us-central1) | result=patched base instructions to re-enable media analysis; made firebase metadata write async; hardened stream status send timeout path | next=commit/push/deploy and validate image + latency logs on prod
- 2026-02-23T22:26:18Z | branch=hotfix-image-latency | commit=pending | service=chef-bot(us-central1) | result=added photo pipeline timeout/fallback in telegram_bot to prevent hangs on get_file/download timeout | next=commit/push/redeploy and verify image turn logs
- 2026-02-23T22:53:23Z | branch=hotfix-image-latency | commit=pending | service=chef-bot(us-central1) | result=patched media description pipeline: fallback to ai_description when no candidate text; continue scanning all sessions; unsilenced vision listener subprocess logs | next=commit/push/deploy and verify user_description_saved_from_ai + vision listener logs
- 2026-02-23T23:00:09Z | branch=main(hotfix-image-latency) | commit=2d4a84e | gha_run=22328384790 | service=chef-bot(us-central1) rev=chef-bot-00017-heb traffic=100 | result=deployed backfill fix and removed extra services (chefdev/chevdev) | evidence=gcloud run services list + gha run status | next=validate live telegram image/log behavior and patch general media instruction follow-through
- 2026-02-23T23:01:32Z | branch=main(hotfix-image-latency) | commit=a5e908e | gha_run=22328523313 | service=chef-bot(us-central1) | result=failed pre-deploy due Docker Hub 504 on base image metadata pull | next=push no-op/log commit to retrigger deploy
