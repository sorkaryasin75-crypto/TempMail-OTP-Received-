import os
import requests
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ⚠️ নিশ্চিত করুন এটি আপনার কাঙ্ক্ষিত বটেরই আসল টোকেন
BOT_TOKEN = "8701243158:AAGoQbU4wGB0R3mpYfY3pdBufYUdXiMqW18".strip()

bot = telebot.TeleBot(BOT_TOKEN)

user_emails = {}

# 1secmail API Functions
def generate_temp_email():
    url = "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1"
    res = requests.get(url).json()
    return res[0]

def check_inbox(email):
    username, domain = email.split('@')
    url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={username}&domain={domain}"
    return requests.get(url).json()

def fetch_message(email, msg_id):
    username, domain = email.split('@')
    url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={username}&domain={domain}&id={msg_id}"
    return requests.get(url).json()

# Inline Menu Generator
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

# Commands
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    chat_id = message.chat.id
    has_email = chat_id in user_emails
    bot.send_message(
        chat_id,
        "<b>📬 Temp Mail Bot UI</b>\n\nনিচের বাটনগুলো ব্যবহার করে ইমেইল জেনারেট করুন:",
        parse_mode="HTML",
        reply_markup=get_main_menu(has_email)
    )

# Callback Handler
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    
    if call.data == "gen_email":
        email = generate_temp_email()
        user_emails[chat_id] = email
        
        text = (
            f"✅ <b>নতুন ইমেইল তৈরি হয়েছে!</b>\n\n"
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
        email = user_emails.get(chat_id)
        if not email:
            bot.answer_callback_query(call.id, "❌ আপনার কোনো সক্রিয় ইমেইল নেই!", show_alert=True)
            return

        messages = check_inbox(email)
        if not messages:
            bot.answer_callback_query(call.id, "📭 ইনবক্স এখনো খালি!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"📩 {len(messages)} টি ইমেইল পাওয়া গেছে!")
            for msg in messages:
                msg_data = fetch_message(email, msg['id'])
                mail_text = (
                    f"📩 <b>নতুন ইমেইল!</b>\n\n"
                    f"👤 <b>From:</b> {msg_data.get('from')}\n"
                    f"📌 <b>Subject:</b> {msg_data.get('subject')}\n"
                    f"-----------------------------\n"
                    f"{msg_data.get('textBody')}"
                )
                bot.send_message(chat_id, mail_text, parse_mode="HTML")

    elif call.data == "delete_email":
        if chat_id in user_emails:
            del user_emails[chat_id]
        bot.edit_message_text(
            "🗑️ ইমেইল মুছে ফেলা হয়েছে। নতুন ইমেইল তৈরি করতে নিচের বাটনে চাপ দিন:",
            chat_id,
            call.message.message_id,
            reply_markup=get_main_menu(False)
        )

# Bot Execution & Webhook Reset
if __name__ == "__main__":
    print("Clearing old webhooks and starting bot...")
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)
