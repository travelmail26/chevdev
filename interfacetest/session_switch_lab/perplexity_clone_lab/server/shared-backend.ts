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

export { resolveCanonicalUserId };
