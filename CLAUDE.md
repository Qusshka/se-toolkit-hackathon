# CLAUDE.md — SpendSense: AI-Powered Personal Finance Tracker

## What You Are Building

A personal finance tracker where users log expenses via a **Telegram bot** using natural language,
and an AI agent (Ollama + qwen2.5:7b, running on VM) analyzes their spending patterns,
flags wasteful habits, and reminds them about recurring costs.

**One-sentence pitch:** Log expenses in Telegram, let AI tell you where your money actually goes.

> **Note on deployment:** Telegram bots cannot run on university VMs (blocked). Run the bot
> locally. The backend + Ollama + database run on the VM via Docker Compose.

---

## Architecture Overview

```
┌──────────────────────┐
│   User (Telegram)    │
└──────────┬───────────┘
           │ Telegram Bot API (polling)
┌──────────▼───────────────────────────────────────┐
│              Bot Process (python-telegram-bot)    │
│  Parses messages → calls Backend REST API         │
└──────────────────────┬───────────────────────────┘
                       │ HTTP
┌──────────────────────▼───────────────────────────┐
│              Backend: FastAPI (Python)            │
│  /expenses  /stats  /agent  /reminders            │
└──────────────┬───────────────────────────────────┘
               │                    │
┌──────────────▼──────┐   ┌─────────▼──────────────┐
│   PostgreSQL DB     │   │  Ollama (qwen2.5:7b)   │
│  users, expenses,   │   │  running in Docker or  │
│  categories,        │   │  natively on VM        │
│  reminders          │   └────────────────────────┘
└─────────────────────┘
```

---

## Tech Stack

| Layer        | Technology                                       |
|--------------|--------------------------------------------------|
| Telegram bot | Python 3.11, python-telegram-bot 20.x            |
| Backend      | FastAPI, SQLAlchemy 2.x                           |
| Database     | PostgreSQL 15                                     |
| AI Agent     | Ollama (qwen2.5:7b), called via HTTP REST API    |
| Container    | Docker + Docker Compose                           |

---

## Repository Structure

```
se-toolkit-hackathon/
├── CLAUDE.md
├── README.md
├── LICENSE                        # MIT
├── .env.example
├── .gitignore
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                    # FastAPI entry point
│   ├── database.py                # Engine + session
│   ├── models.py                  # ORM models
│   ├── schemas.py                 # Pydantic schemas
│   ├── routers/
│   │   ├── expenses.py
│   │   ├── categories.py
│   │   ├── stats.py
│   │   ├── goals.py               # savings goals
│   │   ├── agent.py               # AI agent endpoint
│   │   └── reminders.py
│   └── services/
│       └── ai_agent.py            # Ollama integration
├── bot/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                    # Bot entry point (polling)
│   ├── handlers/
│   │   ├── start.py               # /start, /help
│   │   ├── expense.py             # logging expenses
│   │   ├── stats.py               # /stats, /history
│   │   ├── forecast.py            # /forecast — projection + what-if
│   │   ├── goals.py               # /goal — savings goal tracker
│   │   ├── digest.py              # /digest — toggle daily digest
│   │   ├── agent.py               # /ask — AI chat
│   │   └── reminders.py           # /reminders
│   └── utils/
│       └── api_client.py          # Talks to backend REST API
```

---

## Environment Variables

`.env` (never commit; `.env.example` goes in git):

```
DATABASE_URL=postgresql://spenduser:spendpass@db:5432/spenddb
TELEGRAM_BOT_TOKEN=<from BotFather>
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b
BACKEND_URL=http://backend:8000
DIGEST_HOUR=21
```

---

## Database Schema

Use SQLAlchemy models with `Base.metadata.create_all()` on startup. No Alembic needed.

### Table: `users`
```sql
id              SERIAL PRIMARY KEY
telegram_id     BIGINT NOT NULL UNIQUE
username        VARCHAR(100)
first_name      VARCHAR(100)
digest_enabled  BOOLEAN DEFAULT TRUE     -- daily digest opt-in
created_at      TIMESTAMP DEFAULT NOW()
```

### Table: `goals`
```sql
id          SERIAL PRIMARY KEY
user_id     INTEGER REFERENCES users(id)
name        VARCHAR(255) NOT NULL        -- e.g. "iPhone 16"
target      NUMERIC(10,2) NOT NULL       -- e.g. 80000
saved       NUMERIC(10,2) DEFAULT 0      -- manually updated via /goal add 5000
deadline    DATE                         -- optional target date
created_at  TIMESTAMP DEFAULT NOW()
```

### Table: `categories`
```sql
id          SERIAL PRIMARY KEY
name        VARCHAR(100) NOT NULL UNIQUE
icon        VARCHAR(10)                  -- emoji e.g. "☕"
color       VARCHAR(7)                   -- hex e.g. "#FF9F40"
```

Seed on first run:
- Food 🍔 #FF6384
- Coffee ☕ #FF9F40
- Transport 🚌 #FFCD56
- Shopping 🛍️ #4BC0C0
- Entertainment 🎬 #36A2EB
- Health 💊 #9966FF
- Subscriptions 📦 #C9CBCF
- Other 💸 #E7E9ED

### Table: `expenses`
```sql
id            SERIAL PRIMARY KEY
user_id       INTEGER REFERENCES users(id)
amount        NUMERIC(10, 2) NOT NULL
description   VARCHAR(255) NOT NULL
category_id   INTEGER REFERENCES categories(id)
date          DATE NOT NULL DEFAULT CURRENT_DATE
is_recurring  BOOLEAN DEFAULT FALSE
recur_days    INTEGER                   -- NULL if not recurring; e.g. 30 for monthly
next_reminder DATE                      -- auto-computed: date + recur_days
created_at    TIMESTAMP DEFAULT NOW()
```

### Table: `reminders`
```sql
id          SERIAL PRIMARY KEY
expense_id  INTEGER REFERENCES expenses(id) ON DELETE CASCADE
user_id     INTEGER REFERENCES users(id)
remind_at   DATE NOT NULL
message     TEXT
is_sent     BOOLEAN DEFAULT FALSE
created_at  TIMESTAMP DEFAULT NOW()
```

---

## Telegram Bot — Commands & Flows

### Commands

| Command      | Description                                      |
|--------------|--------------------------------------------------|
| `/start`     | Register user, show welcome message + help       |
| `/help`      | Show all commands with examples                  |
| `/add`       | Guided step-by-step expense logging              |
| `/history`   | Show last 10 expenses                            |
| `/stats`     | This month's summary with category totals + AI tip |
| `/forecast`  | Project end-of-month total based on current pace + what-if savings |
| `/goal`      | Set a savings goal with deadline and track progress |
| `/digest`    | Toggle daily evening spending digest on/off      |
| `/reminders` | Show upcoming recurring payment reminders        |
| `/ask`       | Start AI agent conversation                      |
| `/cancel`    | Cancel any active conversation flow              |

### Natural Language Logging (core UX)

Users can also send a plain message without any command. The bot tries to parse it:

- `"coffee 3.50"` → amount=3.50, description="coffee" → prompt for category
- `"spent 12 on lunch"` → amount=12, description="lunch" → prompt for category
- `"netflix 15 monthly"` → amount=15, description="netflix", is_recurring=True, recur_days=30

**Parsing logic** (`bot/handlers/expense.py`):
Use simple regex + keyword matching. Do NOT use the LLM for this — keep it fast.

```python
import re

RECURRING_KEYWORDS = {"monthly": 30, "weekly": 7, "yearly": 365, "every month": 30}

def parse_expense_message(text: str) -> dict | None:
    pattern = r"(?:spent|paid)?\s*(\d+(?:[.,]\d{1,2})?)\s*(?:on|for)?\s*(.+)"
    match = re.match(pattern, text.strip(), re.IGNORECASE)
    if not match:
        return None
    amount = float(match.group(1).replace(",", "."))
    description = match.group(2).strip()
    is_recurring = False
    recur_days = None
    for kw, days in RECURRING_KEYWORDS.items():
        if kw in description.lower():
            is_recurring = True
            recur_days = days
            description = re.sub(kw, "", description, flags=re.IGNORECASE).strip()
            break
    return {"amount": amount, "description": description,
            "is_recurring": is_recurring, "recur_days": recur_days}
```

### Category Selection via Inline Keyboard

After parsing, bot sends inline keyboard with category buttons. User taps → expense saved → bot confirms:

```
✅ Saved: Oat latte — ₽3.50
Category: ☕ Coffee | Date: today

Total on coffee this month: ₽47.50 (14 purchases)
```

### /stats Output Format

```
📊 Your spending — April 2026

Total: ₽312.40
Transactions: 28

By category:
☕ Coffee         ₽47.50  (15%)
🍔 Food           ₽89.00  (28%)
🚌 Transport      ₽34.00  (11%)
📦 Subscriptions  ₽45.00  (14%)
💸 Other          ₽96.90  (31%)

Biggest single expense: Dentist — ₽80.00

💡 You've bought coffee 14 times this month — try a weekly ₽15 budget.
```

The 💡 tip is generated by the AI agent (one sentence, cheap call to `/api/agent/insight`).

### /ask — AI Conversation Flow

```
User: /ask
Bot:  What would you like to know about your spending?

      [Where am I overspending?]  [My coffee habit]
      [Upcoming subscriptions]    [How to save money?]

User: where am i overspending?
Bot:  You've spent ₽47.50 on coffee across 14 purchases this month —
      that's ₽3.39 per visit on average.

      💡 Skipping 3 coffees per week saves ~₽40/month, ~₽480/year.

      [Tell me more]  [Show subscriptions]  [Done ✅]
```

### /reminders Output Format

```
🔔 Upcoming reminders

📦 Netflix — ₽15.00
   Renews in 3 days (April 9)

📦 Gym membership — ₽35.00
   Renews in 12 days (April 18)

[Dismiss Netflix]  [Dismiss Gym]
```

### /forecast Output Format

`/forecast` combines two things in one screen: **end-of-month projection** based on current
daily average, and **what-if savings** for the top recurring habits. No LLM needed — pure math.

```
📈 Spending forecast — April 2026

So far this month: ₽8 450  (13 days)
Daily average: ₽650
Days remaining: 17

Projected total: ₽19 500
Last month: ₽16 200  ⚠️ +20%

─────────────────────────
✂️ What if you cut back?

☕ Coffee (14 purchases, ₽3 640)
  Skip 1/day → save ₽1 820 → projected ₽17 680
  Skip all   → save ₽3 640 → projected ₽15 860

🍔 Takeout (6 purchases, ₽2 100)
  Cut in half → save ₽1 050 → projected ₽18 450

📦 Subscriptions renewing this month: ₽1 200
```

**How to compute it** (`backend/routers/stats.py` — add new endpoint, or `bot/handlers/forecast.py`
can compute directly from the expenses API without a new backend endpoint):

```python
from datetime import date, timedelta
import calendar

def compute_forecast(expenses: list[dict], user_id: int) -> dict:
    today = date.today()
    month_start = today.replace(day=1)
    days_passed = today.day
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_remaining = days_in_month - days_passed

    # Filter current month
    this_month = [e for e in expenses
                  if date.fromisoformat(e["date"]) >= month_start]
    total_so_far = sum(e["amount"] for e in this_month)
    daily_avg = total_so_far / days_passed if days_passed > 0 else 0
    projected = total_so_far + daily_avg * days_remaining

    # Top categories by spend this month for what-if
    by_category: dict[str, float] = {}
    by_category_count: dict[str, int] = {}
    for e in this_month:
        cat = e["category"]
        by_category[cat] = by_category.get(cat, 0) + e["amount"]
        by_category_count[cat] = by_category_count.get(cat, 0) + 1

    top = sorted(by_category.items(), key=lambda x: -x[1])[:3]

    whatif = []
    for cat, spent in top:
        count = by_category_count[cat]
        per_item = spent / count if count else 0
        whatif.append({
            "category": cat,
            "total": spent,
            "count": count,
            "save_half": spent / 2,
            "projected_if_half": projected - spent / 2,
        })

    return {
        "total_so_far": total_so_far,
        "daily_avg": daily_avg,
        "days_remaining": days_remaining,
        "projected": projected,
        "whatif": whatif,
    }
```

Add endpoint to `routers/stats.py`:
```
GET /api/stats/forecast?user_id=&month=YYYY-MM
    → { total_so_far, daily_avg, days_remaining, projected, whatif: [...] }
```

Add `bot/handlers/forecast.py` — calls the endpoint, formats and sends the message above.

---

## Feature: Daily Digest (Proactive Push)

The bot sends a message to the user every evening at a configured time **without the user asking**.
This is the key differentiator — the bot initiates contact.

### Output format (sent automatically each evening)

```
🌙 Daily digest — Monday, April 7

Today: ₽1 240 across 3 purchases
  ☕ Coffee       ₽340
  🍔 Lunch        ₽650
  🚌 Metro        ₽250

This month so far: ₽9 680 / 7 days
On track for: ₽41 500 this month

⚠️ Coffee today = ₽340 — that's your 3rd coffee this week.
```

If user spent nothing today: `✅ No expenses today — solid day.`

### Implementation — APScheduler inside the bot process

Add `apscheduler==3.10.4` to `bot/requirements.txt`.
Add `DIGEST_HOUR=21` to `.env` and `.env.example`.

In `bot/main.py`, after building the Application:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio, os

DIGEST_HOUR = int(os.getenv("DIGEST_HOUR", "21"))

async def send_digests():
    users = await api_client.get("/api/users/digest-enabled")
    for user in users:
        today = str(date.today())
        month_start = str(date.today().replace(day=1))
        expenses_today = await api_client.get(
            "/api/expenses", params={"user_id": user["id"], "from": today, "to": today}
        )
        summary = await api_client.get(
            "/api/stats/summary", params={"user_id": user["id"], "from": month_start, "to": today}
        )
        text = format_digest(user, expenses_today, summary)
        await application.bot.send_message(chat_id=user["telegram_id"], text=text)

scheduler = AsyncIOScheduler()
scheduler.add_job(send_digests, CronTrigger(hour=DIGEST_HOUR, minute=0))
scheduler.start()
```

Add backend endpoint:
```
GET /api/users/digest-enabled   → list of users where digest_enabled=true
PATCH /api/users/{id}/digest    Body: { "enabled": true/false }
```

`/digest` command toggles `digest_enabled` on the user row:
```
✅ Daily digest ON — I'll message you every evening at 9pm.
🔕 Daily digest OFF.
```

---

## Feature: Savings Goal Tracker

Users set a named savings goal with a target and optional deadline. The bot tracks progress
and shows how current spending habits affect the timeline.

### Commands

```
/goal new iPhone 16 80000 2026-12-31   → create goal
/goal add 5000                          → log a deposit toward active goal
/goal                                   → show all goals
```

### Output format

```
🎯 Savings Goals

📱 iPhone 16
  Target:   ₽80 000
  Saved:    ₽23 500  (29%)
  ████░░░░░░░░░░░░░░░░  29%
  Deadline: Dec 31, 2026  (269 days away)
  Need:     ₽210/day to hit target on time

  ⚠️ You spent ₽3 640 on coffee this month.
     Cutting it in half frees up ₽33/day toward this goal.
```

### Progress bar helper

```python
def progress_bar(pct: float, width: int = 20) -> str:
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled)
```

### API endpoints — new `routers/goals.py`

```
POST   /api/goals                     { user_id, name, target, deadline? }
GET    /api/goals?user_id=            list all goals for user
PUT    /api/goals/{id}/deposit        { amount } → adds to saved
DELETE /api/goals/{id}
```

Bot handler: `bot/handlers/goals.py`
Parse `/goal new <name> <amount> [YYYY-MM-DD]` with regex.
Parse `/goal add <amount>` — if multiple goals exist, show inline keyboard to pick one.
Parse `/goal` alone — show all goals with progress bars.

---

## Feature: Impulse Purchase Detector

Automatically tags expenses as potentially impulsive. Passive — no user action needed.
Shows up in `/stats` only when flagged purchases exist.

### Detection rules (run on every POST /api/expenses)

```python
from datetime import datetime, time, timedelta

def is_impulse(created_at: datetime, recent_expenses: list[dict]) -> bool:
    # Rule 1: logged between 23:00 and 04:00
    late_night = created_at.time() >= time(23, 0) or created_at.time() <= time(4, 0)
    # Rule 2: 3+ expenses within the last 30 minutes
    cutoff = created_at - timedelta(minutes=30)
    rapid = sum(1 for e in recent_expenses
                if datetime.fromisoformat(e["created_at"]) >= cutoff) >= 2
    return late_night or rapid
```

### DB change — add column to `expenses`

```sql
is_impulse  BOOLEAN DEFAULT FALSE
```

Set this flag in `routers/expenses.py` POST handler before saving.

### How it surfaces

In `/stats` output, append at the bottom if any impulse purchases flagged this month:

```
⚡ Possible impulse buys this month: 4  (₽2 180)
   [Show details]   ← inline button → lists the flagged expenses
```

In `/ask` AI context, include:
```
Impulse-flagged purchases this month: 4 items, ₽2 180 total
```
So the AI can reference it naturally in its analysis.

---

## Backend: API Endpoints
```json
{ "telegram_id": 123456789, "username": "alex", "first_name": "Alex" }
```

### Expenses — `routers/expenses.py`
```
POST   /api/expenses
GET    /api/expenses?user_id=&from=&to=&category_id=&limit=&offset=
GET    /api/expenses/{id}
PUT    /api/expenses/{id}
DELETE /api/expenses/{id}
```
On POST, if `is_recurring=true` and `recur_days` is set: set `next_reminder`, insert reminder row.
Also run `is_impulse()` check and set `is_impulse` flag before saving.

### Categories — `routers/categories.py`
```
GET  /api/categories
POST /api/categories
```

### Goals — `routers/goals.py`
```
POST   /api/goals                  { user_id, name, target, deadline? }
GET    /api/goals?user_id=
PUT    /api/goals/{id}/deposit     { amount }
DELETE /api/goals/{id}
```

### Users — digest control
```
GET   /api/users/digest-enabled
PATCH /api/users/{id}/digest       { "enabled": true/false }
```

### Stats — `routers/stats.py`
```
GET /api/stats/summary?user_id=&from=&to=
    → { total, count, avg_per_day, biggest_expense }

GET /api/stats/by-category?user_id=&from=&to=
    → [{ category_name, icon, color, total, percentage }]

GET /api/stats/by-day?user_id=&from=&to=
    → [{ date, total }]

GET /api/stats/forecast?user_id=&month=YYYY-MM
    → { total_so_far, daily_avg, days_remaining, projected, whatif: [...] }
```

### Reminders — `routers/reminders.py`
```
GET  /api/reminders/due?user_id=
     → reminders where remind_at <= today AND is_sent=false

POST /api/reminders/{id}/dismiss
     → sets is_sent=true
```

### AI Agent — `routers/agent.py`
```
POST /api/agent/chat
     Body: { "user_id": 1, "message": "...", "context_days": 30 }
     → { "reply": "..." }

POST /api/agent/insight
     Body: { "user_id": 1, "context_days": 30 }
     → { "tip": "one short actionable sentence" }
```

---

## AI Agent Logic — `backend/services/ai_agent.py`

### System Prompts

```python
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
```

### Context Builder

```python
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
```

### Ollama API Call

```python
import httpx, os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

async def chat(user_message: str, context: str, one_liner: bool = False) -> str:
    system = INSIGHT_PROMPT if one_liner else SYSTEM_PROMPT
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": f"{context}\n\nUser: {user_message}"},
        ],
        "stream": False,
        "options": {"num_predict": 60 if one_liner else 400},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
```

> `stream: false` waits for the full response. Timeout 60s — qwen2.5:7b is fast on CPU but allow headroom.

---

## Web Dashboard (Frontend)

Two pages. Simple and functional — secondary to the bot.

### `index.html` — Dashboard
- Header + nav: Dashboard | History
- Summary cards: Total this month | Avg/day | Top category | # transactions
- Pie chart (by category) — Chart.js
- Bar chart (by day, last 30 days) — Chart.js
- User filter via URL param `?user_id=1` (no auth needed)

### `history.html` — Expense History
- Filter: date range + category dropdown
- Table: date | description | category icon | amount
- Last 50 expenses

### `js/api.js`
```javascript
const API_BASE = window.API_BASE || "http://localhost:8000/api";

async function apiFetch(path, options = {}) {
    const res = await fetch(API_BASE + path, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}
```

---

## Bot API Client — `bot/utils/api_client.py`

The bot never touches the DB directly — always goes through the backend.

```python
import httpx, os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

async def post(path: str, data: dict) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BACKEND_URL}{path}", json=data, timeout=10)
        r.raise_for_status()
        return r.json()

async def get(path: str, params: dict = None) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BACKEND_URL}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
```

---

## Docker Compose

```yaml
version: "3.9"

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: spenduser
      POSTGRES_PASSWORD: spendpass
      POSTGRES_DB: spenddb
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U spenduser -d spenddb"]
      interval: 5s
      timeout: 5s
      retries: 5

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    restart: unless-stopped

  backend:
    build: ./backend
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

  bot:
    build: ./bot
    env_file: .env
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  pgdata:
  ollama_data:
```

### `backend/Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `bot/Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### `backend/requirements.txt`
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.30
psycopg2-binary==2.9.9
pydantic==2.7.1
pydantic-settings==2.2.1
python-dotenv==1.0.1
httpx==0.27.0
```

### `bot/requirements.txt`
```
python-telegram-bot==20.8
httpx==0.27.0
python-dotenv==1.0.1
apscheduler==3.10.4
```

---

## Implementation Order

### Phase 1 — Version 1 (bot + core tracking)

Implement in this exact order:

1. `backend/database.py` — engine, SessionLocal, Base
2. `backend/models.py` — User, Category, Expense, Reminder
3. `backend/schemas.py` — Pydantic in/out schemas
4. `backend/main.py` — app init, startup seed, mount routers
5. `backend/routers/categories.py`
6. `backend/routers/expenses.py` — full CRUD + auto reminder on recurring
7. `backend/routers/stats.py` — summary, by-category, by-day
8. `backend/routers/reminders.py` — due list + dismiss
9. `bot/utils/api_client.py`
10. `bot/handlers/start.py` — /start (upsert user), /help
11. `bot/handlers/expense.py` — natural language parser + ConversationHandler + inline keyboard
12. `bot/handlers/stats.py` — /stats, /history
13. `bot/handlers/forecast.py` — /forecast with projection + what-if table
14. `bot/handlers/reminders.py` — /reminders with inline dismiss
14. `bot/main.py` — wire all handlers
15. `docker-compose.yml` + all Dockerfiles
16. Test: log 10 expenses, check /stats output, add a recurring expense, check /reminders

### Phase 2 — Version 2 (AI agent + smart features)

17. `backend/services/ai_agent.py`
18. `backend/routers/agent.py` — /chat and /insight
19. `backend/routers/goals.py` — goals CRUD + deposit
20. Add `digest_enabled` to users model, add `/api/users/digest-enabled` + PATCH endpoint
21. Add `is_impulse` column to expenses, add detection logic in POST handler
22. `bot/handlers/agent.py` — /ask with quick-option inline chips
23. `bot/handlers/goals.py` — /goal with progress bar
24. `bot/handlers/digest.py` — /digest toggle
25. Add APScheduler to `bot/main.py` — daily digest job
26. Add 💡 AI tip to /stats output (call /insight)
27. Add impulse summary block to /stats output
28. Full end-to-end test: `docker compose up --build` from clean state
29. `README.md` with screenshots

---

## Key Implementation Notes

### ConversationHandler for /add

Use `python-telegram-bot`'s `ConversationHandler` for multi-step entry:
```
States: ASK_AMOUNT → ASK_DESCRIPTION → ASK_CATEGORY → CONFIRM
```
For natural language (plain message not starting with /), use a plain `MessageHandler` that
calls the parser. If parsing fails, start the guided flow. If parsing succeeds, skip straight
to category selection.

### Startup category seeding

```python
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if db.query(Category).count() == 0:
        db.add_all([
            Category(name="Food",          icon="🍔", color="#FF6384"),
            Category(name="Coffee",        icon="☕", color="#FF9F40"),
            Category(name="Transport",     icon="🚌", color="#FFCD56"),
            Category(name="Shopping",      icon="🛍️", color="#4BC0C0"),
            Category(name="Entertainment", icon="🎬", color="#36A2EB"),
            Category(name="Health",        icon="💊", color="#9966FF"),
            Category(name="Subscriptions", icon="📦", color="#C9CBCF"),
            Category(name="Other",         icon="💸", color="#E7E9ED"),
        ])
        db.commit()
    db.close()
```

### Recurring expense → reminder creation

```python
if body.is_recurring and body.recur_days:
    from datetime import timedelta
    db.add(Reminder(
        expense_id=expense.id,
        user_id=body.user_id,
        remind_at=body.date + timedelta(days=body.recur_days),
        message=f"Recurring: {body.description} — {body.amount}"
    ))
    db.commit()
```

---

## Error Handling Rules

- All API errors: `{"detail": "human-readable message"}` with correct HTTP status
- Bot handlers: wrap API calls in try/except → send `"⚠️ Something went wrong, try again."` on failure
- Ollama failure (model not loaded, timeout): return `"💡 AI insights unavailable right now."` — never crash the bot
- DB failures: rollback + log, return 500

---

## README.md Structure to Generate

```markdown
# SpendSense
> One-line description

## Demo
[screenshot placeholder]
[screenshot placeholder]

## Product Context
- **End users:** ...
- **Problem:** ...
- **Solution:** ...

## Features
- ✅ Natural language expense logging via Telegram
- ✅ Category selection with inline keyboard
- ✅ Monthly spending summary with category breakdown
- ✅ Recurring expense tracking with reminders
- ✅ End-of-month forecast + what-if savings calculator (/forecast)
- ✅ Savings goal tracker with progress bar (/goal)
- ✅ Proactive daily spending digest (bot messages you at 9pm)
- ✅ Impulse purchase detector (auto-flags late night / rapid buys)
- ✅ AI-powered spending insights (/ask)
- ✅ One-liner AI tip in /stats
- 🔲 Multi-currency support
- 🔲 Budget limits per category

## Usage
...how to log, use /stats, /ask, /reminders...

## Deployment
**OS:** Ubuntu 24.04
**Requirements:** Docker, Docker Compose v2, Git

\`\`\`bash
git clone https://github.com/<YOU>/se-toolkit-hackathon.git
cd se-toolkit-hackathon
cp .env.example .env
# Fill in TELEGRAM_BOT_TOKEN in .env
docker compose up -d --build
\`\`\`

> Note: The Telegram bot must run on a machine where Telegram is accessible.
> On university VMs (where Telegram is blocked), run the bot locally and point
> BACKEND_URL to the VM's IP where the backend is deployed.
```

---

## What You (the Human) Must Do Manually

1. **Talk to BotFather** on Telegram → `/newbot` → copy the token into `.env`
2. **Create `.env`** with your `TELEGRAM_BOT_TOKEN` (no paid API keys needed)
3. **Install Docker on the VM** (for backend + Ollama + database deployment):
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
   sudo usermod -aG docker $USER
   # log out and back in
   ```
4. **Pull the model** after first `docker compose up`:
   ```bash
   docker exec -it <ollama_container> ollama pull qwen2.5:7b
   ```
5. **Run the bot locally** (your laptop) since Telegram is blocked on university VMs;
   set `BACKEND_URL=http://<VM_IP>:8000` and `OLLAMA_BASE_URL=http://<VM_IP>:11434` in your local `.env`
6. **Add screenshots** to README.md after testing
7. **Create GitHub repo** named `se-toolkit-hackathon`, add MIT license, push

Everything else Claude Code implements fully.