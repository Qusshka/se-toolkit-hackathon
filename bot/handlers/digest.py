from datetime import date
from telegram import Update
from telegram.ext import ContextTypes

from utils import api_client


async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        db_user = await api_client.post("/api/users", {
            "telegram_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
        })
        user_id = db_user["id"]
        current = db_user.get("digest_enabled", True)
        new_state = not current
        await api_client.patch(f"/api/users/{user_id}/digest", {"enabled": new_state})
    except Exception:
        await update.message.reply_text("⚠️ Something went wrong, try again.")
        return

    if new_state:
        await update.message.reply_text("✅ Daily digest ON — I'll message you every evening at 9pm.")
    else:
        await update.message.reply_text("🔕 Daily digest OFF.")


def format_digest(user: dict, expenses_today: list, summary: dict) -> str:
    today = date.today()
    day_name = today.strftime("%A, %B %-d")
    lines = [f"🌙 Daily digest — {day_name}\n"]

    if not expenses_today:
        lines.append("✅ No expenses today — solid day.")
    else:
        total_today = sum(float(e["amount"]) for e in expenses_today)
        lines.append(f"Today: ₽{total_today:,.0f} across {len(expenses_today)} purchases")
        # Group by category
        by_cat: dict[str, float] = {}
        for e in expenses_today:
            cat = e.get("category") or {}
            icon = cat.get("icon", "") if cat else ""
            name = cat.get("name", "Other") if cat else "Other"
            key = f"{icon} {name}".strip()
            by_cat[key] = by_cat.get(key, 0) + float(e["amount"])
        for cat_label, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
            lines.append(f"  {cat_label:<18} ₽{amt:,.0f}")

    total_month = summary.get("total", 0)
    count_days = today.day
    projected = (total_month / count_days * 30) if count_days > 0 else 0
    lines.append(f"\nThis month so far: ₽{total_month:,.0f} / {count_days} days")
    lines.append(f"On track for: ₽{projected:,.0f} this month")

    return "\n".join(lines)


async def send_digests(application) -> None:
    try:
        users = await api_client.get("/api/users/digest-enabled")
    except Exception:
        return

    today = date.today()
    today_str = str(today)
    month_start = str(today.replace(day=1))

    for user in users:
        try:
            expenses_today = await api_client.get(
                "/api/expenses",
                {"user_id": user["id"], "from": today_str, "to": today_str},
            )
            summary = await api_client.get(
                "/api/stats/summary",
                {"user_id": user["id"], "from": month_start, "to": today_str},
            )
            text = format_digest(user, expenses_today, summary)
            await application.bot.send_message(chat_id=user["telegram_id"], text=text)
        except Exception:
            continue
