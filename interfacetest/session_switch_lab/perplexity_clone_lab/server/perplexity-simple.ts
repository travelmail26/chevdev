type ChatRole = "user" | "assistant";

type ConversationMessage = {
  role: ChatRole;
  content: string;
};

type Source = {
  title: string;
  url: string;
  snippet: string;
};

const PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions";
const DEFAULT_MODEL = "sonar";

interface CallPerplexitySimpleParams {
  conversation: ConversationMessage[];
  requestedModel?: string;
  latestUserMessage: string;
}

interface CallPerplexitySimpleResult {
  model: string;
  content: string;
  thinking: string;
  sources: Source[];
}

function resolvePerplexityApiKey(): string {
  // Before example: only PERPLEXITY_API_KEY worked, so existing PERPLEXITY_KEY setups failed.
  // After example: either env var works, and the UI can run with current local secrets.
  const key = process.env.PERPLEXITY_KEY || process.env.PERPLEXITY_API_KEY;
  if (!key) {
    throw new Error("Perplexity API key not configured. Set PERPLEXITY_KEY or PERPLEXITY_API_KEY.");
  }
  return key;
}

function splitThinkingFromAnswer(rawContent: string): { thinking: string; answer: string } {
  if (!rawContent) {
    return { thinking: "", answer: "" };
  }

  const thinkingParts: string[] = [];
  const answer = rawContent
    .replace(/<think>([\s\S]*?)<\/think>/g, (_match, thinkPart: string) => {
      const cleaned = thinkPart.trim();
      if (cleaned) thinkingParts.push(cleaned);
      return "";
    })
    .trim();

  return {
    thinking: thinkingParts.join("\n\n"),
    answer,
  };
}

function normalizeSources(raw: any): Source[] {
  if (Array.isArray(raw?.search_results)) {
    return raw.search_results.map((source: any, index: number) => ({
      title: source?.title || `Source ${index + 1}`,
      url: source?.url || "",
      snippet: source?.snippet || "",
    }));
  }

  if (Array.isArray(raw?.citations)) {
    return raw.citations.map((url: string, index: number) => ({
      title: `Source ${index + 1}`,
      url: url || "",
      snippet: "",
    }));
  }

  return [];
}

export async function callPerplexitySimple(
  params: CallPerplexitySimpleParams,
): Promise<CallPerplexitySimpleResult> {
  const apiKey = resolvePerplexityApiKey();
  const model = params.requestedModel || DEFAULT_MODEL;
  const safeConversation = buildAlternatingConversation(
    params.conversation,
    params.latestUserMessage,
  );

  const response = await fetch(PERPLEXITY_API_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model,
      messages: safeConversation,
      stream: false,
    }),
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`Perplexity API error ${response.status}: ${errorBody}`);
  }

  const payload = await response.json();
  const rawContent = payload?.choices?.[0]?.message?.content ?? "";
  const { thinking, answer } = splitThinkingFromAnswer(rawContent);
  const sources = normalizeSources(payload);

  return {
    model,
    content: answer,
    thinking,
    sources,
  };
}

function buildAlternatingConversation(
  messages: ConversationMessage[],
  latestUserMessage: string,
): ConversationMessage[] {
  const cleaned: ConversationMessage[] = [];

  for (const msg of messages) {
    if (msg.role !== "user" && msg.role !== "assistant") {
      continue;
    }

    const content = (msg.content || "").trim();
    if (!content) {
      continue;
    }

    if (cleaned.length === 0) {
      if (msg.role !== "user") {
        continue;
      }
      cleaned.push({ role: "user", content });
      continue;
    }

    const previous = cleaned[cleaned.length - 1];
    if (previous.role === msg.role) {
      // Before example: duplicate user messages caused Perplexity 400 invalid_message.
      // After example: same-role runs are merged so role ordering always alternates.
      previous.content = `${previous.content}\n\n${content}`;
      continue;
    }

    cleaned.push({ role: msg.role, content });
  }

  let recent = cleaned.slice(-10);
  if (recent[0]?.role === "assistant") {
    recent = recent.slice(1);
  }

  const fallbackUser = latestUserMessage.trim();
  if (recent.length === 0 && fallbackUser) {
    recent = [{ role: "user", content: fallbackUser }];
  }

  if (recent.length > 0 && recent[recent.length - 1].role !== "user" && fallbackUser) {
    recent.push({ role: "user", content: fallbackUser });
  }

  return recent;
}
