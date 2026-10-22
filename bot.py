"""
O'rinboy Hotdog buyurtma boti (aiogram 3).

Muhit o'zgaruvchilari: BOT_TOKEN, WEBAPP_URL, ADMIN_CHAT_ID, CARD_NUMBER, CARD_OWNER,
ADMIN_PASSWORD (admin panel uchun), PUBLIC_URL (ixtiyoriy: menyu API ning ochiq HTTPS manzili)
"""
import asyncio
import html
import json
import os
import re
import sqlite3
from datetime import datetime
from urllib.parse import urlencode

import admin
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
PUBLIC_URL = (os.environ.get("PUBLIC_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

db = sqlite3.connect(os.environ.get("DB_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db"))
db.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, phone TEXT, address TEXT)")
db.execute("CREATE TABLE IF NOT EXISTS pending(uid INTEGER PRIMARY KEY, total INTEGER)")
db.execute("CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, created TEXT, "
           "items TEXT, total INTEGER, pay TEXT, address TEXT, comment TEXT, status TEXT DEFAULT 'new')")
for _sql in ("ALTER TABLE orders ADD COLUMN rating INTEGER", "ALTER TABLE orders ADD COLUMN zone TEXT",
             "ALTER TABLE orders ADD COLUMN zone_id TEXT", "ALTER TABLE orders ADD COLUMN delivery INTEGER DEFAULT 0", "ALTER TABLE orders ADD COLUMN ahead INTEGER",
             "ALTER TABLE users ADD COLUMN zone TEXT"):
    try:
        db.execute(_sql)
    except sqlite3.OperationalError:
        pass
admin.init_menu(db)
admin.init_zones(db)
db.commit()


def get_user(uid):
    row = db.execute("SELECT name, phone, address, zone FROM users WHERE id=?", (uid,)).fetchone()
    return dict(zip(("name", "phone", "address", "zone"), row)) if row else None


def save_user(uid, name, phone, address):
    db.execute("INSERT INTO users(id, name, phone, address) VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
               "name=excluded.name, phone=excluded.phone, address=excluded.address", (uid, name, phone, address))
    db.commit()


def fmt(n):
    return f"{n:,}".replace(",", " ") + " so'm"


def active_order(uid):
    """Hali tayyorlanishi boshlanmagan (tahrirlash va bekor qilish mumkin) buyurtma."""
    r = db.execute("SELECT id, items, total, zone_id FROM orders WHERE uid=? AND status='new' ORDER BY id DESC LIMIT 1",
                   (uid,)).fetchone()
    return {"id": r[0], "items": json.loads(r[1]), "total": r[2], "zone": r[3]} if r else None


def kb_for(uid):
    user = get_user(uid)
    if not user:
        return ReplyKeyboardRemove()
    params = {"n": user["name"].split()[0], "a": user["address"]}
    if PUBLIC_URL:
        params["api"] = PUBLIC_URL
    order = active_order(uid)
    zid = (order or {}).get("zone") or user.get("zone")
    if zid:
        params["z"] = zid
    if order:
        params["e"] = order["id"]
        params["c"] = ",".join(f"{i['id']}:{i['qty']}" for i in order["items"])
    sep = "&" if "?" in WEBAPP_URL else "?"
    app = WebAppInfo(url=WEBAPP_URL + sep + urlencode(params))
    if order:
        rows = [[KeyboardButton(text="✏️ Buyurtmani tahrirlash", web_app=app)],
                [KeyboardButton(text="❌ Buyurtmani bekor qilish")]]
    else:
        rows = [[KeyboardButton(text="🌭 Buyurtma berish", web_app=app)]]
    rows.append([KeyboardButton(text="👤 Ma'lumotlarim")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


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
                             reply_markup=kb_for(message.from_user.id))
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
    await message.answer("Rahmat, ro'yxatdan o'tdingiz! Endi buyurtma berishingiz mumkin.",
                         reply_markup=kb_for(message.from_user.id))


@dp.message(F.web_app_data)
async def on_order(message: Message):
    uid = message.from_user.id
    user = get_user(uid)
    if not user:
        await message.answer("Avval /start orqali ro'yxatdan o'ting.")
        return
    order = json.loads(message.web_app_data.data)

    # Narx va nomlar sahifadan emas, bazadan olinadi (soxtalashtirib bo'lmaydi)
    menu = {m["id"]: m for m in admin.get_menu(db)}
    items, soldout, bad = [], [], False
    for it in order.get("items", []):
        m = menu.get(it.get("id"))
        try:
            qty = int(it.get("qty", 0))
        except (TypeError, ValueError):
            qty = 0
        if not m or not 0 < qty <= 50:
            bad = True
        elif m["sold"]:
            soldout.append(m["name"])
        else:
            items.append({"id": m["id"], "name": m["name"], "qty": qty, "price": m["price"]})
    if soldout or bad or not items:
        msg = "Kechirasiz, buyurtmani qabul qilib bo'lmadi."
        if soldout:
            msg += "\nHozircha tugagan: " + ", ".join(soldout) + "."
        msg += "\nMenyuni qayta ochib, qaytadan tanlang."
        await message.answer(msg, reply_markup=kb_for(uid))
        return

    zone = next((z for z in admin.get_zones(db) if z["id"] == order.get("zone")), None)
    if not zone:
        await message.answer("Yetkazib berish hududi topilmadi. Menyuni qayta ochib, hududni tanlang.",
                             reply_markup=kb_for(uid))
        return
    subtotal = sum(i["price"] * i["qty"] for i in items)
    delivery = zone["fee"]
    total = subtotal + delivery
    address = "Olib ketadi (o'zi keladi)" if zone["pickup"] else (order.get("address") or user["address"]).strip()
    comment = str(order.get("comment", ""))[:200]
    by_card = order.get("pay") == "card"
    pay = "card" if by_card else "cash"
    items_json = json.dumps(items, ensure_ascii=False)
    edit_id = int(order.get("edit") or 0)

    if edit_id:
        row = db.execute("SELECT status FROM orders WHERE id=? AND uid=?", (edit_id, uid)).fetchone()
        if not row or row[0] != "new":
            await message.answer("Bu buyurtmani endi o'zgartirib bo'lmaydi (tayyorlanmoqda yoki yakunlangan).",
                                 reply_markup=kb_for(uid))
            return
        db.execute("UPDATE orders SET items=?, total=?, pay=?, address=?, comment=?, zone=?, zone_id=?, delivery=? WHERE id=?",
                   (items_json, total, pay, address, comment, zone["name"], zone["id"], delivery, edit_id))
        oid, title = edit_id, "✏️ Buyurtma o'zgartirildi"
    else:
        cur = db.execute(
            "INSERT INTO orders(uid, created, items, total, pay, address, comment, zone, zone_id, delivery) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (uid, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), items_json, total, pay, address, comment,
             zone["name"], zone["id"], delivery))
        oid, title = cur.lastrowid, "🆕 Yangi buyurtma"
    if by_card:
        db.execute("INSERT OR REPLACE INTO pending VALUES (?,?)", (uid, total))
    else:
        db.execute("DELETE FROM pending WHERE uid=?", (uid,))
    db.execute("UPDATE users SET zone=? WHERE id=?", (zone["id"], uid))
    ahead = admin.queue_ahead(db, oid)
    db.execute("UPDATE orders SET ahead=? WHERE id=?", (ahead, oid))
    db.commit()

    lines = "\n".join(f"• {i['name']} × {i['qty']} = {fmt(i['price'] * i['qty'])}" for i in items)
    pay_text = "💳 Kartaga o'tkazma (chek kutilmoqda)" if by_card else "💵 Naqd"
    fee_label = "Olib ketish" if zone["pickup"] else "Yetkazib berish"
    fee_line = "Olib ketadi (yetkazish yo'q)" if zone["pickup"] else f"Yetkazib berish ({zone['name']}): {fmt(delivery)}"
    text = (f"{title} #{oid}\n\n{lines}\n{fee_line}\n\nJami: {fmt(total)}\nTo'lov: {pay_text}\n"
            f"Ism: {user['name']}\nTelefon: {user['phone']}\nManzil: {address}\n")
    if comment:
        text += f"Izoh: {comment}\n"
    text += f"Telegram: @{message.from_user.username or uid}"
    await bot.send_message(ADMIN_CHAT_ID, text)

    done = "Buyurtmangiz o'zgartirildi! ✏️" if edit_id else "Buyurtmangiz qabul qilindi! 🌭"
    queue_text = ("Sizdan oldin buyurtma yo'q, navbat sizniki! 🎉" if ahead == 0
                  else f"Sizdan oldin {ahead} ta buyurtma bor, siz {ahead + 1}-chisiz.")
    if by_card and CARD_NUMBER:
        await message.answer(
            f"{done}\n{queue_text}\n\nMahsulotlar: {fmt(subtotal)}\n{fee_label}: {fmt(delivery)}\nTo'lov summasi: <b>{fmt(total)}</b>\n"
            f"Karta raqami (bosib nusxalang):\n<code>{html.escape(CARD_NUMBER)}</code>\n"
            f"Karta egasi: {html.escape(CARD_OWNER)}\n\n"
            "Pulni o'tkazgach, to'lov chekini (skrinshot) shu chatga yuboring.",
            parse_mode="HTML", reply_markup=kb_for(uid))
    elif by_card:
        await message.answer(f"{done}\n{queue_text}\nOperator karta raqamini yuboradi.", reply_markup=kb_for(uid))
    else:
        await message.answer(f"{done}\n{queue_text}\nJami: {fmt(total)}{'' if zone['pickup'] else ' (yetkazib berish bilan)'}. Tez orada bog'lanamiz. "
                             "Tayyorlash boshlanmaguncha buyurtmani tahrirlashingiz yoki bekor qilishingiz mumkin.",
                             reply_markup=kb_for(uid))


# ---- Mijoz buyurtmani bekor qilishi ----
@dp.message(F.text == "❌ Buyurtmani bekor qilish")
async def ask_cancel(message: Message):
    o = active_order(message.from_user.id)
    if not o:
        await message.answer("Bekor qilinadigan buyurtma yo'q.", reply_markup=kb_for(message.from_user.id))
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Ha, bekor qilish", callback_data=f"cancel:yes:{o['id']}"),
        InlineKeyboardButton(text="Yo'q", callback_data="cancel:no:0"),
    ]])
    await message.answer(f"Buyurtma #{o['id']} ({fmt(o['total'])}) bekor qilinsinmi?", reply_markup=kb)


@dp.callback_query(F.data.startswith("cancel:"))
async def do_cancel(cb: CallbackQuery):
    _, answer, oid = cb.data.split(":")
    if answer == "no":
        await cb.message.edit_text("Buyurtma saqlab qolindi.")
        await cb.answer()
        return
    uid, oid = cb.from_user.id, int(oid)
    row = db.execute("SELECT uid, status, pay FROM orders WHERE id=?", (oid,)).fetchone()
    if not row or row[0] != uid:
        await cb.answer()
        return
    if row[1] != "new":
        await cb.message.edit_text("Buyurtma allaqachon tayyorlanmoqda, endi bekor qilib bo'lmaydi. "
                                   "Operator bilan bog'laning.")
        await cb.answer()
        return
    db.execute("UPDATE orders SET status='cancelled' WHERE id=?", (oid,))
    db.execute("DELETE FROM pending WHERE uid=?", (uid,))
    db.commit()
    await cb.message.edit_text(f"Buyurtma #{oid} bekor qilindi.")
    await bot.send_message(uid, "Yangi buyurtma berishingiz mumkin.", reply_markup=kb_for(uid))
    user = get_user(uid)
    await bot.send_message(ADMIN_CHAT_ID, f"❌ Mijoz buyurtma #{oid} ni bekor qildi.\n"
                                          f"{user['name']}, {user['phone']}\n"
                                          f"To'lov turi: {'💳 Karta' if row[2] == 'card' else '💵 Naqd'}")
    await admin.notify_queue(db, bot)
    await cb.answer()


# ---- Mijoz buyurtmani qabul qildi ----
@dp.callback_query(F.data.startswith("recv:"))
async def on_received(cb: CallbackQuery):
    oid = int(cb.data.split(":")[1])
    row = db.execute("SELECT uid, status FROM orders WHERE id=?", (oid,)).fetchone()
    if not row or row[0] != cb.from_user.id:
        await cb.answer()
        return
    await cb.message.edit_text("✅ Rahmat! Buyurtmani qabul qilganingiz tasdiqlandi.")
    if row[1] == "done":
        db.execute("UPDATE orders SET status='completed' WHERE id=?", (oid,))
        db.commit()
        await bot.send_message(cb.from_user.id, "Xizmatimizni baholang, fikringiz biz uchun muhim:",
                               reply_markup=admin.rating_kb(oid))
    await cb.answer()


# ---- Baho ----
@dp.callback_query(F.data.startswith("rate:"))
async def on_rate(cb: CallbackQuery):
    _, oid, n = cb.data.split(":")
    oid, n = int(oid), int(n)
    row = db.execute("SELECT uid, rating FROM orders WHERE id=?", (oid,)).fetchone()
    if not row or row[0] != cb.from_user.id or not 1 <= n <= 5:
        await cb.answer()
        return
    if row[1]:
        await cb.answer("Baho allaqachon qabul qilingan.")
        return
    db.execute("UPDATE orders SET rating=? WHERE id=?", (n, oid))
    db.commit()
    await cb.message.edit_text(f"Rahmat! Bahoyingiz: {'⭐' * n}")
    if n <= 3:
        user = get_user(row[0])
        await bot.send_message(ADMIN_CHAT_ID, f"⚠️ Buyurtma #{oid} uchun past baho: {'⭐' * n}\n"
                                              f"{user['name']}, {user['phone']}")
    await cb.answer()


# ---- To'lov cheki ----
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
    "ok": ("✅ To'lovingiz tasdiqlandi, rahmat! Buyurtmangiz tayyorlanmoqda. 🌭", "✅ Tasdiqlandi"),
    "less": ("⚠️ O'tkazilgan summa yetarli emas. Iltimos, yetishmayotgan qismini o'tkazib, "
             "yangi chekni shu chatga yuboring.", "⚠️ Kam to'langan, mijozga xabar yuborildi"),
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
    print("Bot ishga tushdi: v8 (navbat, qabul qildim, hudud qidiruvi)")
    await admin.run(db, bot, kb_for)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())