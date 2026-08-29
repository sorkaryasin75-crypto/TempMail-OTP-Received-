import os
import random
import string
import requests
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ⚠️ আপনার টেলিগ্রাম বট টোকেন দিন
BOT_TOKEN = "8701243158:AAGoQbU4wGB0R3mpYfY3pdBufYUdXiMqW18".strip()

bot = telebot.TeleBot(BOT_TOKEN)

# ইউজার সেশন ডাটা সংরক্ষণের স্থান
user_sessions = {}

BASE_URL = "https://api.mail.tm"

# ----------------- Mail.tm API Functions ----------------- #

def get_domain():
    res = requests.get(f"{BASE_URL}/domains", timeout=10)
    if res.status_code == 200:
        domains = res.json().get("hydra:member", [])
        if domains:
            return domains[0]['domain']
    raise Exception("ডোমেইন সংগ্রহ করতে সমস্যা হয়েছে।")

def create_mail_tm_account():
    domain = get_domain()
    # র্যান্ডম ইউজারনেম ও পাসওয়ার্ড জেনারেট
    rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    email = f"user_{rand_str}@{domain}"
    password = f"Pass_{rand_str}!"

    # অ্যাকাউন্ট রেজিস্টার
    acc_res = requests.post(
        f"{BASE_URL}/accounts",
        json={"address": email, "password": password},
        timeout=10
    )
    
    if acc_res.status_code not in [200, 201]:
        raise Exception(f"Account creation failed: {acc_res.status_code}")

    # অথেনটিকেশন টোকেন সংগ্রহ
    token_res = requests.post(
        f"{BASE_URL}/token",
        json={"address": email, "password": password},
        timeout=10
    )
    
    if token_res.status_code == 200:
        token = token_res.json().get("token")
        return email, token
    else:
        raise Exception("Token generation failed.")

def check_messages(token):
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(f"{BASE_URL}/messages", headers=headers, timeout=10)
    if res.status_code == 200:
        return res.json().get("hydra:member", [])
    return []

def get_message_detail(msg_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(f"{BASE_URL}/messages/{msg_id}", headers=headers, timeout=10)
    if res.status_code == 200:
        return res.json()
    return {}

# ----------------- UI & Inline Keyboards ----------------- #

def get_main_menu(email_exists=False):
    markup = InlineKeyboardMarkup(row_width=2)
    if not email_exists:
        markup.add(InlineKeyboardButton("🎲 Generate Email", callback_data="gen_email"))
    else:
        markup.add(
            InlineKeyboardButton("🔄 Refresh Inbox", callback_data="check_mail"),
            InlineKeyboardButton("🗑️ Delete Email", callback_data="delete_email")
        )
        markup.add(InlineKeyboardButton("🎲 Generate New Email", callback_data="gen_email"))
    return markup

# ----------------- Bot Message Handlers ----------------- #

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    chat_id = message.chat.id
    has_email = chat_id in user_sessions
    bot.send_message(
        chat_id,
        "<b>📬 Temp Mail Bot (Mail.tm Powered)</b>\n\nনিচের বাটন চেপে কার্যক্রম পরিচালনা করুন:",
        parse_mode="HTML",
        reply_markup=get_main_menu(has_email)
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    
    try:
        if call.data == "gen_email":
            bot.answer_callback_query(call.id, "Generating Email...⏳")
            
            email, token = create_mail_tm_account()
            user_sessions[chat_id] = {"email": email, "token": token}
            
            text = (
                f"✅ <b>আপনার Temp Mail তৈরি হয়েছে!</b>\n\n"
                f"<code>{email}</code>\n\n"
                f"<i>👆 ইমেইলের ওপর ক্লিক করলেই কপি হয়ে যাবে।</i>"
            )
            bot.edit_message_text(
                text, 
                chat_id, 
                call.message.message_id, 
                parse_mode="HTML", 
                reply_markup=get_main_menu(True)
            )
            
        elif call.data == "check_mail":
            bot.answer_callback_query(call.id, "Checking Inbox...🔄")
            session = user_sessions.get(chat_id)
            
            if not session:
                bot.send_message(chat_id, "❌ আপনার কোনো সক্রিয় ইমেইল নেই!")
                return

            messages = check_messages(session["token"])
            if not messages:
                bot.send_message(chat_id, "📭 ইনবক্স এখনো খালি!")
            else:
                bot.send_message(chat_id, f"📩 <b>{len(messages)} টি ইমেইল পাওয়া গেছে!</b>", parse_mode="HTML")
                for msg in messages:
                    detail = get_message_detail(msg['id'], session["token"])
                    
                    sender = detail.get('from', {}).get('address', 'Unknown')
                    subject = detail.get('subject', 'No Subject')
                    body = detail.get('text', detail.get('intro', 'No Body Text'))
                    
                    mail_text = (
                        f"📩 <b>নতুন ইমেইল!</b>\n\n"
                        f"👤 <b>From:</b> {sender}\n"
                        f"📌 <b>Subject:</b> {subject}\n"
                        f"-----------------------------\n"
                        f"{body}"
                    )
                    bot.send_message(chat_id, mail_text, parse_mode="HTML")

        elif call.data == "delete_email":
            bot.answer_callback_query(call.id, "Email Deleted 🗑️")
            if chat_id in user_sessions:
                del user_sessions[chat_id]
            bot.edit_message_text(
                "🗑️ ইমেইল মুছে ফেলা হয়েছে। নতুন ইমেইল তৈরি করতে নিচের বাটনে চাপ দিন:",
                chat_id,
                call.message.message_id,
                reply_markup=get_main_menu(False)
            )
            
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Error Occurred!")
        bot.send_message(chat_id, f"⚠️ <b>এরর:</b> {str(e)}", parse_mode="HTML")

# ----------------- Execution ----------------- #

if __name__ == "__main__":
    bot.remove_webhook()
    print("Bot is starting via Mail.tm API...")
    bot.infinity_polling(skip_pending=True)
