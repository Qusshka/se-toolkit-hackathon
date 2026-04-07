import os
import httpx

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
# If OLLAMA_API_KEY is set, use Ollama cloud; otherwise use local instance
OLLAMA_BASE_URL = "https://api.ollama.com" if OLLAMA_API_KEY else os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = """
You are SpendSense, a personal finance AI assistant embedded in a Telegram bot.
You have access to the user's recent expense data provided in the user message.
Your job is:
- Answer questions about spending clearly and concisely
- Identify patterns (frequent small purchases that add up)
- Flag potentially wasteful habits (daily expensive coffee, frequent takeout)
- Remind users about upcoming recurring costs
- Give specific, actionable suggestions — never generic advice
- Be friendly, direct, and non-judgmental

Keep responses under 150 words — this is a Telegram chat, not an essay.
Always end with one concrete suggestion prefixed with 💡.
"""

INSIGHT_PROMPT = """
You are a personal finance assistant. Given the user's spending summary,
produce exactly ONE short actionable tip (max 15 words).
No preamble. Start with 💡.
Example: "💡 You've bought coffee 14 times — consider a weekly budget of ₽15."
"""


def build_context(expenses: list[dict], period_days: int) -> str:
    total = sum(e["amount"] for e in expenses)
    by_category: dict[str, float] = {}
    freq: dict[str, int] = {}
    for e in expenses:
        by_category[e["category"]] = by_category.get(e["category"], 0) + e["amount"]
        key = e["description"].lower()
        freq[key] = freq.get(key, 0) + 1
    top_freq = sorted(freq.items(), key=lambda x: -x[1])[:10]
    return f"""
SPENDING SUMMARY — last {period_days} days
Total: {total:.2f} | Transactions: {len(expenses)}
By category: {by_category}
Most frequent items: {top_freq}
Recent 50 expenses: {expenses[-50:]}
"""


async def _call_groq(messages: list[dict], max_tokens: int) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={"model": GROQ_MODEL, "messages": messages, "max_tokens": max_tokens},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()


async def _call_ollama(messages: list[dict], max_tokens: int) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"num_predict": max_tokens},
    }
    headers = {}
    if OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"
    timeout = 30 if OLLAMA_API_KEY else 300
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, headers=headers)
        r.raise_for_status()
        return r.json()["message"]["content"].strip()


async def _call_llm(messages: list[dict], max_tokens: int) -> str:
    if GROQ_API_KEY:
        return await _call_groq(messages, max_tokens)
    return await _call_ollama(messages, max_tokens)  # handles both local and cloud Ollama


async def classify_category(description: str, category_names: list[str]) -> str | None:
    """Return the best-matching category name, or None if uncertain."""
    names_str = ", ".join(category_names)
    messages = [
        {
            "role": "system",
            "content": (
                f"You are a purchase categorizer. Given a purchase description, "
                f"reply with ONLY the single most fitting category name from this list: {names_str}. "
                f"No punctuation, no explanation. If truly unclear, reply: Other"
            ),
        },
        {"role": "user", "content": description},
    ]
    try:
        raw = await _call_llm(messages, max_tokens=6)
        raw = raw.strip().rstrip(".")
        for name in category_names:
            if name.lower() == raw.lower():
                return name
        return None
    except Exception:
        return None


async def chat(user_message: str, context: str, one_liner: bool = False) -> str:
    system = INSIGHT_PROMPT if one_liner else SYSTEM_PROMPT
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"{context}\n\nUser: {user_message}"},
    ]
    try:
        return await _call_llm(messages, max_tokens=60 if one_liner else 400)
    except Exception:
        return "💡 AI insights unavailable right now."
