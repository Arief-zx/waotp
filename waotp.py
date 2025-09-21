import os
import requests
import time
import threading
import random
from bs4 import BeautifulSoup
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get("TOKEN", "8224787115:AAHDsKKdZmWTqUIMAeTbcM29g5SPeRNeOd0")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID", "-1002825740190")
CHANNEL_CHAT_ID = os.environ.get("CHANNEL_CHAT_ID", "-1002964625223")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "5"))  # Real-time OTP WhatsApp, detik
SUMMARY_INTERVAL = int(os.environ.get("SUMMARY_INTERVAL", str(2 * 60 * 60)))  # Summary tiap 2 jam

GROUP_LINK = "https://t.me/riefzzallotp"
CHANNEL_LINK = "https://t.me/riefzallotp"

bot = Bot(token=TOKEN)
last_sms_id_per_number = {}
user_state = {}  # user_id: {"country": "", "number": ""}

def get_all_numbers():
    url = "https://www.smsonline.cloud/id"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="table")
    numbers = {}
    for row in table.find_all("tr")[1:]:
        cols = row.find_all("td")
        if len(cols) < 5:
            continue
        country = cols[2].text.strip()
        number = cols[1].text.strip()
        num_url = "https://www.smsonline.cloud" + cols[4].find("a")["href"]
        if country not in numbers:
            numbers[country] = []
        numbers[country].append((number, num_url))
    return numbers

def get_latest_sms_from_number(number_url):
    resp = requests.get(number_url)
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="table")
    if not table:
        return None
    rows = table.find_all("tr")[1:]  # skip header
    if not rows:
        return None
    first_row = rows[0].find_all("td")
    if len(first_row) < 4:
        return None
    sms_id = first_row[0].text.strip()
    sender = first_row[1].text.strip()
    msg = first_row[2].text.strip()
    date = first_row[3].text.strip()
    return {"id": sms_id, "sender": sender, "msg": msg, "date": date}

def format_otp_message(number, country, sms, number_url):
    msg = (
        f"<b>{country} - WhatsApp OTP Detected ✨</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 <b>Number:</b> <code>{number}</code>\n"
        f"🌍 <b>Country:</b> {country}\n"
        f"💬 <b>Service:</b> <code>{sms['sender']}</code>\n"
        f"✉️ <b>Message:</b>\n<pre>{sms['msg']}</pre>\n"
        f"🕒 <b>Time:</b> <code>{sms['date']}</code>\n"
        f"🔗 <a href='{number_url}'>Cek SMS di Web</a>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ Powered by Github: <a href='https://github.com/Arief-zx'>Arief-zx</a> | Telegram: <a href='https://t.me/zxiety'>@zxiety</a>"
    )
    return msg

def format_summary_message(numbers):
    msg = "<b>📋 Daftar Nomor Virtual Gratis (smsonline.cloud)</b>\n\n"
    for country, nums in numbers.items():
        msg += f"🌍 <b>{country}</b>:\n"
        for n, u in nums:
            msg += f"• <code>{n}</code> - <a href='{u}'>Cek SMS</a>\n"
        msg += "\n"
    msg += (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ Powered by Github: <a href='https://github.com/Arief-zx'>Arief-zx</a> | Telegram: <a href='https://t.me/zxiety'>@zxiety</a>"
    )
    return msg

def check_otp_loop():
    while True:
        numbers = get_all_numbers()
        for country, nums in numbers.items():
            for number, url in nums:
                try:
                    sms = get_latest_sms_from_number(url)
                    if (
                        sms
                        and sms["id"] != last_sms_id_per_number.get(number)
                        and "WhatsApp" in sms["sender"]
                    ):
                        msg = format_otp_message(number, country, sms, url)
                        try:
                            bot.send_message(chat_id=CHANNEL_CHAT_ID, text=msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                        except Exception as e:
                            print(f"Error send to channel: {e}")
                        last_sms_id_per_number[number] = sms["id"]
                except Exception as e:
                    print(f"Error processing number {number}: {e}")
        time.sleep(CHECK_INTERVAL)

def summary_scheduler():
    while True:
        try:
            numbers = get_all_numbers()
            msg = format_summary_message(numbers)
            for chat_id in [GROUP_CHAT_ID, CHANNEL_CHAT_ID]:
                try:
                    bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                except Exception as e:
                    print(f"Error sending summary to {chat_id}: {e}")
        except Exception as e:
            print(f"Error sending summary: {e}")
        time.sleep(SUMMARY_INTERVAL)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type in ["group", "supergroup", "channel"]:
        return  # abaikan jika /start di grup/channel
    keyboard = [
        [InlineKeyboardButton("🌍 Country", callback_data="country")],
        [InlineKeyboardButton("🔁 Change", callback_data="change")],
        [InlineKeyboardButton("📬 GetOTP", url=CHANNEL_LINK)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "Selamat datang di bot OTP!\n\n"
        f"🔗 <b>Join Group:</b> <a href='{GROUP_LINK}'>Klik di sini</a>\n"
        f"🔗 <b>Join Channel:</b> <a href='{CHANNEL_LINK}'>Klik di sini</a>\n\n"
        "Gunakan tombol di bawah untuk pilih negara, tukar nomor, atau cek OTP di channel kami."
    )
    await update.message.reply_text(
        text, reply_markup=reply_markup, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()
    numbers = get_all_numbers()

    if data == "country":
        countries = list(numbers.keys())
        keyboard = []
        for c in countries:
            keyboard.append([InlineKeyboardButton(c, callback_data=f"select_country|{c}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Pilih negara:", reply_markup=reply_markup)
    elif data.startswith("select_country|"):
        country = data.split("|")[1]
        user_state[user_id] = {"country": country, "number": ""}
        nomor = random.choice(numbers[country])
        user_state[user_id]["number"] = nomor[0]
        keyboard = [
            [InlineKeyboardButton("🔁 Change", callback_data="change")],
            [InlineKeyboardButton("📬 GetOTP", url=CHANNEL_LINK)],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"Nomor Acak dari {country}:\n\n<code>{nomor[0]}</code>\n\n"
            f"<a href='{nomor[1]}'>Cek SMS</a>",
            parse_mode=ParseMode.HTML, reply_markup=reply_markup
        )
    elif data == "change":
        if user_id not in user_state or "country" not in user_state[user_id]:
            await query.edit_message_text("Silakan pilih negara dulu dengan tombol Country.")
            return
        country = user_state[user_id]["country"]
        nomor = random.choice(numbers[country])
        user_state[user_id]["number"] = nomor[0]
        keyboard = [
            [InlineKeyboardButton("🔁 Change", callback_data="change")],
            [InlineKeyboardButton("📬 GetOTP", url=CHANNEL_LINK)],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"Nomor Acak dari {country}:\n\n<code>{nomor[0]}</code>\n\n"
            f"<a href='{nomor[1]}'>Cek SMS</a>",
            parse_mode=ParseMode.HTML, reply_markup=reply_markup
        )

def run_polling_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=check_otp_loop, daemon=True).start()
    threading.Thread(target=summary_scheduler, daemon=True).start()
    run_polling_bot()
