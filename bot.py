import os
import re
import asyncio
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configurations (Fallback to Env Variables or hardcoded as provided)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8701243158:AAGoQbU4wGB0R3mpYfY3pdBufYUdXiMqW18")
TMAILOR_API_KEY = os.getenv("TMAILOR_API_KEY", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJlIjoicHprS1pKNVhFVU1QcTFjZ0RLcTBBU3lESTNJaklVeXlHSGc0cXhXMkkzY25xMFMyREhxbm9SV0hGS3lucTBFZ0R5RVJvSDEzRktjbnEwdGtEeGNLcUhrZ3FRT1pFMXEySmFNS0JLQUlKd0lQSEt5ZyJ9.9zcrGKQM9SiTyaR-r_GjgsvCRA1xU5u429vcbUsPzyU")
INITIAL_ADMIN_ID = int(os.getenv("ADMIN_UID", "6582650458"))

# Dynamic Admin and User Storage (In-Memory)
admin_users = {INITIAL_ADMIN_ID}
allowed_users = {INITIAL_ADMIN_ID}  # By default admin is allowed
user_emails = {}  # {user_id: {"email": str, "token": str}}

# Helper Functions for Tmailor API
TMAILOR_BASE = "https://api.tmailor.com/v1"

def create_tmailor_email():
    headers = {"Authorization": f"Bearer {TMAILOR_API_KEY}"}
    try:
        res = requests.post(f"{TMAILOR_BASE}/emails", headers=headers, json={})
        if res.status_code == 200 or res.status_code == 201:
            data = res.json()
            return data.get("address"), data.get("token")
    except Exception as e:
        logger.error(f"Error creating email: {e}")
    return None, None

def get_tmailor_messages(email_token):
    headers = {"Authorization": f"Bearer {TMAILOR_API_KEY}"}
    try:
        res = requests.get(f"{TMAILOR_BASE}/messages?token={email_token}", headers=headers)
        if res.status_code == 200:
            return res.json().get("messages", [])
    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
    return []

def extract_otp(text):
    """Filter out 4 to 8 digit OTP/Code from body text."""
    if not text:
        return None
    match = re.search(r'\b\d{4,8}\b', text)
    return match.group(0) if match else None

# Inline Keyboards
def main_menu_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("📧 Generate Mail", callback_data="gen_mail")],
        [InlineKeyboardButton("📬 Check OTP", callback_data="check_otp")],
    ]
    if user_id in admin_users:
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def admin_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add User UID", callback_data="add_user")],
        [InlineKeyboardButton("➖ Remove User UID", callback_data="remove_user")],
        [InlineKeyboardButton("📋 Allowed Users List", callback_data="list_users")],
        [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

# Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in allowed_users:
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
    
    await update.message.reply_text(
        "👋 **Welcome to Temp Mail OTP Bot!**\n\nClick below to generate an email address or check received OTPs.",
        reply_markup=main_menu_keyboard(user_id),
        parse_mode="Markdown"
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in allowed_users:
        await query.edit_message_text("❌ You are not authorized.")
        return

    data = query.data

    if data == "main_menu":
        await query.edit_message_text(" Main Menu:", reply_markup=main_menu_keyboard(user_id))

    elif data == "gen_mail":
        await query.edit_message_text("⏳ Generating email, please wait...")
        email, token = create_tmailor_email()
        if email and token:
            user_emails[user_id] = {"email": email, "token": token}
            
            # Message with inline copy-able monospaced email
            msg_text = (
                f"✅ **Your Generated Email:**\n`{email}`\n\n"
                f"Tap on the text above to copy, or use the button below to easily copy and check for OTP."
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Copy Email", copy_text={"text": email})],
                [InlineKeyboardButton("🔄 Check OTP", callback_data="check_otp")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ])
            await query.edit_message_text(msg_text, reply_markup=kb, parse_mode="Markdown")
        else:
            await query.edit_message_text(
                "❌ Failed to generate email. Check API key or limit.",
                reply_markup=main_menu_keyboard(user_id)
            )

    elif data == "check_otp":
        if user_id not in user_emails:
            await query.edit_message_text("⚠️ No active email found. Generate one first!", reply_markup=main_menu_keyboard(user_id))
            return

        email = user_emails[user_id]["email"]
        token = user_emails[user_id]["token"]
        messages = get_tmailor_messages(token)

        if not messages:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh OTP", callback_data="check_otp")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ])
            await query.edit_message_text(f"📥 Checking inbox for `{email}`...\n\n❌ No OTP received yet.", reply_markup=kb, parse_mode="Markdown")
            return

        latest_msg = messages[0]
        msg_body = latest_msg.get("text") or latest_msg.get("html") or ""
        otp = extract_otp(msg_body)

        if otp:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Copy OTP", copy_text={"text": otp})],
                [InlineKeyboardButton("🔄 Refresh", callback_data="check_otp")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ])
            await query.edit_message_text(f"🔑 **OTP Received!**\n\nCode: `{otp}`", reply_markup=kb, parse_mode="Markdown")
        else:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data="check_otp")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ])
            await query.edit_message_text(f"📩 Mail received, but no OTP code detected in body.", reply_markup=kb)

    elif data == "admin_panel":
        if user_id not in admin_users:
            await query.edit_message_text("❌ Access Denied.")
            return
        await query.edit_message_text("⚙️ **Admin Control Panel**", reply_markup=admin_panel_keyboard(), parse_mode="Markdown")

    elif data == "add_user":
        context.user_data["action"] = "add_uid"
        await query.edit_message_text("Please send the Telegram **UID** you want to authorize:")

    elif data == "remove_user":
        context.user_data["action"] = "remove_uid"
        await query.edit_message_text("Please send the Telegram **UID** you want to revoke access from:")

    elif data == "list_users":
        uids_str = "\n".join([f"`{uid}`" for uid in allowed_users])
        await query.edit_message_text(f"👥 **Allowed UIDs:**\n{uids_str}", reply_markup=admin_panel_keyboard(), parse_mode="Markdown")

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admin_users:
        return

    action = context.user_data.get("action")
    text = update.message.text.strip()

    if action in ["add_uid", "remove_uid"]:
        if not text.isdigit():
            await update.message.reply_text("❌ Invalid Telegram UID. Must be numbers only.")
            return

        target_uid = int(text)
        if action == "add_uid":
            allowed_users.add(target_uid)
            await update.message.reply_text(f"✅ UID `{target_uid}` added successfully!", parse_mode="Markdown")
        elif action == "remove_uid":
            if target_uid in allowed_users and target_uid not in admin_users:
                allowed_users.remove(target_uid)
                await update.message.reply_text(f"🗑️ UID `{target_uid}` removed successfully!", parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ Cannot remove primary admin or unlisted UID.")

        context.user_data["action"] = None

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))

    logger.info("Bot started successfully.")
    app.run_polling()

if __name__ == "__main__":
    main()
