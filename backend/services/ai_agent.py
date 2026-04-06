import os
import httpx

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

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


async def chat(user_message: str, context: str, one_liner: bool = False) -> str:
    system = INSIGHT_PROMPT if one_liner else SYSTEM_PROMPT
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"{context}\n\nUser: {user_message}"},
        ],
        "stream": False,
        "options": {"num_predict": 60 if one_liner else 400},
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
            r.raise_for_status()
            return r.json()["message"]["content"].strip()
    except Exception:
        return "💡 AI insights unavailable right now."
