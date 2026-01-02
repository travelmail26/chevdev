# replit.md

## Overview

This is a culinary assistant chatbot system that operates through Telegram. Users can interact with the bot to get recipe suggestions, cooking guidance, and meal planning help. The system uses AI (OpenAI/GPT models) to understand user requests and route them to appropriate tools like recipe search (via Perplexity API) or advanced recipe reasoning.

The bot supports:
- Text conversations about cooking and recipes
- Photo and video uploads with Firebase storage
- Conversation history persistence in MongoDB
- Multi-turn recipe experimentation workflows

## User Preferences

Preferred communication style: Simple, everyday language.

Additional preferences:
- Keep code simple and readable - prefer multiple simple functions over complex efficient ones
- Never change major code structure or approach without explicit approval
- Add inline comments with before/after examples so changes are easy to follow
- Do not use `gpt-5-nano-2025-08-07` model - always use `gpt-5-2025-08-07`
- Remove unnecessary debug statements and avoid verbose output
- No emojis in code or debug output
- Always show progress in terminal while working (print statements, etc.)

## System Architecture

### Directory Structure
- `chef/chefmain/` - Main bot runtime code (entrypoint is `main.py`)
- `chef/utilities/` - Shared helper modules (Firebase, history, OpenAI utilities)
- `chef/testscripts/` - Test scripts and development tools
- `chef/analysisfolder/` - MongoDB embedding and search utilities
- `chat_history_logs/` - Local JSON files for conversation persistence
- `mongo_exports/` - Downloaded MongoDB data exports

### Core Components

**Telegram Bot** (`chef/chefmain/telegram_bot.py`)
- Handles webhook and polling modes for receiving Telegram messages
- Routes incoming messages to the MessageRouter
- Manages photo/video uploads to Firebase

**Message Router** (`chef/chefmain/message_router.py`)
- Central routing logic for all user messages
- Uses OpenAI function calling to select appropriate tools
- Tools include: `search_perplexity`, `advanced_recipe_reasoning`, `answer_general_question`
- Streams responses back to users in chunks

**History Management** (`chef/utilities/history_messages.py`)
- Persists conversation history to JSON files and MongoDB
- Creates unique session IDs per user conversation
- Loads history for context in multi-turn conversations

### Key Design Decisions

1. **AI-driven tool selection** - The OpenAI model naturally chooses which tool to use based on user intent. No forced heuristics that override the model's decisions.

2. **Streaming responses** - Bot streams responses in ~300 character chunks for better user experience rather than waiting for complete responses.

3. **Dual storage** - Conversations saved both locally (JSON) and to MongoDB for redundancy and different query patterns.

4. **Webhook mode for production** - Uses Flask webhook handler for production (Cloud Run), polling mode for local development.

## External Dependencies

### APIs
- **OpenAI API** - Primary AI model (`gpt-5-2025-08-07`) for conversation and function calling
- **Telegram Bot API** - Message handling via `python-telegram-bot` library
- **Perplexity API** - Web search for recipe information (`sonar-pro` model)
- **xAI/Grok API** - Alternative AI provider (optional, configured via `XAI_API_KEY`)

### Databases
- **MongoDB** - Stores conversation sessions and media metadata
  - Database: `chef_chatbot` (configurable via `MONGODB_DB_NAME`)
  - Collections: `chat_sessions`, `media_metadata`
  - Connection: `MONGODB_URI` environment variable

### Storage
- **Firebase Storage** - Stores user-uploaded photos and videos
  - Bucket: `cheftest-f174c`
  - Credentials via `FIREBASEJSON` environment variable

### Environment Variables Required
- `OPENAI_API_KEY` - OpenAI API access
- `TELEGRAM_KEY` / `TELEGRAM_DEV_KEY` - Telegram bot tokens
- `PERPLEXITY_KEY` - Perplexity search API
- `MONGODB_URI` - MongoDB connection string
- `FIREBASEJSON` - Firebase service account JSON
- `XAI_API_KEY` - xAI/Grok API (optional)
- `ENVIRONMENT` - Set to `development` or `production`

### Python Dependencies
Key packages from `chef/chefmain/requirements.txt`:
- `python-telegram-bot[webhooks]` - Telegram integration
- `openai` - OpenAI SDK
- `pymongo[srv]` - MongoDB driver
- `firebase-admin` - Firebase SDK
- `flask` - Webhook server
- `requests` - HTTP client