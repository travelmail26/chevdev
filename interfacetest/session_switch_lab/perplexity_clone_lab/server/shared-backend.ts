interface Source {
  title: string;
  url: string;
  snippet: string;
}

interface CallSharedBackendParams {
  latestUserMessage: string;
  canonicalUserId: string;
  botMode?: string;
}

interface CallSharedBackendResult {
  content: string;
  thinking: string;
  sources: Source[];
  sessionId: string;
  botMode: string;
}

interface StreamHandlers {
  onContent?: (delta: string) => void;
}

function resolveSharedBackendUrl(): string {
  return process.env.LAB_SHARED_BACKEND_URL || "http://127.0.0.1:9001";
}

function resolveCanonicalUserId(): string {
  return process.env.LAB_CANONICAL_USER_ID || "demo_user_1";
}

export async function callSharedBackend(
  params: CallSharedBackendParams,
): Promise<CallSharedBackendResult> {
  const backendUrl = resolveSharedBackendUrl();
  const canonicalUserId = params.canonicalUserId || resolveCanonicalUserId();

  const response = await fetch(`${backendUrl}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      canonical_user_id: canonicalUserId,
      source: "web",
      message: params.latestUserMessage,
      bot_mode: params.botMode,
    }),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Shared backend error ${response.status}: ${errText}`);
  }

  const payload = await response.json();
  return {
    content: payload?.assistant_text || "",
    thinking: payload?.thinking || "",
    sources: Array.isArray(payload?.sources) ? payload.sources : [],
    sessionId: payload?.active_session_id || "",
    botMode: payload?.bot_mode || "general",
  };
}

export async function streamSharedBackend(
  params: CallSharedBackendParams,
  handlers: StreamHandlers = {},
): Promise<CallSharedBackendResult> {
  const backendUrl = resolveSharedBackendUrl();
  const canonicalUserId = params.canonicalUserId || resolveCanonicalUserId();

  const response = await fetch(`${backendUrl}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      canonical_user_id: canonicalUserId,
      source: "web",
      message: params.latestUserMessage,
      bot_mode: params.botMode,
      stream: true,
    }),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Shared backend error ${response.status}: ${errText}`);
  }
  if (!response.body) {
    throw new Error("Shared backend stream missing body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventType = "";
  let donePayload: any = null;

  const processBlock = (block: string) => {
    const lines = block.split("\n");
    let dataStr = "";
    eventType = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        dataStr += line.slice(6);
      }
    }
    if (!dataStr) return;
    let data: any = {};
    try {
      data = JSON.parse(dataStr);
    } catch {
      return;
    }
    if (eventType === "content") {
      const delta = String(data?.text || "");
      if (delta) handlers.onContent?.(delta);
    } else if (eventType === "done") {
      donePayload = data;
    } else if (eventType === "error") {
      const message = String(data?.message || "Unknown shared backend stream error");
      throw new Error(message);
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";
    for (const block of blocks) {
      if (!block.trim()) continue;
      processBlock(block);
    }
  }

  if (buffer.trim()) {
    processBlock(buffer);
  }
  if (!donePayload) {
    throw new Error("Shared backend stream ended without done payload");
  }

  return {
    content: donePayload?.assistant_text || "",
    thinking: donePayload?.thinking || "",
    sources: Array.isArray(donePayload?.sources) ? donePayload.sources : [],
    sessionId: donePayload?.active_session_id || "",
    botMode: donePayload?.bot_mode || "general",
  };
}

export { resolveCanonicalUserId };
