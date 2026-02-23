# General Edit Streaming Rollback Notes

This change adds an interfacetest-style single-message edit stream for `general` mode.

## Fast disable (no code changes)
- Set env var: `GENERAL_EDIT_STREAMING=0`
- Result:
  - `/stop` command still exists, but general responses go back to normal one-shot message sending.
  - `Application.concurrent_updates(8)` is not enabled by this feature path.

## Code sections to remove (easy undo)
The feature is isolated with markers:
- `chef/chefmain/telegram_bot.py`
  - `# === INTERFACETEST-STYLE STREAMING BLOCK START (easy to undo) ===`
  - `# === INTERFACETEST-STYLE STREAMING BLOCK END ===`
- `chef/chefmain/message_router.py`
  - `# === INTERFACETEST-STYLE STREAMING BLOCK START (easy to undo) ===`
  - `# === INTERFACETEST-STYLE STREAMING BLOCK END ===`

## What this feature does
- In `general` mode, bot sends one placeholder message and continually edits that same message.
- `/stop` sets a stop flag checked at safe checkpoints.
- Perplexity tool streaming can update the same edited message through callback updates.

## Safety scope
- Streaming path is only used when both are true:
  - `GENERAL_EDIT_STREAMING` is enabled.
  - `bot_mode == "general"`.
- Non-general modes keep existing one-shot behavior.
