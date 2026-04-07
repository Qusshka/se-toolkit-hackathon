import re
from datetime import date
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from utils import api_client

# Conversation states
MENU, NEW_NAME, NEW_AMOUNT, NEW_DEADLINE, ADD_PICK_GOAL, ADD_AMOUNT = range(6)


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
        f"  {bar}",
    ]
    if goal.get("deadline"):
        deadline = date.fromisoformat(goal["deadline"])
        days_away = (deadline - today).days
        lines.append(f"  Deadline: {deadline.strftime('%b %d, %Y')}  ({days_away} days away)")
        remaining = target - saved
        if days_away > 0 and remaining > 0:
            lines.append(f"  Need: ₽{remaining / days_away:.0f}/day to hit target on time")
    return "\n".join(lines)


def _main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 My Goals", callback_data="goal_view")],
        [InlineKeyboardButton("➕ Add Savings", callback_data="goal_add")],
        [InlineKeyboardButton("🎯 New Goal", callback_data="goal_new")],
    ])


# ── Entry point ───────────────────────────────────────────────────────────────

async def goal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "What would you like to do?",
        reply_markup=_main_menu_keyboard(),
    )
    return MENU


# ── Menu callbacks ────────────────────────────────────────────────────────────

async def goal_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("What would you like to do?", reply_markup=_main_menu_keyboard())
    return MENU


async def goal_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    try:
        user_id = await _get_user_id(user)
        goals = await api_client.get("/api/goals", {"user_id": user_id})
    except Exception:
        await query.edit_message_text("⚠️ Something went wrong, try again.")
        return MENU

    if not goals:
        await query.edit_message_text(
            "No goals yet. Create one first.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎯 New Goal", callback_data="goal_new"),
            ]]),
        )
        return MENU

    today = date.today()
    text = "🎯 Savings Goals\n\n" + "\n\n".join(_format_goal(g, today) for g in goals)
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Back", callback_data="goal_menu"),
    ]]))
    return MENU


# ── New goal flow ─────────────────────────────────────────────────────────────

async def goal_new_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "What's the name of your goal?\n_(e.g. iPhone 16, Vacation, Car)_",
        parse_mode="Markdown",
    )
    return NEW_NAME


async def new_goal_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["goal_name"] = update.message.text.strip()
    await update.message.reply_text("What's the target amount? _(e.g. 80000)_", parse_mode="Markdown")
    return NEW_AMOUNT


async def new_goal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", ".")
    try:
        amount = float(text)
    except ValueError:
        await update.message.reply_text("Please enter a number, e.g. `80000`", parse_mode="Markdown")
        return NEW_AMOUNT

    context.user_data["goal_amount"] = amount
    await update.message.reply_text(
        "Set a deadline? Send a date _(YYYY-MM-DD)_ or tap skip.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⏭ Skip", callback_data="goal_no_deadline"),
        ]]),
    )
    return NEW_DEADLINE


async def new_goal_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        await update.message.reply_text(
            "Format must be YYYY-MM-DD, e.g. `2026-12-31`", parse_mode="Markdown"
        )
        return NEW_DEADLINE
    context.user_data["goal_deadline"] = text
    return await _save_new_goal(update, context)


async def new_goal_no_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["goal_deadline"] = None
    return await _save_new_goal(update, context)


async def _save_new_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    send = update.message.reply_text if update.message else update.callback_query.message.reply_text
    try:
        user_id = await _get_user_id(user)
        goal = await api_client.post("/api/goals", {
            "user_id": user_id,
            "name": context.user_data["goal_name"],
            "target": context.user_data["goal_amount"],
            "deadline": context.user_data.get("goal_deadline"),
        })
    except Exception:
        await send("⚠️ Something went wrong, try again.")
        context.user_data.clear()
        return MENU

    deadline_line = f"\nDeadline: {goal['deadline']}" if goal.get("deadline") else ""
    await send(
        f"✅ Goal created!\n\n"
        f"🎯 {goal['name']}\n"
        f"Target: ₽{float(goal['target']):,.0f}"
        f"{deadline_line}",
        parse_mode="Markdown",
        reply_markup=_main_menu_keyboard(),
    )
    context.user_data.clear()
    return MENU


# ── Add savings flow ──────────────────────────────────────────────────────────

async def goal_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    try:
        user_id = await _get_user_id(user)
        goals = await api_client.get("/api/goals", {"user_id": user_id})
    except Exception:
        await query.edit_message_text("⚠️ Something went wrong, try again.")
        return MENU

    if not goals:
        await query.edit_message_text(
            "No goals yet. Create one first.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎯 New Goal", callback_data="goal_new"),
            ]]),
        )
        return MENU

    if len(goals) == 1:
        context.user_data["deposit_goal_id"] = goals[0]["id"]
        context.user_data["deposit_goal_name"] = goals[0]["name"]
        await query.edit_message_text(
            f"How much are you adding to *{goals[0]['name']}*?",
            parse_mode="Markdown",
        )
        return ADD_AMOUNT

    buttons = [
        [InlineKeyboardButton(
            f"🎯 {g['name']} (₽{float(g['saved']):,.0f}/₽{float(g['target']):,.0f})",
            callback_data=f"goal_pick_{g['id']}_{g['name']}",
        )]
        for g in goals
    ]
    await query.edit_message_text("Which goal?", reply_markup=InlineKeyboardMarkup(buttons))
    return ADD_PICK_GOAL


async def goal_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_", 3)
    context.user_data["deposit_goal_id"] = int(parts[2])
    context.user_data["deposit_goal_name"] = parts[3] if len(parts) > 3 else "goal"
    await query.edit_message_text(
        f"How much are you adding to *{context.user_data['deposit_goal_name']}*?",
        parse_mode="Markdown",
    )
    return ADD_AMOUNT


async def add_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", ".")
    try:
        amount = float(text)
    except ValueError:
        await update.message.reply_text("Please enter a number, e.g. `5000`", parse_mode="Markdown")
        return ADD_AMOUNT

    goal_id = context.user_data.get("deposit_goal_id")
    goal_name = context.user_data.get("deposit_goal_name", "goal")

    try:
        updated = await api_client.put(f"/api/goals/{goal_id}/deposit", {"amount": amount})
        saved = float(updated["saved"])
        target = float(updated["target"])
        pct = min(saved / target * 100, 100) if target > 0 else 0
        bar = progress_bar(pct)
        await update.message.reply_text(
            f"✅ Added ₽{amount:,.0f} to *{goal_name}*\n\n"
            f"Saved: ₽{saved:,.0f} / ₽{target:,.0f}  ({pct:.0f}%)\n"
            f"{bar}",
            parse_mode="Markdown",
            reply_markup=_main_menu_keyboard(),
        )
    except Exception:
        await update.message.reply_text("⚠️ Something went wrong, try again.")

    context.user_data.clear()
    return MENU


# ── Cancel ────────────────────────────────────────────────────────────────────

async def goal_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cancelled.", reply_markup=_main_menu_keyboard())
    return ConversationHandler.END


# ── Build handler ─────────────────────────────────────────────────────────────

def build_goal_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("goal", goal_command)],
        states={
            MENU: [
                CallbackQueryHandler(goal_view_callback, pattern="^goal_view$"),
                CallbackQueryHandler(goal_new_callback, pattern="^goal_new$"),
                CallbackQueryHandler(goal_add_callback, pattern="^goal_add$"),
                CallbackQueryHandler(goal_menu_callback, pattern="^goal_menu$"),
            ],
            NEW_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_goal_name)],
            NEW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_goal_amount)],
            NEW_DEADLINE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, new_goal_deadline),
                CallbackQueryHandler(new_goal_no_deadline, pattern="^goal_no_deadline$"),
            ],
            ADD_PICK_GOAL: [
                CallbackQueryHandler(goal_pick_callback, pattern=r"^goal_pick_\d+_.+$"),
            ],
            ADD_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_amount_received)],
        },
        fallbacks=[CommandHandler("cancel", goal_cancel)],
        per_message=False,
    )
