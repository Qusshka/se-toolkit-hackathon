# SpendSense
> Log expenses in Telegram, let AI tell you where your money actually goes.

## Demo
<img width="412" height="222" alt="Screenshot 2026-04-08 at 14 28 20" src="https://github.com/user-attachments/assets/5c418767-adaa-4792-88e3-d83d4ce8f66c" />
<img width="431" height="310" alt="Screenshot 2026-04-08 at 14 28 35" src="https://github.com/user-attachments/assets/18530ff7-25df-4f2b-8681-202988763d35" />

## Product Context
- **End users:** Anyone who wants to track personal spending without a complex app
- **Problem:** Manual budgeting apps have too much friction — people stop using them
- **Solution:** Log expenses as a natural Telegram message; AI surfaces patterns and forecasts automatically

## Features
- ✅ Natural language expense logging via Telegram
- ✅ Category selection with inline keyboard
- ✅ Monthly spending summary with category breakdown (`/stats`)
- ✅ End-of-month forecast + what-if savings calculator (`/forecast`)
- ✅ Recurring expense tracking with reminders (`/reminders`)
- ✅ AI-powered spending insights (`/ask`)
- ✅ One-liner AI tip in `/stats`
- ✅ Web dashboard with pie + bar charts
- 🔲 Multi-currency support
- 🔲 Budget limits per category

## Usage

**Log an expense** — just send a message:
```
coffee 3.50
spent 12 on lunch
netflix 15 monthly
```

**Commands:**
| Command | What it does |
|---|---|
| `/add` | Guided step-by-step expense entry |
| `/history` | Last 10 expenses |
| `/stats` | Monthly summary + AI tip |
| `/forecast` | End-of-month projection + what-if calculator |
| `/reminders` | Upcoming recurring payments |
| `/ask` | Chat with AI about your spending |

## Deployment

**OS:** Ubuntu 24.04  
**Requirements:** Docker, Docker Compose v2, Git

```bash
git clone https://github.com/<YOU>/se-toolkit-hackathon.git
cd se-toolkit-hackathon
cp .env.example .env
# Fill in TELEGRAM_BOT_TOKEN in .env
docker compose up -d --build
```

Pull the AI model after first startup:
```bash
docker exec -it $(docker compose ps -q ollama) ollama pull qwen2.5:7b
```

> **Note:** The Telegram bot must run on a machine where Telegram is accessible.
> On university VMs (where Telegram is blocked), run the bot locally and point
> `BACKEND_URL` to the VM's IP where the backend is deployed.

### Local bot setup (laptop → VM backend)
```bash
# In your local .env:
BACKEND_URL=http://<VM_IP>:8000
OLLAMA_BASE_URL=http://<VM_IP>:11434
TELEGRAM_BOT_TOKEN=<your token>

pip install -r bot/requirements.txt
python -m bot.main
```
