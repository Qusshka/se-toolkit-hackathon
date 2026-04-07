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

# States
ASK_CATEGORY_FIRST = 0
ASK_AMOUNT_AND_DESC = 1

RECURRING_KEYWORDS = {"monthly": 30, "weekly": 7, "yearly": 365, "every month": 30}


def parse_expense_message(text: str) -> dict | None:
    """Parse natural language expense. Handles both 'amount description' and 'description amount'."""
    raw = text.strip()

    # Extract and strip recurring keywords first
    is_recurring = False
    recur_days = None
    for kw, days in RECURRING_KEYWORDS.items():
        if kw in raw.lower():
            is_recurring = True
            recur_days = days
            raw = re.sub(re.escape(kw), "", raw, flags=re.IGNORECASE).strip()
            break

    # Pass 1: "spent/paid <amount> on/for <description>" or "<amount> <description>"
    m = re.match(r"^(?:spent|paid)?\s*(\d+(?:[.,]\d{1,2})?)\s*(?:on|for)?\s*(.+)", raw, re.IGNORECASE)
    if m:
        amount = float(m.group(1).replace(",", "."))
        description = m.group(2).strip()
        if description:
            return {"amount": amount, "description": description,
                    "is_recurring": is_recurring, "recur_days": recur_days}

    # Pass 2: "<description> <amount>" — e.g. "coffee 350"
    m = re.match(r"^(.+?)\s+(\d+(?:[.,]\d{1,2})?)$", raw, re.IGNORECASE)
    if m:
        description = m.group(1).strip()
        amount = float(m.group(2).replace(",", "."))
        if description:
            return {"amount": amount, "description": description,
                    "is_recurring": is_recurring, "recur_days": recur_days}

    return None


def _parse_amount_and_desc(text: str) -> tuple[float, str] | None:
    """Parse 'amount description' or 'description amount' from guided /add step."""
    raw = text.strip()
    m = re.match(r"^(\d+(?:[.,]\d{1,2})?)\s+(.+)", raw)
    if m:
        return float(m.group(1).replace(",", ".")), m.group(2).strip()
    m = re.match(r"^(.+?)\s+(\d+(?:[.,]\d{1,2})?)$", raw)
    if m:
        return float(m.group(2).replace(",", ".")), m.group(1).strip()
    return None


async def _try_ai_classify(description: str, categories: list) -> dict | None:
    """Try to auto-classify description via AI. Returns category dict or None."""
    try:
        result = await api_client.post("/api/agent/classify", {"description": description})
        cat_name = (result.get("category") or "").strip()
        if cat_name:
            for c in categories:
                if c["name"].lower() == cat_name.lower():
                    return c
    except Exception:
        pass
    return None


async def _show_category_keyboard(message, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fetch categories and show inline keyboard. Returns next state."""
    try:
        categories = await api_client.get("/api/categories")
    except Exception:
        await message.reply_text("⚠️ Something went wrong, try again.")
        return ConversationHandler.END

    context.user_data["categories"] = {str(c["id"]): c for c in categories}
    buttons = [
        InlineKeyboardButton(f"{c['icon'] or ''} {c['name']}", callback_data=f"cat_{c['id']}")
        for c in categories
    ]
    keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    await message.reply_text("Select a category:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ASK_CATEGORY_FIRST


async def _save_expense_from_message(message, context: ContextTypes.DEFAULT_TYPE, cat: dict) -> None:
    """Save expense directly (AI-classified path) — replies to a plain message."""
    user = message.from_user
    try:
        db_user = await api_client.post("/api/users", {
            "telegram_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
        })
        user_id = db_user["id"]
    except Exception:
        await message.reply_text("⚠️ Something went wrong, try again.")
        return

    amount = context.user_data["amount"]
    description = context.user_data["description"]
    is_recurring = context.user_data.get("is_recurring", False)
    recur_days = context.user_data.get("recur_days")
    cat_id = cat["id"]
    icon = cat.get("icon", "")
    cat_name = cat["name"]

    try:
        await api_client.post("/api/expenses", {
            "user_id": user_id,
            "amount": amount,
            "description": description,
            "category_id": cat_id,
            "is_recurring": is_recurring,
            "recur_days": recur_days,
        })
    except Exception:
        await message.reply_text("⚠️ Something went wrong, try again.")
        return

    recurring_note = f"\n🔁 Recurring every {recur_days} days" if is_recurring else ""

    try:
        today = date.today()
        month_start = today.replace(day=1)
        cat_stats = await api_client.get("/api/stats/by-category", {
            "user_id": user_id,
            "from": str(month_start),
            "to": str(today),
        })
        cat_total = next((c["total"] for c in cat_stats if c["category_name"] == cat_name), None)
        monthly_line = f"\nTotal on {cat_name.lower()} this month: ₽{cat_total:.0f}" if cat_total else ""
    except Exception:
        monthly_line = ""

    await message.reply_text(
        f"✅ Saved: {description} — ₽{amount:.0f}\n"
        f"Category: {icon} {cat_name} | Date: today"
        f"{recurring_note}"
        f"{monthly_line}"
    )
    context.user_data.clear()


async def _save_expense(query, context: ContextTypes.DEFAULT_TYPE, cat_id: int) -> None:
    """Save expense to backend and edit message with confirmation."""
    categories = context.user_data.get("categories", {})
    cat = categories.get(str(cat_id))
    cat_name = cat["name"] if cat else "Unknown"
    icon = cat["icon"] if cat else ""

    user = query.from_user
    try:
        db_user = await api_client.post("/api/users", {
            "telegram_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
        })
        user_id = db_user["id"]
    except Exception:
        await query.edit_message_text("⚠️ Something went wrong, try again.")
        return

    amount = context.user_data["amount"]
    description = context.user_data["description"]
    is_recurring = context.user_data.get("is_recurring", False)
    recur_days = context.user_data.get("recur_days")

    try:
        await api_client.post("/api/expenses", {
            "user_id": user_id,
            "amount": amount,
            "description": description,
            "category_id": cat_id,
            "is_recurring": is_recurring,
            "recur_days": recur_days,
        })
    except Exception:
        await query.edit_message_text("⚠️ Something went wrong, try again.")
        return

    recurring_note = f"\n🔁 Recurring every {recur_days} days" if is_recurring else ""

    try:
        today = date.today()
        month_start = today.replace(day=1)
        cat_stats = await api_client.get("/api/stats/by-category", {
            "user_id": user_id,
            "from": str(month_start),
            "to": str(today),
        })
        cat_total = next((c["total"] for c in cat_stats if c["category_name"] == cat_name), None)
        count_expenses = await api_client.get("/api/expenses", {
            "user_id": user_id,
            "from": str(month_start),
            "to": str(today),
            "category_id": cat_id,
        })
        count_this_month = len(count_expenses)
        monthly_line = (f"\nTotal on {cat_name.lower()} this month: "
                        f"₽{cat_total:.0f} ({count_this_month} purchases)") if cat_total else ""
    except Exception:
        monthly_line = ""

    await query.edit_message_text(
        f"✅ Saved: {description} — ₽{amount:.0f}\n"
        f"Category: {icon} {cat_name} | Date: today"
        f"{recurring_note}"
        f"{monthly_line}"
    )
    context.user_data.clear()


# ── /add flow ─────────────────────────────────────────────────────────────────

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry: /add — show category keyboard immediately."""
    context.user_data.clear()
    context.user_data["guided"] = True
    return await _show_category_keyboard(update.message, context)


async def category_first_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Category was tapped. If NL flow (amount already set) → save. If guided → ask amount+desc."""
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.replace("cat_", ""))
    context.user_data["pending_cat_id"] = cat_id

    if context.user_data.get("amount") is not None:
        # Natural language flow — already have amount + description
        await _save_expense(query, context, cat_id)
        return ConversationHandler.END
    else:
        # Guided /add flow — ask for amount and description together
        cat = context.user_data.get("categories", {}).get(str(cat_id), {})
        cat_name = cat.get("name", "")
        icon = cat.get("icon", "")
        await query.edit_message_text(
            f"Category: {icon} {cat_name}\n\nHow much and what for?\n"
            f"_(e.g. `350 oat latte` or `oat latte 350`)_",
            parse_mode="Markdown",
        )
        return ASK_AMOUNT_AND_DESC


async def amount_and_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guided flow: user typed amount + description in one message."""
    result = _parse_amount_and_desc(update.message.text)
    if not result:
        await update.message.reply_text(
            "Couldn't parse that. Try: `350 coffee` or `coffee 350`",
            parse_mode="Markdown",
        )
        return ASK_AMOUNT_AND_DESC

    amount, description = result

    # Check for recurring keywords
    is_recurring = False
    recur_days = None
    for kw, days in RECURRING_KEYWORDS.items():
        if kw in description.lower():
            is_recurring = True
            recur_days = days
            description = re.sub(re.escape(kw), "", description, flags=re.IGNORECASE).strip()
            break

    context.user_data["amount"] = amount
    context.user_data["description"] = description
    context.user_data["is_recurring"] = is_recurring
    context.user_data["recur_days"] = recur_days

    cat_id = context.user_data["pending_cat_id"]

    user = update.effective_user
    categories = context.user_data.get("categories", {})
    cat = categories.get(str(cat_id), {})
    cat_name = cat.get("name", "Unknown")
    icon = cat.get("icon", "")

    try:
        db_user = await api_client.post("/api/users", {
            "telegram_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
        })
        user_id = db_user["id"]
    except Exception:
        await update.message.reply_text("⚠️ Something went wrong, try again.")
        return ConversationHandler.END

    try:
        await api_client.post("/api/expenses", {
            "user_id": user_id,
            "amount": amount,
            "description": description,
            "category_id": cat_id,
            "is_recurring": is_recurring,
            "recur_days": recur_days,
        })
    except Exception:
        await update.message.reply_text("⚠️ Something went wrong, try again.")
        return ConversationHandler.END

    recurring_note = f"\n🔁 Recurring every {recur_days} days" if is_recurring else ""

    try:
        today = date.today()
        month_start = today.replace(day=1)
        cat_stats = await api_client.get("/api/stats/by-category", {
            "user_id": user_id,
            "from": str(month_start),
            "to": str(today),
        })
        cat_total = next((c["total"] for c in cat_stats if c["category_name"] == cat_name), None)
        monthly_line = f"\nTotal on {cat_name.lower()} this month: ₽{cat_total:.0f}" if cat_total else ""
    except Exception:
        monthly_line = ""

    await update.message.reply_text(
        f"✅ Saved: {description} — ₽{amount:.0f}\n"
        f"Category: {icon} {cat_name} | Date: today"
        f"{recurring_note}"
        f"{monthly_line}"
    )
    context.user_data.clear()
    return ConversationHandler.END


# ── Natural language entry ────────────────────────────────────────────────────

async def natural_language_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parsed = parse_expense_message(text)
    if not parsed:
        return ConversationHandler.END  # not an expense — don't enter conversation

    context.user_data["amount"] = parsed["amount"]
    context.user_data["description"] = parsed["description"]
    context.user_data["is_recurring"] = parsed["is_recurring"]
    context.user_data["recur_days"] = parsed["recur_days"]

    # Try AI auto-classification
    try:
        categories = await api_client.get("/api/categories")
        matched_cat = await _try_ai_classify(parsed["description"], categories)
        if matched_cat:
            context.user_data["categories"] = {str(c["id"]): c for c in categories}
            await _save_expense_from_message(update.message, context, matched_cat)
            return ConversationHandler.END
    except Exception:
        pass

    return await _show_category_keyboard(update.message, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


def build_expense_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("add", add_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, natural_language_expense),
        ],
        states={
            ASK_CATEGORY_FIRST: [
                CallbackQueryHandler(category_first_chosen, pattern=r"^cat_\d+$"),
            ],
            ASK_AMOUNT_AND_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, amount_and_desc),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )
