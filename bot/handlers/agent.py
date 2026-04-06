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

WAITING_FOR_QUESTION = 0

QUICK_OPTIONS = [
    "Where am I overspending?",
    "My coffee habit",
    "Upcoming subscriptions",
    "How to save money?",
]


async def _get_user_id(telegram_id: int, username: str, first_name: str) -> int:
    user = await api_client.post("/api/users", {
        "telegram_id": telegram_id,
        "username": username,
        "first_name": first_name,
    })
    return user["id"]


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        InlineKeyboardButton(opt, callback_data=f"ask_{i}")
        for i, opt in enumerate(QUICK_OPTIONS)
    ]
    keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    await update.message.reply_text(
        "What would you like to know about your spending?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return WAITING_FOR_QUESTION


async def quick_option_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.replace("ask_", ""))
    question = QUICK_OPTIONS[idx]
    await query.edit_message_text(f"You: {question}\n\nThinking... ⏳")

    user = update.effective_user
    try:
        user_id = await _get_user_id(user.id, user.username, user.first_name)
        result = await api_client.post("/api/agent/chat", {
            "user_id": user_id,
            "message": question,
            "context_days": 30,
        })
        reply = result["reply"]
    except Exception:
        reply = "⚠️ Something went wrong, try again."

    follow_up_buttons = [
        InlineKeyboardButton("Tell me more", callback_data="ask_0"),
        InlineKeyboardButton("Show subscriptions", callback_data="ask_2"),
        InlineKeyboardButton("Done ✅", callback_data="ask_done"),
    ]
    keyboard = [follow_up_buttons[:2], [follow_up_buttons[2]]]
    await query.edit_message_text(reply, reply_markup=InlineKeyboardMarkup(keyboard))
    return WAITING_FOR_QUESTION


async def done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(query.message.text + "\n\n✅ Done!")
    return ConversationHandler.END


async def free_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    question = update.message.text.strip()
    try:
        user_id = await _get_user_id(user.id, user.username, user.first_name)
        result = await api_client.post("/api/agent/chat", {
            "user_id": user_id,
            "message": question,
            "context_days": 30,
        })
        reply = result["reply"]
    except Exception:
        reply = "⚠️ Something went wrong, try again."

    follow_up_buttons = [
        InlineKeyboardButton("Ask another question", callback_data="ask_0"),
        InlineKeyboardButton("Done ✅", callback_data="ask_done"),
    ]
    await update.message.reply_text(
        reply,
        reply_markup=InlineKeyboardMarkup([follow_up_buttons]),
    )
    return WAITING_FOR_QUESTION


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


def build_agent_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("ask", ask_command)],
        states={
            WAITING_FOR_QUESTION: [
                CallbackQueryHandler(quick_option_callback, pattern=r"^ask_\d+$"),
                CallbackQueryHandler(done_callback, pattern=r"^ask_done$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, free_question),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )
