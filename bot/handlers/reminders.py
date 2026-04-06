from datetime import date
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from utils import api_client


async def _get_user_id(telegram_id: int, username: str, first_name: str) -> int:
    user = await api_client.post("/api/users", {
        "telegram_id": telegram_id,
        "username": username,
        "first_name": first_name,
    })
    return user["id"]


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        user_id = await _get_user_id(user.id, user.username, user.first_name)
        reminders = await api_client.get("/api/reminders/due", {"user_id": user_id})
    except Exception:
        await update.message.reply_text("⚠️ Something went wrong, try again.")
        return

    if not reminders:
        await update.message.reply_text("No upcoming reminders.")
        return

    today = date.today()
    lines = ["🔔 Upcoming reminders\n"]
    buttons = []

    for r in reminders:
        expense = r.get("expense") or {}
        description = expense.get("description", r.get("message", "Unknown"))
        amount = float(expense.get("amount", 0))
        remind_date = r["remind_at"]
        remind_d = date.fromisoformat(remind_date)
        days_until = (remind_d - today).days

        if days_until < 0:
            when = f"overdue ({remind_date})"
        elif days_until == 0:
            when = "today"
        else:
            when = f"in {days_until} day{'s' if days_until != 1 else ''} ({remind_date})"

        lines.append(f"📦 {description} — ₽{amount:.2f}")
        lines.append(f"   Renews {when}\n")
        buttons.append(InlineKeyboardButton(f"Dismiss {description}", callback_data=f"dismiss_{r['id']}"))

    keyboard = [[b] for b in buttons]
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def dismiss_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    reminder_id = int(query.data.replace("dismiss_", ""))
    try:
        await api_client.post(f"/api/reminders/{reminder_id}/dismiss", {})
        await query.edit_message_text(query.message.text + "\n\n✅ Dismissed.")
    except Exception:
        await query.edit_message_text("⚠️ Something went wrong, try again.")
