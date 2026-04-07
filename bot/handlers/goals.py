import re
from datetime import date
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from utils import api_client


def progress_bar(pct: float, width: int = 20) -> str:
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled)


async def _get_user_id(user) -> int:
    db_user = await api_client.post("/api/users", {
        "telegram_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
    })
    return db_user["id"]


def _format_goal(goal: dict, today: date) -> str:
    name = goal["name"]
    target = float(goal["target"])
    saved = float(goal["saved"])
    pct = min(saved / target * 100, 100) if target > 0 else 0
    bar = progress_bar(pct)
    lines = [
        f"🎯 {name}",
        f"  Target: ₽{target:,.0f}",
        f"  Saved:  ₽{saved:,.0f}  ({pct:.0f}%)",
        f"  {bar}  {pct:.0f}%",
    ]
    if goal.get("deadline"):
        deadline = date.fromisoformat(goal["deadline"])
        days_away = (deadline - today).days
        lines.append(f"  Deadline: {deadline.strftime('%b %d, %Y')}  ({days_away} days away)")
        remaining = target - saved
        if days_away > 0 and remaining > 0:
            per_day = remaining / days_away
            lines.append(f"  Need: ₽{per_day:.0f}/day to hit target on time")
    return "\n".join(lines)


async def goal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args or []

    try:
        user_id = await _get_user_id(user)
    except Exception:
        await update.message.reply_text("⚠️ Something went wrong, try again.")
        return

    if not args:
        # Show all goals
        try:
            goals = await api_client.get("/api/goals", {"user_id": user_id})
        except Exception:
            await update.message.reply_text("⚠️ Something went wrong, try again.")
            return

        if not goals:
            await update.message.reply_text(
                "No goals yet.\n\nCreate one:\n`/goal new iPhone 16 80000 2026-12-31`",
                parse_mode="Markdown",
            )
            return

        today = date.today()
        text = "🎯 Savings Goals\n\n" + "\n\n".join(_format_goal(g, today) for g in goals)
        await update.message.reply_text(text)
        return

    sub = args[0].lower()

    if sub == "new":
        # /goal new <name...> <amount> [YYYY-MM-DD]
        rest = " ".join(args[1:])
        # Try to extract optional date at end
        deadline = None
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})$", rest)
        if date_match:
            try:
                deadline = date_match.group(1)
                rest = rest[:date_match.start()].strip()
            except ValueError:
                deadline = None

        # Last token in rest is the amount
        parts = rest.rsplit(None, 1)
        if len(parts) < 2:
            await update.message.reply_text(
                "Usage: `/goal new <name> <amount> [YYYY-MM-DD]`\nExample: `/goal new iPhone 16 80000 2026-12-31`",
                parse_mode="Markdown",
            )
            return

        name = parts[0].strip()
        try:
            target = float(parts[1].replace(",", "."))
        except ValueError:
            await update.message.reply_text("Invalid amount. Example: `/goal new iPhone 16 80000`", parse_mode="Markdown")
            return

        try:
            goal = await api_client.post("/api/goals", {
                "user_id": user_id,
                "name": name,
                "target": target,
                "deadline": deadline,
            })
        except Exception:
            await update.message.reply_text("⚠️ Something went wrong, try again.")
            return

        await update.message.reply_text(
            f"✅ Goal created: {goal['name']}\nTarget: ₽{float(goal['target']):,.0f}"
            + (f"\nDeadline: {goal['deadline']}" if goal.get('deadline') else "")
        )

    elif sub == "add":
        if len(args) < 2:
            await update.message.reply_text("Usage: `/goal add <amount>`", parse_mode="Markdown")
            return

        try:
            amount = float(args[1].replace(",", "."))
        except ValueError:
            await update.message.reply_text("Invalid amount.")
            return

        try:
            goals = await api_client.get("/api/goals", {"user_id": user_id})
        except Exception:
            await update.message.reply_text("⚠️ Something went wrong, try again.")
            return

        if not goals:
            await update.message.reply_text("No goals yet. Create one with `/goal new ...`", parse_mode="Markdown")
            return

        if len(goals) == 1:
            await _do_deposit(update, goals[0], amount)
        else:
            # Show inline keyboard to pick a goal
            context.user_data["deposit_amount"] = amount
            buttons = [
                [InlineKeyboardButton(f"🎯 {g['name']} (₽{float(g['saved']):,.0f}/₽{float(g['target']):,.0f})", callback_data=f"goal_deposit_{g['id']}")]
                for g in goals
            ]
            await update.message.reply_text(
                f"Which goal to add ₽{amount:,.0f} to?",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
    else:
        await update.message.reply_text(
            "Usage:\n"
            "  `/goal` — show all goals\n"
            "  `/goal new <name> <amount> [YYYY-MM-DD]`\n"
            "  `/goal add <amount>`",
            parse_mode="Markdown",
        )


async def _do_deposit(update_or_query, goal: dict, amount: float):
    try:
        updated = await api_client.put(f"/api/goals/{goal['id']}/deposit", {"amount": amount})
        saved = float(updated["saved"])
        target = float(updated["target"])
        pct = min(saved / target * 100, 100) if target > 0 else 0
        bar = progress_bar(pct)
        text = (
            f"✅ Added ₽{amount:,.0f} to {goal['name']}\n"
            f"Saved: ₽{saved:,.0f} / ₽{target:,.0f}  ({pct:.0f}%)\n"
            f"{bar}"
        )
    except Exception:
        text = "⚠️ Something went wrong, try again."

    if hasattr(update_or_query, "message"):
        await update_or_query.message.reply_text(text)
    else:
        await update_or_query.edit_message_text(text)


async def goal_deposit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    goal_id = int(query.data.replace("goal_deposit_", ""))
    amount = context.user_data.pop("deposit_amount", 0)

    user = update.effective_user
    try:
        goals = await api_client.get("/api/goals", {
            "user_id": (await api_client.post("/api/users", {
                "telegram_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
            }))["id"]
        })
        goal = next((g for g in goals if g["id"] == goal_id), None)
        if goal:
            await _do_deposit(query, goal, amount)
        else:
            await query.edit_message_text("Goal not found.")
    except Exception:
        await query.edit_message_text("⚠️ Something went wrong, try again.")


def build_goal_deposit_handler() -> CallbackQueryHandler:
    return CallbackQueryHandler(goal_deposit_callback, pattern=r"^goal_deposit_\d+$")
