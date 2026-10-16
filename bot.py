"""
Hotdog buyurtma boti (aiogram 3).

O'rnatish:   pip install aiogram
Ishga tushirish:
    export BOT_TOKEN="BotFather bergan token"
    export WEBAPP_URL="https://sizning-domen.uz/index.html"   # HTTPS bo'lishi shart
    export ADMIN_CHAT_ID="123456789"                         # buyurtmalar keladigan chat ID
    python bot.py
"""
import asyncio
import json
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (KeyboardButton, Message, ReplyKeyboardMarkup,
                           WebAppInfo)

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBAPP_URL = os.environ["WEBAPP_URL"]
ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"])

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ") + " so'm"


@dp.message(Command("start"))
async def start(message: Message):
    # Eslatma: sendData faqat ReplyKeyboard'dagi WebApp tugmasi bilan ishlaydi
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🌭 Buyurtma berish",
                                  web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True,
    )
    await message.answer(
        "Salom! O'rinboy Hotdog botiga xush kelibsiz. Buyurtma berish uchun pastdagi tugmani bosing.",
        reply_markup=kb,
    )


@dp.message(F.web_app_data)
async def on_order(message: Message):
    order = json.loads(message.web_app_data.data)
    lines = "\n".join(
        f"• {i['name']} × {i['qty']} = {fmt(i['price'] * i['qty'])}"
        for i in order["items"]
    )
    text = (
        f"🆕 Yangi buyurtma\n\n{lines}\n\n"
        f"Jami: {fmt(order['total'])}\n"
        f"Ism: {order['name']}\n"
        f"Telefon: {order['phone']}\n"
        f"Manzil: {order['address']}\n"
        f"Telegram: @{message.from_user.username or message.from_user.id}"
    )
    await bot.send_message(ADMIN_CHAT_ID, text)
    await message.answer("Buyurtmangiz qabul qilindi! Tez orada bog'lanamiz. 🌭")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())