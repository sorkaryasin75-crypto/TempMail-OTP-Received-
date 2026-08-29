import os
import re
import time
import requests
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ⚠️ আপনার টেলিগ্রাম বট টোকেন দিন (BotFather থেকে প্রাপ্ত)
BOT_TOKEN = "8701243158:AAGoQbU4wGB0R3mpYfY3pdBufYUdXiMqW18".strip()

bot = telebot.TeleBot(BOT_TOKEN)

# ইউজার তথ্য সংরক্ষণের জন্য ডিকশনারি
user_sessions = {}

# ফ্রি পাবলিক SMS API Endpoint (Free Virtual Numbers)
FREE_SMS_API = "https://raw.githubusercontent.com/httpJibon/Free-SMS-API/main/api.json"

# ----------------- Helper Functions ----------------- #

def get_free_numbers():
    """পাবলিক ফ্রি ভার্চুয়াল নম্বরগুলোর তালিকা আনে"""
    try:
        # বিকল্প ব্যাকআপ ফ্রি এপিআই রিসোর্স
        res = requests.get("https://receive-sms-free.cc/api/v1/numbers", timeout=10)
        if res.status_code == 200:
            data = res.json()
            return data.get("numbers", [])
    except Exception:
        pass
    
    # ফলব্যাক ফিক্সড ফ্রি নম্বর লিস্ট (টেস্টিং এর জন্য)
    return [
        {"country": "🇺🇸 USA", "number": "+12025550143", "id": "us_1"},
        {"country": "🇬🇧 UK", "number": "+447700900077", "id": "uk_1"},
        {"country": "🇸🇪 Sweden", "number": "+46701234567", "id": "se_1"}
    ]

def get_latest_otp(phone_number):
    """উক্ত নম্বরে আসা সাম্প্রতিক ওটিপি মেসেজ ফিল্টার করে আনে"""
    try:
        # ফ্রি সার্ভিস ব্যাকএন্ডে রিকোয়েস্ট
        url = f"https://receive-sms-free.cc/api/v1/messages?number={phone_number}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            messages = res.json().get("messages", [])
            if messages:
                latest_msg = messages[0].get("text", "")
                # ৪ থেকে ৮ ডিজিটের OTP Regex দিয়ে খোঁজা
                otp_match = re.search(r'\b\d{4,8}\b', latest_msg)
                if otp_match:
                    return otp_match.group(0), latest_msg
                return None, latest_msg
    except Exception as e:
        print(f"Error fetching SMS: {e}")
    
    return None, None

# ----------------- UI Keyboards ----------------- #

def get_main_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📱 ফ্রি ভার্চুয়াল নম্বর নিন (Get Number)", callback_data="list_numbers")
    )
    return markup

def get_number_menu(numbers):
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = []
    for item in numbers[:6]: # প্রথম ৬টি নম্বর দেখানো হবে
        btn_text = f"{item['country']} {item['number']}"
        buttons.append(InlineKeyboardButton(btn_text, callback_data=f"select_{item['number']}"))
    markup.add(*buttons)
    markup.add(InlineKeyboardButton("🔙 প্রধান মেনু", callback_data="main_menu"))
    return markup

def get_active_number_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔄 Refresh OTP", callback_data="check_otp"),
        InlineKeyboardButton("❌ নম্বর পরিবর্তন করুন", callback_data="list_numbers")
    )
    return markup

# ----------------- Bot Handlers ----------------- #

@bot.message_handler(commands=['start', 'help'])
def start_command(message):
    chat_id = message.chat.id
    bot.send_message(
        chat_id,
        "<b>🌐 Free Virtual Number & OTP Bot</b>\n\n"
        "সম্পূর্ণ ফ্রিতে সোশ্যাল মিডিয়া ও অ্যাপ ভেরিফিকেশনের জন্য ভার্চুয়াল নম্বর নিতে নিচের বাটনে চাপ দিন:",
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id

    try:
        if call.data == "main_menu":
            bot.edit_message_text(
                "<b>🌐 Free Virtual Number & OTP Bot</b>\n\nনিচের বাটন থেকে সেবা বেছে নিন:",
                chat_id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=get_main_menu()
            )

        elif call.data == "list_numbers":
            bot.answer_callback_query(call.id, "Loading numbers...⏳")
            numbers = get_free_numbers()
            bot.edit_message_text(
                "📋 <b>উপলব্ধ ফ্রি ভার্চুয়াল নম্বরসমূহ:</b>\n\nযেকোনো একটি নম্বরের ওপর ক্লিক করে নির্বাচন করুন:",
                chat_id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=get_number_menu(numbers)
            )

        elif call.data.startswith("select_"):
            selected_num = call.data.split("_")[1]
            user_sessions[chat_id] = {"number": selected_num}

            bot.answer_callback_query(call.id, "Number Selected! Selected ✅")
            
            text = (
                f"✅ <b>আপনার নির্বাচিত ফ্রি নম্বর:</b>\n\n"
                f"📱 <b>Number:</b> <code>{selected_num}</code>\n\n"
                f"<i>👆 নম্বরটিতে চাপ দিলে কপি হয়ে যাবে। কাঙ্ক্ষিত অ্যাপে নম্বরটি বসিয়ে OTP পাঠান, তারপর নিচে 'Refresh OTP' বাটনে ক্লিক করুন।</i>"
            )
            
            bot.edit_message_text(
                text,
                chat_id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=get_active_number_menu()
            )

        elif call.data == "check_otp":
            session = user_sessions.get(chat_id)
            if not session or "number" not in session:
                bot.answer_callback_query(call.id, "❌ কোনো নম্বর সিলেক্ট করা নেই!", show_alert=True)
                return

            bot.answer_callback_query(call.id, "Checking Inbox...🔄")
            number = session["number"]
            otp, full_msg = get_latest_otp(number)

            if otp:
                msg_text = (
                    f"🔑 <b>Your OTP Code:</b>\n\n"
                    f"<code>{otp}</code>\n\n"
                    f"👆 <i>কপি করতে ওটিপির ওপর চাপ দিন।</i>\n\n"
                    f"📄 <b>Full Message:</b> {full_msg}"
                )
                bot.send_message(chat_id, msg_text, parse_mode="HTML")
            else:
                bot.send_message(
                    chat_id, 
                    "📭 এখনো নতুন কোনো ওটিপি পাওয়া যায়নি।\n\n"
                    "<i>কোড পাঠানোর পর ১০-১৫ সেকেন্ড অপেক্ষা করে আবার 'Refresh OTP' চাপুন।</i>",
                    parse_mode="HTML"
                )

    except Exception as e:
        bot.answer_callback_query(call.id, "❌ সমস্যা হয়েছে!")
        bot.send_message(chat_id, f"⚠️ Error: {str(e)}")

# ----------------- Start Bot ----------------- #

if __name__ == "__main__":
    bot.remove_webhook()
    print("Bot is working successfully...")
    bot.infinity_polling(skip_pending=True)
