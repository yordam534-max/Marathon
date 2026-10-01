import asyncio
import logging
import os
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)

# --- SOZLAMALAR ---
TOKEN = "8160966086:AAHtslwDZd8zUjdhtjf7XCVYZEVSvUB4xxY"
CHANNELS = ["@myjourneySAT", "@unitopuz"]

# Yangi maxfiy guruh havolasi:
PRIVATE_CHANNEL_LINK = "https://t.me/+goYEx8iHpSRiYzZi"

PORT = int(os.environ.get("PORT", 8080))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- BAZA BILAN ISHLASH (SQLITE) ---
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            referrer_id INTEGER,
            points INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_user(user_id, referrer_id=None):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, referrer_id, points) VALUES (?, ?, 0)", (user_id, referrer_id))
    conn.commit()
    conn.close()

def add_point(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET points = points + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_top_users(limit=20):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, points FROM users ORDER BY points DESC LIMIT ?", (limit,))
    top = cursor.fetchall()
    conn.close()
    return top

# --- KANALGA A'ZOLIKNI TEKSHIRISH ---
async def check_subscriptions(user_id: int) -> bool:
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True

# --- TUGMALAR (KEYBOARDS) ---
def get_main_keyboard():
    kb = [
        [KeyboardButton(text="🔗 Taklif havolasi"), KeyboardButton(text="📊 Ballarim")],
        [KeyboardButton(text="🏆 Reyting (Top 20)"), KeyboardButton(text="🔒 Maxfiy kanal")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_sub_keyboard():
    inline_kb = [
        [InlineKeyboardButton(text="1-kanalga a'zo bo'lish", url="https://t.me/myjourneySAT")],
        [InlineKeyboardButton(text="2-kanalga a'zo bo'lish", url="https://t.me/unitopuz")],
        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

# --- BUYRUKLAR VA TUGMALAR ISHLOVCHISI ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    if not get_user(user_id):
        add_user(user_id, referrer_id)

    if not await check_subscriptions(user_id):
        await message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:",
            reply_markup=get_sub_keyboard()
        )
        return

    await message.answer("Xush kelibsiz! Konkursda ishtirok etish uchun menyudan foydalaning.", reply_markup=get_main_keyboard())

@dp.callback_query(F.data == "check_sub")
async def process_check_sub(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if await check_subscriptions(user_id):
        user = get_user(user_id)
        if user and user[1]:  # referrer_id mavjud bo'lsa
            add_point(user[1])
            try:
                await bot.send_message(user[1], "🎉 Siz taklif qilgan foydalanuvchi kanallarga a'zo bo'ldi! +1 ball.")
            except Exception:
                pass
        await callback.message.delete()
        await callback.message.answer("A'zolik tasdiqlandi! Bosh menyu:", reply_markup=get_main_keyboard())
    else:
        await callback.answer("Siz hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)

@dp.message(F.text == "🔗 Taklif havolasi")
async def send_ref_link(message: types.Message):
    if not await check_subscriptions(message.from_user.id):
        await message.answer("Avval kanallarga a'zo bo'ling!", reply_markup=get_sub_keyboard())
        return
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
    await message.answer(f"Sizning taklif havolangiz:\n\n`{ref_link}`\n\nUshbu havolani do'stlaringizga yuboring va ball to'plang!", parse_mode="Markdown")

@dp.message(F.text == "📊 Ballarim")
async def show_points(message: types.Message):
    user = get_user(message.from_user.id)
    points = user[2] if user else 0
    await message.answer(f"Sizning joriy ballaringiz: **{points}** ball", parse_mode="Markdown")

@dp.message(F.text == "🏆 Reyting (Top 20)")
async def show_top(message: types.Message):
    top_users = get_top_users(20)
    text = "🏆 **Top-20 Ishtirokchilar:**\n\n"
    for idx, (u_id, pts) in enumerate(top_users, start=1):
        text += f"{idx}. ID: `{u_id}` — {pts} ball\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🔒 Maxfiy kanal")
async def secret_channel(message: types.Message):
    user = get_user(message.from_user.id)
    points = user[2] if user else 0
    if points >= 3:
        await message.answer(f"Siz 3 yoki undan ko'p ball to'pladingiz!\nMaxfiy kanal havolasi: {PRIVATE_CHANNEL_LINK}")
    else:
        await message.answer(f"Maxfiy kanalga kirish uchun kamida 3 ball kerak. Sizda hozir: {points} ball.")

# --- BOSHQA BARCHA XABARLAR UCHUN JAVOB ---
@dp.message()
async def default_handler(message: types.Message):
    if not await check_subscriptions(message.from_user.id):
        await message.answer("Botdan foydalanish uchun kanallarga a'zo bo'ling:", reply_markup=get_sub_keyboard())
    else:
        await message.answer("Iltimos, menyudagi tugmalardan birini tanlang yoki /start buyrug'ini yuboring.", reply_markup=get_main_keyboard())

# --- RENDER PORT XATOSINI OLDI OLUVCHI VEB-SERVER ---
async def handle_ping(request):
    return web.Response(text="Bot runs smoothly!")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
