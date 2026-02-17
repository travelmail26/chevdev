import type { Express } from "express";
import type { Server } from "http";
import { storage } from "./storage";
import { api } from "@shared/routes";
import { resolveCanonicalUserId, streamSharedBackend } from "./shared-backend";

const threadOwners = new Map<number, string>();

function normalizeCanonicalUserId(raw: string): string {
  const trimmed = String(raw || "").trim();
  if (trimmed.startsWith("tg_") && /^[0-9]+$/.test(trimmed.slice(3))) {
    return trimmed.slice(3);
  }
  return trimmed;
}

function resolveCanonicalUserFromRequest(req: { headers: Record<string, unknown> }): string {
  const raw = req.headers["x-canonical-user-id"];
  if (Array.isArray(raw)) {
    const first = String(raw[0] || "").trim();
    return normalizeCanonicalUserId(first || resolveCanonicalUserId());
  }
  const direct = String(raw || "").trim();
  return normalizeCanonicalUserId(direct || resolveCanonicalUserId());
}

export async function registerRoutes(
  httpServer: Server,
  app: Express,
): Promise<Server> {
  app.get(api.threads.list.path, async (req, res) => {
    const canonicalUserId = resolveCanonicalUserFromRequest(req);
    const threads = await storage.getThreads();
    const owned = threads.filter((thread) => threadOwners.get(thread.id) === canonicalUserId);
    res.json(owned);
  });

  app.post(api.threads.create.path, async (req, res) => {
    const canonicalUserId = resolveCanonicalUserFromRequest(req);
    const input = api.threads.create.input.parse(req.body);
    const thread = await storage.createThread(input.title);
    threadOwners.set(thread.id, canonicalUserId);
    res.status(201).json(thread);
  });

  app.get(api.threads.get.path, async (req, res) => {
    const canonicalUserId = resolveCanonicalUserFromRequest(req);
    const id = parseInt(req.params.id, 10);
    if (threadOwners.get(id) !== canonicalUserId) {
      return res.status(404).json({ message: "Thread not found" });
    }
    const thread = await storage.getThread(id);
    if (!thread) {
      return res.status(404).json({ message: "Thread not found" });
    }
    const messages = await storage.getThreadMessages(id);
    res.json({ ...thread, messages });
  });

  app.post(api.chat.sendMessage.path, async (req, res) => {
    try {
      const { message, threadId: inputThreadId, model: requestedModel } =
        api.chat.sendMessage.input.parse(req.body);
      const canonicalUserId = resolveCanonicalUserFromRequest(req);

      let threadId = inputThreadId;
      if (!threadId) {
        const title = message.slice(0, 50) + (message.length > 50 ? "..." : "");
        const thread = await storage.createThread(title);
        threadId = thread.id;
        threadOwners.set(threadId, canonicalUserId);
      } else if (threadOwners.get(threadId) !== canonicalUserId) {
        // Before example: stale threadId after restart returned 404 and blocked chat.
        // After example: recover by creating a fresh thread for this user.
        const title = message.slice(0, 50) + (message.length > 50 ? "..." : "");
        const thread = await storage.createThread(title);
        threadId = thread.id;
        threadOwners.set(threadId, canonicalUserId);
      }

      await storage.createMessage({
        threadId,
        role: "user",
        content: message,
        sources: [],
      });

      res.setHeader("Content-Type", "text/event-stream");
      res.setHeader("Cache-Control", "no-cache");
      res.setHeader("Connection", "keep-alive");
      res.setHeader("X-Accel-Buffering", "no");
      res.flushHeaders();

      const sendEvent = (event: string, data: unknown) => {
        res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
      };

      sendEvent("meta", { threadId });
      sendEvent("status", {
        phase: "searching",
        text: `Shared session lookup for ${canonicalUserId}...`,
      });

      sendEvent("status", {
        phase: "answering",
        text: "Writing final answer...",
      });

      const result = await streamSharedBackend(
        {
          latestUserMessage: message,
          canonicalUserId,
          botMode: "general",
        },
        {
          onContent: (delta: string) => {
            if (delta) {
              sendEvent("content", { text: delta });
            }
          },
        },
      );

      if (result.sources.length > 0) {
        sendEvent("sources", { sources: result.sources });
      }

      if (result.thinking) {
        sendEvent("status", {
          phase: "thinking",
          text: "Synthesizing research notes...",
        });
        sendEvent("thinking", { content: result.thinking });
      }

      await storage.createMessage({
        threadId,
        role: "assistant",
        content: result.content,
        sources: result.sources,
      });

      sendEvent("done", {
        threadId,
        canonicalUserId,
        botMode: result.botMode,
        sessionId: result.sessionId,
        requestedModel: requestedModel || "sonar",
      });
      res.end();
    } catch (error: any) {
      console.error("Chat route error:", error);
      if (!res.headersSent) {
        res.status(500).json({ message: error?.message || "Internal server error" });
      } else {
        res.write(`event: error\ndata: ${JSON.stringify({ message: error?.message || "Internal server error" })}\n\n`);
        res.end();
      }
    }
  });

  return httpServer;
}
