from telegram import Update
from telegram.ext import ContextTypes

from utils import api_client

HELP_TEXT = """
*SpendSense* — your personal finance tracker 💰

*Logging expenses:*
Just send a message like:
  • `coffee 350`
  • `spent 450 on lunch`
  • `netflix 699 monthly`
  • `gym 2500 monthly`

Or use /add for guided entry \(category first, then amount\)\.

*Commands:*
/add — Log an expense
/stats — Monthly spending summary
/forecast — End\-of\-month projection \+ what\-if
/history — Last 10 expenses
/reminders — Upcoming recurring payments
/ask — Chat with AI about your spending
/cancel — Cancel current action
/help — Show this message
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        await api_client.post("/api/users", {
            "telegram_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
        })
    except Exception:
        pass

    await update.message.reply_text(
        f"👋 Welcome, {user.first_name or 'there'}!\n\n" + HELP_TEXT,
        parse_mode="MarkdownV2",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="MarkdownV2")
