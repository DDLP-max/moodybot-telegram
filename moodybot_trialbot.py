# -*- coding: utf-8 -*-
import json
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from moodybot import generate_moody_reply
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# --- CONFIGURATION ---
TOKEN = os.getenv("TELEGRAM_TRIAL_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
TRIAL_LIMIT = 3
TRIAL_FILE = "trial_users.json"

# --- UTILITIES ---
def load_trials():
    if os.path.exists(TRIAL_FILE):
        with open(TRIAL_FILE, "r") as f:
            return json.load(f)
    return {}

def save_trials(data):
    with open(TRIAL_FILE, "w") as f:
        json.dump(data, f)

def moodybot_response(user_input: str) -> str:
    return generate_moody_reply(user_input)  # uses full MoodyBot engine

def upgrade_prompt() -> str:
    return (
        "🚫 Trial limit reached.\n\n"
        "You’ve had your 3 free confessions.\n"
        "This isn’t a chatbot. It’s a literary AI engine running on chaos and clarity.\n\n"
        "🔓 Upgrade to Premium:\n"
        "https://moodybot.gumroad.com/l/moodybotpremium\n\n"
        "Or keep spiraling in silence. Your call."
    )

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to MoodyBotTrial.\n"
        "You get 3 brutally honest replies. After that, it’s Premium or purgatory.\n\n"
        "Type your confession or question below."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    message_text = update.message.text.strip()
    trials = load_trials()

    if user_id not in trials:
        trials[user_id] = {"count": 0}

    if trials[user_id]["count"] >= TRIAL_LIMIT:
        await update.message.reply_text(upgrade_prompt())
        return

    reply = moodybot_response(message_text)
    trials[user_id]["count"] += 1
    save_trials(trials)

    await update.message.reply_text(f"🧠 MoodyBot says:\n{reply}")

def main():
    # Not the production poller. Render starts moodybot.py only (see render.yaml).
    # Never share TELEGRAM_BOT_TOKEN with the production worker.
    try:
        if not TOKEN:
            raise RuntimeError(
                "TELEGRAM_TRIAL_BOT_TOKEN or TELEGRAM_BOT_TOKEN is not set"
            )
        app = ApplicationBuilder().token(TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        print("MoodyBotTrial is live.")
        app.run_polling()

    except Exception as e:
        print(f"Trial bot crashed: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"MoodyBotTrialBot crashed: {e}")

