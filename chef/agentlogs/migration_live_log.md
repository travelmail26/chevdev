# Migration Live Log

Use this temporary handoff file during migrations/deployments. Keep entries brief and append-only.

- 2026-02-23T20:37:58Z | branch=main(redeploy-main-20260223b) | commit=pending | service=chef-bot(us-central1) | result=patched per-turn mode persistence + /restart media backfill always-on | next=commit, deploy, and verify Cloud Run logs while user tests in Telegram
- 2026-02-23T22:21:25Z | branch=hotfix-image-latency | commit=pending | service=chef-bot(us-central1) | result=patched base instructions to re-enable media analysis; made firebase metadata write async; hardened stream status send timeout path | next=commit/push/deploy and validate image + latency logs on prod
