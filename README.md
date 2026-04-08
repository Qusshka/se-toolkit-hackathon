# SpendSense
> Log expenses in Telegram, let AI tell you where your money actually goes.

## Demo
[screenshot placeholder — /stats output]
[screenshot placeholder — /forecast output]

## Product Context
- **End users:** Anyone who wants to track personal spending without a complex app
- **Problem:** Manual budgeting apps have too much friction — people stop using them
- **Solution:** Log expenses as a natural Telegram message; AI auto-categorizes, surfaces patterns, forecasts spending, and sends evening digests automatically

## Features
- ✅ Natural language expense logging via Telegram
- ✅ AI auto-categorization — type `iced latte 350`, AI picks ☕ Coffee automatically
- ✅ Monthly spending summary with category breakdown (`/stats`)
- ✅ One-liner AI tip in `/stats`
- ✅ Impulse purchase detector — flags late-night or rapid buys
- ✅ End-of-month forecast with AI savings suggestions per category (`/forecast`)
- ✅ Recurring expense tracking with reminders (`/reminders`)
- ✅ Savings goal tracker with progress bar and button-driven flow (`/goal`)
- ✅ Proactive daily digest — bot messages you every evening automatically (`/digest`)
- ✅ AI-powered spending insights (`/ask`)
- ✅ Web dashboard with pie + bar charts
- 🔲 Multi-currency support
- 🔲 Budget limits per category

## Usage

**Log an expense** — just send a message, AI picks the category:
```
iced latte 350
spent 450 on lunch
netflix 699 monthly
gym 2500 weekly
```

**Commands:**
| Command | What it does |
|---|---|
| `/add` | Guided step-by-step expense entry |
| `/stats` | Monthly summary + AI tip + impulse buy alert |
| `/history` | Last 10 expenses |
| `/forecast` | End-of-month projection + AI savings tips per category |
| `/reminders` | Upcoming recurring payments |
| `/goal` | Savings goal tracker — create, track progress, log deposits |
| `/digest` | Toggle daily evening spending digest on/off |
| `/ask` | Chat with AI about your spending |
| `/cancel` | Cancel any active flow |

## Deployment

**OS:** Ubuntu 24.04  
**Requirements:** Docker, Docker Compose v2, Git

```bash
git clone https://github.com/Qusshka/se-toolkit-hackathon.git
cd se-toolkit-hackathon
cp .env.example .env.secret
# Fill in required values in .env.secret (see below)
docker compose up -d --build db backend bot
```

> The `ollama` service is not started — AI runs via Ollama cloud API (no local model needed).

### Required environment variables (`.env.secret`)

```
DATABASE_URL=postgresql://spenduser:spendpass@db:5432/spenddb
TELEGRAM_BOT_TOKEN=<from BotFather>
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=gemma3:4b
OLLAMA_API_KEY=<from ollama.com>
BACKEND_URL=http://backend:8000
DIGEST_HOUR=21
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
```

Get a free Ollama API key at **ollama.com** → sign in → API Keys.

> **Note:** The Telegram bot must run on a machine where Telegram is accessible.
> On university VMs (where Telegram is blocked), run the bot locally and point
> `BACKEND_URL` to the VM's IP where the backend is deployed.

### Local bot setup (laptop → VM backend)

```bash
# In your local .env.secret:
BACKEND_URL=http://<VM_IP>:8000
OLLAMA_API_KEY=<your key>
OLLAMA_MODEL=gemma3:4b
TELEGRAM_BOT_TOKEN=<your token>

cd bot
pip install -r requirements.txt
python main.py
```
