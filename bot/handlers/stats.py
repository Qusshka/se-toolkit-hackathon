from datetime import date
from telegram import Update
from telegram.ext import ContextTypes

from utils import api_client


async def _get_user_id(telegram_id: int, username: str, first_name: str) -> int:
    user = await api_client.post("/api/users", {
        "telegram_id": telegram_id,
        "username": username,
        "first_name": first_name,
    })
    return user["id"]


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        user_id = await _get_user_id(user.id, user.username, user.first_name)
    except Exception:
        await update.message.reply_text("⚠️ Something went wrong, try again.")
        return

    today = date.today()
    month_start = today.replace(day=1)
    params = {"user_id": user_id, "from": str(month_start), "to": str(today)}

    try:
        summary = await api_client.get("/api/stats/summary", params)
        by_cat = await api_client.get("/api/stats/by-category", params)
        all_expenses = await api_client.get("/api/expenses", params)
    except Exception:
        await update.message.reply_text("⚠️ Something went wrong, try again.")
        return

    month_name = today.strftime("%B %Y")
    lines = [f"📊 Your spending — {month_name}\n"]
    lines.append(f"Total: ₽{summary['total']:.2f}")
    lines.append(f"Transactions: {summary['count']}\n")

    if by_cat:
        lines.append("By category:")
        for c in by_cat:
            icon = c["icon"] or ""
            lines.append(f"{icon} {c['category_name']:<16} ₽{c['total']:.2f}  ({c['percentage']}%)")

    if summary.get("biggest_expense"):
        big = summary["biggest_expense"]
        lines.append(f"\nBiggest single expense: {big['description']} — ₽{big['amount']:.2f}")

    # Impulse summary
    impulse_items = [e for e in all_expenses if e.get("is_impulse")]
    if impulse_items:
        impulse_total = sum(float(e["amount"]) for e in impulse_items)
        lines.append(f"\n⚡ Possible impulse buys this month: {len(impulse_items)}  (₽{impulse_total:.2f})")

    # AI tip
    try:
        insight = await api_client.post("/api/agent/insight", {"user_id": user_id, "context_days": 30})
        lines.append(f"\n{insight['tip']}")
    except Exception:
        pass

    await update.message.reply_text("\n".join(lines))


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        user_id = await _get_user_id(user.id, user.username, user.first_name)
        expenses = await api_client.get("/api/expenses", {"user_id": user_id, "limit": 10})
    except Exception:
        await update.message.reply_text("⚠️ Something went wrong, try again.")
        return

    if not expenses:
        await update.message.reply_text("No expenses recorded yet.")
        return

    lines = ["📋 Last 10 expenses:\n"]
    for e in expenses:
        cat = e.get("category") or {}
        icon = cat.get("icon", "") if cat else ""
        lines.append(f"{e['date']}  {icon} {e['description']:<20} ₽{float(e['amount']):.2f}")

    await update.message.reply_text("\n".join(lines))
