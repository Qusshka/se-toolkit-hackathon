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


async def forecast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        user_id = await _get_user_id(user.id, user.username, user.first_name)
    except Exception:
        await update.message.reply_text("⚠️ Something went wrong, try again.")
        return

    today = date.today()
    month_param = today.strftime("%Y-%m")

    try:
        data = await api_client.get("/api/stats/forecast", {"user_id": user_id, "month": month_param})
    except Exception:
        await update.message.reply_text("⚠️ Something went wrong, try again.")
        return

    month_name = today.strftime("%B %Y")
    total_so_far = data["total_so_far"]
    daily_avg = data["daily_avg"]
    days_remaining = data["days_remaining"]
    days_passed = data["days_passed"]
    projected = data["projected"]
    last_month = data["last_month_total"]
    whatif = data["whatif"]

    # trend vs last month
    if last_month > 0:
        pct = (projected - last_month) / last_month * 100
        if pct > 5:
            trend = f"Last month: ₽{last_month:.2f}  ⚠️ +{pct:.0f}%"
        elif pct < -5:
            trend = f"Last month: ₽{last_month:.2f}  ✅ {pct:.0f}%"
        else:
            trend = f"Last month: ₽{last_month:.2f}  ≈ on track"
    else:
        trend = "Last month: no data"

    lines = [
        f"📈 Spending forecast — {month_name}\n",
        f"So far this month: ₽{total_so_far:.2f}  ({days_passed} days)",
        f"Daily average: ₽{daily_avg:.2f}",
        f"Days remaining: {days_remaining}\n",
        f"Projected total: ₽{projected:.2f}",
        trend,
    ]

    if whatif:
        lines.append("\n─────────────────────────")
        lines.append("✂️ What if you cut back?\n")
        for w in whatif:
            icon = w.get("icon", "")
            cat = w["category"]
            total = w["total"]
            count = w["count"]
            save_half = w["save_half"]
            proj_half = w["projected_if_half"]
            lines.append(f"{icon} {cat} ({count} purchases, ₽{total:.2f})")
            lines.append(f"  Cut in half → save ₽{save_half:.2f} → projected ₽{proj_half:.2f}\n")

    await update.message.reply_text("\n".join(lines))
