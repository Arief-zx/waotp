import threading
import time
import requests
from bs4 import BeautifulSoup
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ====== KONFIGURASI ======
BOT_TOKEN = "8224787115:AAHDsKKdZmWTqUIMAeTbcM29g5SPeRNeOd0"
GROUP_ID = -1002825740190
CHANNEL_ID = -1002964625223
BASE_URL = "https://smsonline.cloud"

bot = Bot(token=BOT_TOKEN)

# Simpan state monitoring
user_country = {"default": "62"}  # default Indonesia

# ====== Ambil daftar negara ======
def get_countries():
    countries = {}
    try:
        resp = requests.get(BASE_URL, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("div.country a")
        for item in items:
            href = item.get("href", "")
            code = href.split("/")[-1]
            flag = item.find("span").text.strip() if item.find("span") else ""
            name = item.text.strip()
            countries[code] = f"{flag} {name}"
    except Exception as e:
        print(f"[ERROR get_countries] {e}")
    return countries

# ====== Ambil daftar nomor dari negara ======
def get_numbers(country_code="62"):
    url = f"{BASE_URL}/country/{country_code}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table tbody tr")
        numbers = []
        for row in rows:
            cols = row.find_all("td")
            if cols and len(cols) >= 2:
                nomor_text = cols[0].get_text(strip=True)
                link_tag = cols[-1].find("a")
                nomor_link = link_tag["href"] if link_tag else None
                numbers.append((nomor_text, nomor_link))
        return numbers
    except Exception as e:
        print(f"[ERROR get_numbers] {e}")
        return []

# ====== Ambil OTP terbaru dari nomor ======
def get_otp_for_number(number_url):
    try:
        resp = requests.get(BASE_URL + number_url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table tbody tr")
        messages = []
        for row in rows:
            cols = [c.get_text(strip=True) for c in row.find_all("td")]
            if cols and "WhatsApp" in cols[1]:
                messages.append((cols[0], cols[1]))  # waktu, pesan
        return messages
    except Exception as e:
        print(f"[ERROR get_otp_for_number] {e}")
    return []

# ====== Fungsi kirim ke channel ======
def send_to_channel(message: str):
    try:
        bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        print(f"Gagal kirim ke channel: {e}")

# ====== Loop pengecekan ======
def check_loop():
    posted_numbers = set()
    last_otp = {}
    while True:
        country_code = user_country.get("default", "62")
        countries = get_countries()
        country_name = countries.get(country_code, f"Negara {country_code}")

        numbers = get_numbers(country_code)
        for nomor_text, nomor_link in numbers:
            if not nomor_link:
                continue

            # jika nomor baru
            if nomor_text not in posted_numbers:
                msg = (
                    f"📢 *Nomor Baru Terdeteksi*\n\n"
                    f"🌍 Negara: {country_name}\n"
                    f"📱 Nomor: `{nomor_text}`\n\n"
                    f"⚡ Powered by @zxiety"
                )
                bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")
                send_to_channel(msg)
                posted_numbers.add(nomor_text)

            # cek OTP terbaru
            otps = get_otp_for_number(nomor_link)
            if otps:
                waktu, pesan = otps[0]
                if nomor_text not in last_otp or last_otp[nomor_text] != pesan:
                    otp_msg = (
                        f"🔐 *WhatsApp OTP Baru*\n\n"
                        f"📱 Nomor: `{nomor_text}`\n"
                        f"✉️ Pesan: {pesan}\n"
                        f"⏰ {waktu}\n\n"
                        f"⚡ Powered by @zxiety"
                    )
                    bot.send_message(chat_id=GROUP_ID, text=otp_msg, parse_mode="Markdown")
                    send_to_channel(otp_msg)
                    last_otp[nomor_text] = pesan
        time.sleep(60)

# ====== Command Start ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🌍 Ganti Negara", callback_data="change_country")],
        [InlineKeyboardButton("🔄 Refresh Nomor", callback_data="refresh")],
    ]
    await update.message.reply_text(
        "👋 Selamat datang di *WhatsApp OTP Bot!*\n\n"
        "Pilih aksi di bawah:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )

# ====== Tombol Callback ======
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "change_country":
        countries = get_countries()
        keyboard = [
            [InlineKeyboardButton(v, callback_data=f"set_country:{k}")]
            for k, v in list(countries.items())[:20]
        ]
        await query.edit_message_text("🌍 Pilih negara:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("set_country:"):
        code = query.data.split(":")[1]
        user_country["default"] = code
        countries = get_countries()
        await query.edit_message_text(f"✅ Negara diubah ke {countries.get(code, code)}")

    elif query.data == "refresh":
        code = user_country.get("default", "62")
        numbers = get_numbers(code)
        if numbers:
            text = "\n".join([f"{n}" for n, _ in numbers[:10]])
        else:
            text = "⚠️ Tidak ada nomor ditemukan."
        await query.edit_message_text(text=text)

# ====== Main App ======
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))

    # jalankan loop di thread terpisah
    thread = threading.Thread(target=check_loop, daemon=True)
    thread.start()

    print("🚀 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
