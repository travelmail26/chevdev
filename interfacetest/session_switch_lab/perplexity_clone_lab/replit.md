# Replit Agent Guide

## Overview

This is an AI-powered search/chat application inspired by Perplexity AI. It allows users to ask questions, get AI-generated answers with cited sources, and organize conversations into threads. The app features a clean, warm off-white design with a sidebar for thread navigation and a streaming chat interface that shows search progress, thinking process, and markdown-formatted responses.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Framework**: React 18 with TypeScript, bundled by Vite
- **Routing**: Wouter (lightweight client-side router) with two main routes: Home (`/`) and Thread (`/thread/:id`)
- **State Management**: TanStack React Query for server state (threads, messages), local React state for UI
- **UI Components**: shadcn/ui (new-york style) built on Radix UI primitives with Tailwind CSS
- **Sidebar**: Uses shadcn sidebar primitives (SidebarProvider, Sidebar, SidebarContent, SidebarMenu, etc.) in `client/src/components/app-sidebar.tsx`. SidebarProvider wraps the app in App.tsx with automatic mobile Sheet behavior.
- **Styling**: Tailwind CSS with CSS variables for theming, using a warm off-white Perplexity-inspired color scheme. Fonts: Inter (sans) and Merriweather (serif). Mobile-first with 100dvh viewport, safe-area insets, and touch-friendly targets.
- **Chat Streaming**: Custom `useChatStream` hook that reads server-sent events from `/api/chat` endpoint, tracking phases (searching → thinking → answering → done)
- **Voice Input**: Web Speech API integration in ChatInput with visual listening indicator
- **Model Selection**: User can choose Perplexity model (sonar, sonar-pro, sonar-reasoning, sonar-reasoning-pro) via dropdown in ChatInput, persisted in localStorage
- **Markdown Rendering**: react-markdown with remark-gfm for rendering AI responses
- **Path Aliases**: `@/` maps to `client/src/`, `@shared/` maps to `shared/`, `@assets/` maps to `attached_assets/`

### Backend Architecture
- **Runtime**: Node.js with Express 5
- **Language**: TypeScript, executed via tsx in development
- **API Design**: RESTful JSON API under `/api/` prefix with typed route definitions in `shared/routes.ts`
- **Key Endpoints**:
  - `GET /api/threads` — List all threads
  - `POST /api/threads` — Create a new thread
  - `GET /api/threads/:id` — Get thread with messages
  - `POST /api/chat` — Send a message and receive a streaming AI response
- **AI Integration**: Perplexity AI API (`https://api.perplexity.ai/chat/completions`) for generating responses with source citations
- **Development**: Vite dev server is integrated as middleware with HMR support
- **Production**: Client is built to `dist/public`, server is bundled with esbuild to `dist/index.cjs`

### Data Storage
- **Database**: PostgreSQL via `DATABASE_URL` environment variable
- **ORM**: Drizzle ORM with drizzle-zod for schema validation
- **Schema** (in `shared/schema.ts`):
  - `threads` table: `id` (serial PK), `title` (text), `createdAt` (timestamp)
  - `messages` table: `id` (serial PK), `threadId` (integer FK), `role` (text: 'user'|'assistant'), `content` (text), `sources` (jsonb), `createdAt` (timestamp)
- **Relations**: One thread has many messages
- **Migrations**: Use `drizzle-kit push` (`npm run db:push`) to sync schema to database
- **Storage Layer**: `server/storage.ts` implements a `DatabaseStorage` class with an `IStorage` interface for all DB operations

### Shared Code
- `shared/schema.ts` — Database schema, types, and Zod validation schemas shared between client and server
- `shared/routes.ts` — API route definitions with paths, methods, input/output Zod schemas. Used by both frontend hooks and backend route handlers for type safety

### Build System
- **Development**: `npm run dev` — runs tsx with Vite middleware for HMR
- **Production Build**: `npm run build` — builds client with Vite, then bundles server with esbuild
- **Type Checking**: `npm run check` — runs tsc with no emit
- **Database**: `npm run db:push` — pushes Drizzle schema to PostgreSQL

## External Dependencies

- **PostgreSQL**: Primary database, connected via `DATABASE_URL` environment variable, using `pg` (node-postgres) driver with connection pooling
- **Perplexity AI API**: Used for AI chat completions with source citations. Requires `PERPLEXITY_API_KEY` environment variable. Endpoint: `https://api.perplexity.ai/chat/completions`
- **Google Fonts**: Inter and Merriweather fonts loaded via CDN in `client/index.html`
- **Replit Plugins**: `@replit/vite-plugin-runtime-error-modal`, `@replit/vite-plugin-cartographer`, and `@replit/vite-plugin-dev-banner` for development on Replit