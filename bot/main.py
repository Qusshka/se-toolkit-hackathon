import os
from dotenv import load_dotenv
from telegram import BotCommand
from telegram.ext import Application, ApplicationBuilder, CommandHandler, CallbackQueryHandler

from handlers.start import start, help_command
from handlers.expense import build_expense_conversation, cancel
from handlers.stats import stats_command, history_command
from handlers.reminders import reminders_command, dismiss_callback
from handlers.forecast import forecast_command
from handlers.agent import build_agent_conversation
from handlers.goals import build_goal_conversation
from handlers.digest import digest_command, send_digests

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

DIGEST_START_HOUR = 18  # job fires at 6pm, random delay sends it between 6pm-11pm


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands([
        BotCommand("add",       "Log an expense"),
        BotCommand("stats",     "Monthly spending summary"),
        BotCommand("forecast",  "End-of-month forecast + what-if"),
        BotCommand("history",   "Last 10 expenses"),
        BotCommand("reminders", "Upcoming recurring payments"),
        BotCommand("goal",      "Savings goal tracker"),
        BotCommand("digest",    "Toggle daily spending digest"),
        BotCommand("ask",       "Chat with AI about your spending"),
        BotCommand("help",      "Show all commands"),
        BotCommand("cancel",    "Cancel current action"),
    ])

    # Start APScheduler for daily digest
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_digests, CronTrigger(hour=DIGEST_START_HOUR, minute=0), args=[application])
    scheduler.start()
    application.bot_data["scheduler"] = scheduler


def main():
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("reminders", reminders_command))
    app.add_handler(CommandHandler("forecast", forecast_command))
    app.add_handler(CommandHandler("digest", digest_command))

    # AI agent conversation (must be before expense conversation)
    app.add_handler(build_agent_conversation())

    # Goal conversation (buttons flow)
    app.add_handler(build_goal_conversation())

    # Expense conversation + natural language fallback
    app.add_handler(build_expense_conversation())

    # Reminder dismiss callback
    app.add_handler(CallbackQueryHandler(dismiss_callback, pattern=r"^dismiss_\d+$"))

    print("Bot started. Polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
