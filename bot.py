import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

# ==================== SOZLAMALAR ====================
BOT_TOKEN = "8661534101:AAGGztz3zxYzN3a1qQ9LF3ETPZzave5caMM"  # BotFather bergan token
ADMIN_GROUP_ID = -1003604182355  # Guruh ID si (chiziqchasi bilan)
# ====================================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- MA'LUMOTLAR BAZASI ---
def init_db():
    conn = sqlite3.connect("applications.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            full_name TEXT,
            phone TEXT,
            lang TEXT,
            level TEXT,
            idea_type TEXT,
            idea_content TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- FSM (BOSQICHLAR) ---
class Form(StatesGroup):
    full_name = State()
    phone = State()
    lang = State()
    level = State()
    idea = State()

class AdminForm(StatesGroup):
    reject_reason = State()
    accept_details = State()

# --- HANDLERLAR: FOYDALANUVCHI QISMI ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Assalomu alaykum! Young Innovators Competition botiga xush kelibsiz.\n\nIltimos, ism va familiyangizni kiriting:")
    await state.set_state(Form.full_name)

@dp.message(Form.full_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Telefon raqamingizni yuboring (tugmani bosing yoki yozing):", reply_markup=kb)
    await state.set_state(Form.phone)

@dp.message(Form.phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text
    await state.update_data(phone=phone)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="O'zbekcha", callback_data="lang_uz")],
        [InlineKeyboardButton(text="English", callback_data="lang_en")]
    ])
    await message.answer("Tanlov tilini tanlang:", reply_markup=ReplyKeyboardRemove())
    await message.answer("Til:", reply_markup=kb)
    await state.set_state(Form.lang)

@dp.callback_query(Form.lang, F.data.startswith("lang_"))
async def process_lang(callback: types.CallbackQuery, state: FSMContext):
    lang = "O'zbekcha" if callback.data == "lang_uz" else "English"
    await state.update_data(lang=lang)
    await callback.answer()
    
    if lang == "English":
        await callback.message.answer("Please enter your English proficiency level (e.g., IELTS 6.5, CEFR B2):")
        await state.set_state(Form.level)
    else:
        await state.update_data(level="N/A")
        await callback.message.answer("Loyiha g'oyangizni matn ko'rinishida yozing yoki fayl (PDF/PPTX) shaklida yuboring:")
        await state.set_state(Form.idea)

@dp.message(Form.level)
async def process_level(message: types.Message, state: FSMContext):
    await state.update_data(level=message.text)
    await message.answer("Submit your project idea as text or attach a file (PDF/PPTX):")
    await state.set_state(Form.idea)

@dp.message(Form.idea)
async def process_idea(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    if message.document:
        idea_type = "file"
        idea_content = message.document.file_id
    else:
        idea_type = "text"
        idea_content = message.text

    # Bazaga saqlash
    conn = sqlite3.connect("applications.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO applications (user_id, full_name, phone, lang, level, idea_type, idea_content) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (message.from_user.id, data['full_name'], data['phone'], data['lang'], data['level'], idea_type, idea_content)
    )
    app_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Admin guruhiga yuborish
    admin_text = (
        f"📥 **Yangi ariza #{app_id}**\n\n"
        f"👤 **Ism:** {data['full_name']}\n"
        f"📞 **Tel:** {data['phone']}\n"
        f"🌐 **Til:** {data['lang']}\n"
        f"📊 **Daraja:** {data['level']}\n"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"accept_{app_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{app_id}")
        ]
    ])

    if idea_type == "text":
        admin_text += f"💡 **G'oya:** {idea_content}"
        await bot.send_message(chat_id=ADMIN_GROUP_ID, text=admin_text, reply_markup=kb, parse_mode="Markdown")
    else:
        await bot.send_document(chat_id=ADMIN_GROUP_ID, document=idea_content, caption=admin_text, reply_markup=kb, parse_mode="Markdown")

    await message.answer("Arizangiz qabul qilindi! Tez orada ko'rib chiqib javob beramiz.")
    await state.clear()

# --- HANDLERLAR: ADMIN QISMI ---
@dp.callback_query(F.data.startswith("accept_"))
async def handle_accept(callback: types.CallbackQuery, state: FSMContext):
    app_id = callback.data.split("_")[1]
    await state.update_data(target_app_id=app_id)
    await callback.message.reply(f"#{app_id} arizani qabul qilish uchun sana, lokatsiya va qoidalarni yozib yuboring:")
    await state.set_state(AdminForm.accept_details)
    await callback.answer()

@dp.message(AdminForm.accept_details)
async def process_accept_details(message: types.Message, state: FSMContext):
    data = await state.get_data()
    app_id = data['target_app_id']
    
    conn = sqlite3.connect("applications.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM applications WHERE id = ?", (app_id,))
    row = cursor.fetchone()
    
    if row:
        user_id = row[0]
        cursor.execute("UPDATE applications SET status = 'accepted' WHERE id = ?", (app_id,))
        conn.commit()
        
        await bot.send_message(
            chat_id=user_id,
            text=f"🎉 **Tabriklaymiz! Arizangiz qabul qilindi.**\n\n**Ma'lumotlar:**\n{message.text}"
        )
        await message.reply(f"#{app_id} foydalanuvchiga tasdiqlash xabari yuborildi.")
    conn.close()
    await state.clear()

@dp.callback_query(F.data.startswith("reject_"))
async def handle_reject(callback: types.CallbackQuery, state: FSMContext):
    app_id = callback.data.split("_")[1]
    await state.update_data(target_app_id=app_id)
    await callback.message.reply(f"#{app_id} arizani rad etish sababini yozib yuboring:")
    await state.set_state(AdminForm.reject_reason)
    await callback.answer()

@dp.message(AdminForm.reject_reason)
async def process_reject_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    app_id = data['target_app_id']
    
    conn = sqlite3.connect("applications.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM applications WHERE id = ?", (app_id,))
    row = cursor.fetchone()
    
    if row:
        user_id = row[0]
        cursor.execute("UPDATE applications SET status = 'rejected' WHERE id = ?", (app_id,))
        conn.commit()
        
        await bot.send_message(
            chat_id=user_id,
            text=f"Afsuski, arizangiz qabul qilinmadi.\n\n**Sababi:** {message.text}"
        )
        await message.reply(f"#{app_id} foydalanuvchiga rad etish sababi yuborildi.")
    conn.close()
    await state.clear()

# STATISTIKA BUYRUG'I
@dp.message(Command("stat"))
async def cmd_stat(message: types.Message):
    if message.chat.id == ADMIN_GROUP_ID:
        conn = sqlite3.connect("applications.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM applications")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM applications WHERE status = 'accepted'")
        accepted = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM applications WHERE status = 'rejected'")
        rejected = cursor.fetchone()[0]
        
        conn.close()
        
        await message.answer(
            f"📊 **Statistika:**\n\n"
            f"👥 Jami arizalar: {total}\n"
            f"✅ Qabul qilinganlar: {accepted}\n"
            f"❌ Rad etilganlar: {rejected}\n"
            f"⏳ Kutilayotganlar: {total - accepted - rejected}"
        )


import os
import asyncio
from aiohttp import web

async def handle(request):
    return web.Response(text="Bot is active")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8080)))
    await site.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
