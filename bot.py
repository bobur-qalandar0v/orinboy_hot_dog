"""
O'rinboy Hotdog buyurtma boti (aiogram 3).
Mijoz /start bosganda ism, telefon va manzilni bir marta kiritadi (users.db ga saqlanadi).
Keyingi buyurtmalarda ma'lumot qayta so'ralmaydi.

Muhit o'zgaruvchilari: BOT_TOKEN, WEBAPP_URL, ADMIN_CHAT_ID
"""
import asyncio
import html
import json
import os
import re
import sqlite3
from urllib.parse import urlencode

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, Message, ReplyKeyboardMarkup,
                           ReplyKeyboardRemove, WebAppInfo)

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBAPP_URL = os.environ["WEBAPP_URL"]
ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"])
CARD_NUMBER = os.environ.get("CARD_NUMBER", "")
CARD_OWNER = os.environ.get("CARD_OWNER", "")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

db = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db"))
db.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, phone TEXT, address TEXT)")
db.execute("CREATE TABLE IF NOT EXISTS pending(uid INTEGER PRIMARY KEY, total INTEGER)")
db.commit()


def get_user(uid):
    row = db.execute("SELECT name, phone, address FROM users WHERE id=?", (uid,)).fetchone()
    return dict(zip(("name", "phone", "address"), row)) if row else None


def save_user(uid, name, phone, address):
    db.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?)", (uid, name, phone, address))
    db.commit()


def fmt(n):
    return f"{n:,}".replace(",", " ") + " so'm"


def menu_kb(user):
    sep = "&" if "?" in WEBAPP_URL else "?"
    url = WEBAPP_URL + sep + urlencode({"n": user["name"].split()[0], "a": user["address"]})
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌭 Buyurtma berish", web_app=WebAppInfo(url=url))],
            [KeyboardButton(text="👤 Ma'lumotlarim")],
        ],
        resize_keyboard=True,
    )


class Reg(StatesGroup):
    name = State()
    phone = State()
    address = State()


async def ask_name(message: Message, state: FSMContext):
    await state.set_state(Reg.name)
    await message.answer("Ism va familiyangizni yozing:", reply_markup=ReplyKeyboardRemove())


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    user = get_user(message.from_user.id)
    if user:
        await message.answer(f"Salom, {user['name']}! Buyurtma berish uchun tugmani bosing.",
                             reply_markup=menu_kb(user))
    else:
        await message.answer("Salom! O'rinboy Hotdog botiga xush kelibsiz. "
                             "Buyurtma berish uchun avval qisqa ro'yxatdan o'tamiz (bir marta).")
        await ask_name(message, state)


@dp.message(Command("yangilash"))
async def update_profile(message: Message, state: FSMContext):
    await ask_name(message, state)


@dp.message(F.text == "👤 Ma'lumotlarim")
async def my_info(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Avval /start bosing.")
        return
    await message.answer(f"Ism: {user['name']}\nTelefon: {user['phone']}\nManzil: {user['address']}\n\n"
                         "O'zgartirish uchun /yangilash ni bosing.")


@dp.message(Reg.name, F.text)
async def reg_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 3:
        await message.answer("Iltimos, ism va familiyangizni to'liq yozing.")
        return
    await state.update_data(name=name)
    await state.set_state(Reg.phone)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamimni yuborish", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True,
    )
    await message.answer("Telefon raqamingizni yuboring (tugmani bosing yoki o'zingiz yozing):", reply_markup=kb)


@dp.message(Reg.phone)
async def reg_phone(message: Message, state: FSMContext):
    raw = message.contact.phone_number if message.contact else (message.text or "")
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) != 12 or not digits.startswith("998"):
        await message.answer("Raqam noto'g'ri. Masalan: +998 90 123 45 67")
        return
    await state.update_data(phone="+" + digits)
    await state.set_state(Reg.address)
    await message.answer("Yetkazish manzilingizni yozing (ko'cha, uy, mo'ljal):", reply_markup=ReplyKeyboardRemove())


@dp.message(Reg.address, F.text)
async def reg_address(message: Message, state: FSMContext):
    address = message.text.strip()
    if len(address) < 3:
        await message.answer("Manzilni to'liqroq yozing.")
        return
    data = await state.get_data()
    save_user(message.from_user.id, data["name"], data["phone"], address)
    await state.clear()
    user = get_user(message.from_user.id)
    await message.answer("Rahmat, ro'yxatdan o'tdingiz! Endi buyurtma berishingiz mumkin.",
                         reply_markup=menu_kb(user))


@dp.message(F.web_app_data)
async def on_order(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Avval /start orqali ro'yxatdan o'ting.")
        return
    order = json.loads(message.web_app_data.data)
    address = order.get("address") or user["address"]
    lines = "\n".join(f"• {i['name']} × {i['qty']} = {fmt(i['price'] * i['qty'])}" for i in order["items"])
    by_card = order.get("pay") == "card"
    pay_text = "💳 Kartaga o'tkazma (chek kutilmoqda)" if by_card else "💵 Naqd"
    text = (
        f"🆕 Yangi buyurtma\n\n{lines}\n\nJami: {fmt(order['total'])}\n"
        f"To'lov: {pay_text}\n"
        f"Ism: {user['name']}\nTelefon: {user['phone']}\nManzil: {address}\n"
    )
    if order.get("comment"):
        text += f"Izoh: {order['comment']}\n"
    text += f"Telegram: @{message.from_user.username or message.from_user.id}"
    await bot.send_message(ADMIN_CHAT_ID, text)
    if by_card:
        db.execute("INSERT OR REPLACE INTO pending VALUES (?,?)", (message.from_user.id, order["total"]))
        db.commit()

    if by_card and CARD_NUMBER:
        await message.answer(
            "Buyurtmangiz qabul qilindi! 🌭\n\n"
            f"To'lov summasi: <b>{fmt(order['total'])}</b>\n"
            f"Karta raqami (bosib nusxalang):\n<code>{html.escape(CARD_NUMBER)}</code>\n"
            f"Karta egasi: {html.escape(CARD_OWNER)}\n\n"
            "Pulni o'tkazgach, to'lov chekini (skrinshot) shu chatga yuboring.",
            parse_mode="HTML",
        )
    elif by_card:
        await message.answer("Buyurtmangiz qabul qilindi! Operator karta raqamini yuboradi.")
    else:
        await message.answer("Buyurtmangiz qabul qilindi! Tez orada bog'lanamiz. 🌭")


@dp.message(F.photo | F.document)
async def on_receipt(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        return
    uid = message.from_user.id
    row = db.execute("SELECT total FROM pending WHERE uid=?", (uid,)).fetchone()
    expected = f"\nKutilgan summa: {fmt(row[0])}" if row else ""
    caption = f"🧾 To'lov cheki\nIsm: {user['name']}\nTelefon: {user['phone']}{expected}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"pay:ok:{uid}")],
        [InlineKeyboardButton(text="⚠️ Kam to'langan", callback_data=f"pay:less:{uid}"),
         InlineKeyboardButton(text="❌ Noto'g'ri chek", callback_data=f"pay:bad:{uid}")],
    ])
    await message.copy_to(ADMIN_CHAT_ID, caption=caption, reply_markup=kb)
    await message.answer("Chek qabul qilindi, rahmat! Operator to'lovni tekshirib, tasdiqlaydi.")


REPLIES = {
    "ok": ("✅ To'lovingiz tasdiqlandi, rahmat! Buyurtmangiz tayyorlanmoqda. 🌭",
           "✅ Tasdiqlandi"),
    "less": ("⚠️ O'tkazilgan summa yetarli emas. Iltimos, yetishmayotgan qismini o'tkazib, "
             "yangi chekni shu chatga yuboring.",
             "⚠️ Kam to'langan, mijozga xabar yuborildi"),
    "bad": ("❌ Chekni tasdiqlab bo'lmadi. Iltimos, to'g'ri to'lov chekini qayta yuboring.",
            "❌ Noto'g'ri chek, mijozga xabar yuborildi"),
}


@dp.callback_query(F.data.startswith("pay:"))
async def on_pay_decision(callback: CallbackQuery):
    if callback.message.chat.id != ADMIN_CHAT_ID:
        await callback.answer()
        return
    _, action, uid = callback.data.split(":")
    uid = int(uid)
    to_user, status = REPLIES[action]
    try:
        await bot.send_message(uid, to_user)
    except Exception:
        await callback.answer("Mijozga xabar yuborib bo'lmadi (u botni bloklagan bo'lishi mumkin).",
                              show_alert=True)
        return
    if action == "ok":
        db.execute("DELETE FROM pending WHERE uid=?", (uid,))
        db.commit()
    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n{status}", reply_markup=None)
    await callback.answer("Mijozga xabar yuborildi")


async def main():
    print("Bot ishga tushdi: v4 (chek tasdiqlash tugmalari bilan)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())