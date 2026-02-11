# interfacetest

Telegram UI demo harness for testing modern bot interaction patterns on your existing `cheftestdev` token.

## What this folder includes

- `ui_lab_bot.py`: Telegram bot with one-by-one UI demos.
- `quick_apis.py`: Fast API wrappers for:
  - quick message (`OPENAI_API_KEY` via Responses API)
  - internet search (`PERPLEXITY_KEY` via Perplexity sonar)
- `telegram_raw.py`: Raw Telegram method caller with `sendMessageDraft` probe.
- `api_smoke.py`: CLI smoke test for the quick APIs.

## Environment

Expected env vars:

- `TELEGRAM_DEV_KEY` (preferred for this dev test)
- `OPENAI_API_KEY` (for quick-message demos)
- `PERPLEXITY_KEY` (for internet-search demos)
- optional: `ENVIRONMENT=development`
- optional: `INTERFACETEST_OPENAI_MODEL` (default `gpt-5-2025-08-07`)
- optional: `INTERFACETEST_PERPLEXITY_MODEL` (default `sonar`)

## Run

From repo root:

```bash
python interfacetest/ui_lab_bot.py
```

## Try one by one in Telegram

1. `/start`
2. `/demo_quick give me a 2 sentence answer about hydration`
3. `/demo_stream explain how edit-based streaming improves UX`
4. `/demo_search latest updates to Telegram bot api`
5. `/demo_draft testing draft method`
6. `/uimenu` and tap each button

## What each demo shows

- `demo_quick`: immediate typing + placeholder + fast final answer with controls.
- `demo_stream`: edit-based streaming with throttle and `Stop/Continue`.
- `demo_search`: progress steps for web search + progressive disclosure (`Headline/Details/Sources`).
- `demo_draft`: tries `sendMessageDraft`; if unsupported, falls back to edit-streaming.

## Quick API smoke tests

```bash
python interfacetest/api_smoke.py --quick "say hi in one sentence"
python interfacetest/api_smoke.py --search "top AI safety headlines this week"
```

