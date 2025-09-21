import threading
import time
import requests
from bs4 import BeautifulSoup
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# -----------------------------
# Konfigurasi Bot
# -----------------------------
BOT_TOKEN = "8224787115:AAHDsKKdZmWTqUIMAeTbcM29g5SPeRNeOd0"
GROUP_ID = -1002825740190
CHANNEL_ID = -1002964625223

BASE_URL = "https://smsonline.cloud"

# -----------------------------
# Scraper Functions
# -----------------------------
def get_countries():
    """Scrape daftar negara dari halaman utama"""
    countries = {}
    try:
        resp = requests.get(BASE_URL, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("div.country a")

        if not items:
            print("[WARNING get_countries] Tidak ada elemen div.country a ditemukan")
            return {}

        for item in items:
            href = item.get("href", "")
            code = href.split("/")[-1]
            flag = item.find("span").text.strip() if item.find("span") else ""
            name = item.text.strip()
            countries[code] = f"{flag} {name}"
    except Exception as e:
        print(f"[ERROR get_countries] {e}")
    return countries


def get_numbers(country_code="62"):
    """Ambil daftar nomor dari halaman negara tertentu"""
    url = f"{BASE_URL}/country/{country_code}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table tbody tr")

        if not rows:
            print(f"[WARNING get_numbers] Tidak ada baris tabel di {url}")
            return []

        numbers = []
        for row in rows:
            cols = [str(c) for c in row.find_all("td")]  # raw HTML cols
            if cols:
                numbers.append(cols)
        return numbers
    except Exception as e:
        print(f"[ERROR get_numbers] {e}")
        return []


def get_otp_for_number(number_url):
    """Ambil SMS terbaru dari nomor tertentu"""
    try:
        resp = requests.get(BASE_URL + number_url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table tbody tr")

        if not rows:
            print(f"[WARNING get_otp_for_number] Tidak ada SMS di {number_url}")
            return []

        messages = []
        for row in rows:
            cols = [c.text.strip() for c in row.find_all("td")]
            if cols and "WhatsApp" in cols[1]:
                messages.append(cols)
        return messages
    except Exception as e:
        print(f"[ERROR get_otp_for_number] {e}")
        return []

# -----------------------------
# Bot Handlers
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🌍 Change Country", callback_data="change_country")],
        [InlineKeyboardButton("🔄 Change Number", callback_data="change_number")],
        [InlineKeyboardButton("📩 Get OTP", url=f"https://t.me/c/{str(CHANNEL_ID)[4:]}")],
    ]
    await update.message.reply_text(
        "👋 Selamat datang di *WhatsApp OTP Bot!*\n\n"
        "Gunakan tombol di bawah untuk navigasi.\n\n"
        "⚡ Powered by @zxiety",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "change_country":
        countries = get_countries()
        if not countries:
            await query.edit_message_text("❌ Tidak bisa ambil daftar negara.")
            return
        keyboard = [
            [InlineKeyboardButton(v, callback_data=f"set_country:{k}")]
            for k, v in list(countries.items())[:30]  # batasi 30 biar rapi
        ]
        await query.edit_message_text(
            "🌍 Pilih negara:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif query.data.startswith("set_country:"):
        country_code = query.data.split(":")[1]
        context.user_data["country"] = country_code
        countries = get_countries()
        await query.edit_message_text(
            f"✅ Negara diubah ke {countries.get(country_code, country_code)}"
        )

    elif query.data == "change_number":
        country_code = context.user_data.get("country", "62")
        numbers = get_numbers(country_code)
        if not numbers:
            await query.edit_message_text("❌ Tidak ada nomor ditemukan.")
            return
        import random

        nomor = random.choice(numbers)
        nomor_text = BeautifulSoup(nomor[0], "html.parser").text
        await query.edit_message_text(
            f"📱 Nomor terpilih: <b>{nomor_text}</b>\n"
            f"🌍 Negara: {get_countries().get(country_code, country_code)}\n\n"
            f"⚡ Powered by @zxiety",
            parse_mode=ParseMode.HTML,
        )

# -----------------------------
# Background Task
# -----------------------------
def check_sms_loop(app: Application):
    """Loop background untuk update OTP & daftar nomor"""
    prev_numbers = {}
    while True:
        try:
            countries = get_countries()
            for country_code, country_name in list(countries.items())[:5]:  # cek 5 negara dulu
                numbers = get_numbers(country_code)
                if not numbers:
                    continue

                # Kirim daftar nomor aktif ke group
                if prev_numbers.get(country_code) != numbers:
                    text = f"📢 *Daftar Nomor Aktif* {country_name}\n\n"
                    for n in numbers[:10]:
                        nomor_text = BeautifulSoup(n[0], "html.parser").text
                        status_text = BeautifulSoup(n[1], "html.parser").text
                        text += f"📱 {nomor_text} | {status_text}\n"
                    text += "\n⚡ Powered by @zxiety"
                    try:
                        app.bot.send_message(
                            chat_id=GROUP_ID,
                            text=text,
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    except Exception as e:
                        print(f"[ERROR send group] {e}")
                    prev_numbers[country_code] = numbers

                # Kirim OTP WhatsApp terbaru ke channel
                for n in numbers[:5]:
                    link_tag = BeautifulSoup(n[-1], "html.parser").find("a")
                    if not link_tag:
                        continue
                    sms = get_otp_for_number(link_tag["href"])
                    if sms:
                        nomor_text = BeautifulSoup(n[0], "html.parser").text
                        otp_text = (
                            f"🔐 *WhatsApp OTP*\n\n"
                            f"📱 Nomor: `{nomor_text}`\n"
                            f"✉️ Pesan: {sms[0][1]}\n"
                            f"⏰ Waktu: {sms[0][0]}\n\n"
                            f"⚡ Powered by @zxiety"
                        )
                        try:
                            app.bot.send_message(
                                chat_id=CHANNEL_ID,
                                text=otp_text,
                                parse_mode=ParseMode.MARKDOWN,
                            )
                        except Exception as e:
                            print(f"[ERROR send channel] {e}")
        except Exception as e:
            print(f"[ERROR loop] {e}")
        time.sleep(60)

# -----------------------------
# Main
# -----------------------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    threading.Thread(target=check_sms_loop, args=(app,), daemon=True).start()

    print("🚀 Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
