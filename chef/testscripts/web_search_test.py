import os
from openai import OpenAI

MODEL = "gpt-5"                 # official API model id
REASONING_EFFORT = "high"       # expose more “thinking” (count only)
SEARCH_HINT = "site:arxiv.org retrieval augmented generation"  # <-- edit this
FORCE_SEARCH = True             # set False to let the model decide

def main():
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    prev_id = None

    print("GPT-5 REPL (Ctrl+C to exit)")
    print(f"(Forced web_search: {FORCE_SEARCH}; hint: {SEARCH_HINT!r})\n")

    while True:
        try:
            user_msg = input("You: ").strip()
            if not user_msg:
                continue

            # Developer nudge to use your exact search terms first.
            dev = (
                "Use the web_search tool FIRST. Include these exact terms at least once: "
                f"[{SEARCH_HINT}]. Then answer succinctly with citations."
            )

            resp = client.responses.create(
                model=MODEL,
                input=[{"role": "developer", "content": dev},
                       {"role": "user", "content": user_msg}],
                tools=[{"type": "web_search"}],
                tool_choice="required" if FORCE_SEARCH else "auto",  # force a tool call
                reasoning={"effort": REASONING_EFFORT},
                previous_response_id=prev_id,  # multi-turn state
            )

            print("\nAssistant:\n" + resp.output_text.strip())

            # Usage + “thinking” token counts
            u = getattr(resp, "usage", None)
            rtoks = getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", None) if u else None
            print(f"\n[usage] input_tokens={getattr(u,'input_tokens',None)} | "
                  f"output_tokens={getattr(u,'output_tokens',None)} | "
                  f"reasoning_tokens={rtoks}\n")

            prev_id = resp.id

        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break
        except Exception as e:
            print(f"[error] {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
