"""
Admin panel (veb-sayt) + menyu API. bot.py bilan bir jarayonda ishlaydi va users.db dan o'qiydi.

Muhit o'zgaruvchilari:
  ADMIN_PASSWORD  - panel paroli (majburiy; bo'lmasa panel o'chiq turadi)
  ADMIN_PORT      - port (standart 8080)
  ADMIN_HOST      - manzil (standart 127.0.0.1, ya'ni faqat shu kompyuterdan)
"""
import asyncio
import base64
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiohttp import web

HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin.html")

STATUS_MSG = {
    "cooking": "👨‍🍳 buyurtmangiz tayyorlanmoqda.",
    "delivering": "🛵 buyurtmangiz yo'lda!",
    "done": "✅ buyurtmangiz yetkazildi. Yoqimli ishtaha! 🌭",
    "cancelled": "❌ buyurtmangiz bekor qilindi. Savollar bo'lsa, operator bilan bog'laning.",
}
# Holatlar faqat oldinga yuradi; orqaga qaytib bo'lmaydi.
FLOW = {
    "new": ["cooking", "cancelled"],
    "cooking": ["delivering", "cancelled"],
    "delivering": ["done", "cancelled"],
    "done": [],
    "cancelled": [],
}

DEFAULT_MENU = [
    ("s2", "Sosiskali", "2x sosiska", "Faqat sosiska va chimchi", 18000),
    ("s3", "Sosiskali", "3x sosiska", "Faqat sosiska va chimchi", 22000),
    ("s4", "Sosiskali", "4x sosiska", "Faqat sosiska va chimchi", 25000),
    ("s5", "Sosiskali", "5x sosiska", "Faqat sosiska va chimchi", 28000),
    ("i1", "Ijjonli", "2x sosiska + ijjon", "", 28000),
    ("i2", "Ijjonli", "2x sosiska + 2x ijjon", "", 35000),
    ("i3", "Ijjonli", "3x sosiska + ijjon", "", 35000),
    ("i4", "Ijjonli", "3x sosiska + 2x ijjon", "", 40000),
    ("i5", "Ijjonli", "2x sosiska + ijjon + sir", "", 35000),
    ("c1", "Cheezdog", "Cheezdog (standart)", "", 35000),
    ("c2", "Cheezdog", "Cheezdog (katta)", "", 40000),
    ("t2", "Tushonkali", "Tushonkali 2x sosiska", "", 35000),
    ("t3", "Tushonkali", "Tushonkali 3x sosiska", "", 40000),
    ("tk1", "Toshkent xot dog", "Toshkent xot dog (standart)", "Go'sht assorti", 30000),
    ("tk2", "Toshkent xot dog", "Toshkent xot dog (katta)", "Go'sht assorti", 35000),
    ("m1", "Mangalga xot dog", "Mangalga xot dog sirniy katlet", "", 45000),
    ("m2", "Mangalga xot dog", "Mangalga xot dog shashlikli", "", 35000),
    ("d1", "Ichimliklar", "Cola 0.5 l", "", 8000),
    ("d2", "Ichimliklar", "Fanta 0.5 l", "", 8000),
    ("d3", "Ichimliklar", "Sprite 0.5 l", "", 8000),
    ("d4", "Ichimliklar", "Cola 1.5 l", "", 14000),
    ("d5", "Ichimliklar", "Suv 0.5 l", "", 4000),
]


DEFAULT_ZONES = [
    ("z1", "Yaqin hududlar", 10000, 0),
    ("z2", "O'rta masofa", 15000, 0),
    ("z3", "Uzoq hududlar", 20000, 0),
    ("z0", "Olib ketaman", 0, 1),
]


def init_zones(db):
    db.execute("CREATE TABLE IF NOT EXISTS zones(id TEXT PRIMARY KEY, name TEXT, fee INTEGER, pickup INTEGER DEFAULT 0, pos INTEGER)")
    if not db.execute("SELECT 1 FROM zones LIMIT 1").fetchone():
        db.executemany("INSERT INTO zones VALUES (?,?,?,?,?)", [(*z, i) for i, z in enumerate(DEFAULT_ZONES)])
    db.commit()


def get_zones(db):
    cur = db.execute("SELECT id, name, fee, pickup FROM zones ORDER BY pos, rowid")
    return [{"id": r[0], "name": r[1], "fee": r[2], "pickup": bool(r[3])} for r in cur.fetchall()]


def init_menu(db):
    db.execute("CREATE TABLE IF NOT EXISTS menu(id TEXT PRIMARY KEY, cat TEXT, name TEXT, descr TEXT, "
               "price INTEGER, sold INTEGER DEFAULT 0, pos INTEGER)")
    if not db.execute("SELECT 1 FROM menu LIMIT 1").fetchone():
        db.executemany("INSERT INTO menu VALUES (?,?,?,?,?,0,?)", [(*m, i) for i, m in enumerate(DEFAULT_MENU)])
    db.commit()


def get_menu(db):
    cur = db.execute("SELECT id, cat, name, descr, price, sold FROM menu ORDER BY pos, rowid")
    return [{"id": r[0], "cat": r[1], "name": r[2], "desc": r[3], "price": r[4], "sold": bool(r[5])}
            for r in cur.fetchall()]


def make_app(db, bot, password, kb_for):
    tasks = set()

    def rows(sql, args=()):
        cur = db.execute(sql, args)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def guard(request):
        if request.headers.get("X-Admin") != "1":
            raise web.HTTPForbidden()

    @web.middleware
    async def auth(request, handler):
        if request.method == "GET" and request.path in ("/api/menu", "/api/zones"):
            return await handler(request)  # menyu hammaga ochiq (maxfiy ma'lumot yo'q)
        ok = False
        header = request.headers.get("Authorization", "")
        if header.startswith("Basic "):
            try:
                _, _, pw = base64.b64decode(header[6:]).decode().partition(":")
                ok = hmac.compare_digest(pw.encode(), password.encode())
            except Exception:
                ok = False
        if not ok:
            return web.Response(status=401, text="Parol kerak",
                                headers={"WWW-Authenticate": 'Basic realm="O\'rinboy admin"'})
        return await handler(request)

    async def index(request):
        return web.FileResponse(HTML_PATH)

    async def stats(request):
        orders = rows("SELECT created, items, total, pay FROM orders WHERE status != 'cancelled'")
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        daily = {(now - timedelta(days=i)).strftime("%Y-%m-%d"): [0, 0] for i in range(13, -1, -1)}
        hours, prods, pay = [0] * 24, {}, {"cash": 0, "card": 0}
        revenue = t_orders = t_revenue = 0
        for o in orders:
            day = o["created"][:10]
            revenue += o["total"]
            if day == today:
                t_orders += 1
                t_revenue += o["total"]
            if day in daily:
                daily[day][0] += 1
                daily[day][1] += o["total"]
            hours[int(o["created"][11:13])] += 1
            pay["card" if o["pay"] == "card" else "cash"] += 1
            for it in json.loads(o["items"]):
                p = prods.setdefault(it["name"], {"name": it["name"], "qty": 0, "revenue": 0})
                p["qty"] += it["qty"]
                p["revenue"] += it["qty"] * it["price"]
        n = len(orders)
        rc, ra = db.execute("SELECT COUNT(rating), AVG(rating) FROM orders WHERE rating IS NOT NULL").fetchone()
        return web.json_response({
            "orders": n, "revenue": revenue, "avg": round(revenue / n) if n else 0,
            "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "new": db.execute("SELECT COUNT(*) FROM orders WHERE status='new'").fetchone()[0],
            "today_orders": t_orders, "today_revenue": t_revenue,
            "rating_count": rc, "rating_avg": round(ra, 1) if ra else 0,
            "delivery_revenue": db.execute("SELECT COALESCE(SUM(delivery), 0) FROM orders WHERE status != 'cancelled'").fetchone()[0],
            "daily": [{"d": d, "orders": v[0], "revenue": v[1]} for d, v in daily.items()],
            "hours": hours, "pay": pay,
            "products": sorted(prods.values(), key=lambda x: -x["qty"]),
        })

    async def users(request):
        return web.json_response(rows(
            "SELECT u.id, u.name, u.phone, u.address, COUNT(o.id) AS orders, "
            "COALESCE(SUM(o.total), 0) AS spent, MAX(o.created) AS last "
            "FROM users u LEFT JOIN orders o ON o.uid = u.id AND o.status != 'cancelled' "
            "GROUP BY u.id ORDER BY orders DESC, spent DESC"))

    async def orders(request):
        data = rows(
            "SELECT o.id, o.created, o.items, o.total, o.pay, o.address, o.comment, o.status, o.rating, o.zone, o.delivery, "
            "u.name, u.phone FROM orders o LEFT JOIN users u ON u.id = o.uid ORDER BY o.id DESC LIMIT 200")
        for o in data:
            o["items"] = json.loads(o["items"])
        return web.json_response(data)

    async def set_status(request):
        guard(request)
        oid = int(request.match_info["id"])
        status = (await request.json()).get("status")
        row = db.execute("SELECT uid, status FROM orders WHERE id=?", (oid,)).fetchone()
        if not row:
            raise web.HTTPNotFound()
        if status not in FLOW.get(row[1], []):
            raise web.HTTPConflict(text="Bu holatga o'tib bo'lmaydi")
        uid = row[0]
        db.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
        if status in ("done", "cancelled"):
            db.execute("DELETE FROM pending WHERE uid=?", (uid,))
        db.commit()
        notified = False
        try:
            await bot.send_message(uid, f"Buyurtma #{oid}: {STATUS_MSG[status]}", reply_markup=kb_for(uid))
            notified = True
            if status == "done":
                stars = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text=f"{n}⭐", callback_data=f"rate:{oid}:{n}") for n in range(1, 6)]])
                await bot.send_message(uid, "Xizmatimizni baholang, fikringiz biz uchun muhim:", reply_markup=stars)
        except Exception:
            pass
        return web.json_response({"ok": True, "notified": notified})

    # ---- Menyu ----
    async def menu_list(request):
        return web.json_response(get_menu(db), headers={"Access-Control-Allow-Origin": "*",
                                                        "Cache-Control": "no-store"})

    async def read_item(request):
        d = await request.json()
        cat, name = str(d.get("cat", "")).strip()[:40], str(d.get("name", "")).strip()[:80]
        desc = str(d.get("desc", "")).strip()[:120]
        try:
            price = int(d.get("price"))
        except (TypeError, ValueError):
            price = 0
        if not cat or not name or price <= 0:
            raise web.HTTPBadRequest(text="Bo'lim, nom va narx kerak")
        return cat, name, desc, price

    async def menu_create(request):
        guard(request)
        cat, name, desc, price = await read_item(request)
        pos = (db.execute("SELECT MAX(pos) FROM menu").fetchone()[0] or 0) + 1
        db.execute("INSERT INTO menu VALUES (?,?,?,?,?,0,?)", (uuid.uuid4().hex[:8], cat, name, desc, price, pos))
        db.commit()
        return web.json_response({"ok": True})

    async def menu_update(request):
        guard(request)
        cat, name, desc, price = await read_item(request)
        db.execute("UPDATE menu SET cat=?, name=?, descr=?, price=? WHERE id=?",
                   (cat, name, desc, price, request.match_info["id"]))
        db.commit()
        return web.json_response({"ok": True})

    async def menu_delete(request):
        guard(request)
        db.execute("DELETE FROM menu WHERE id=?", (request.match_info["id"],))
        db.commit()
        return web.json_response({"ok": True})

    async def zones_list(request):
        return web.json_response(get_zones(db), headers={"Access-Control-Allow-Origin": "*",
                                                         "Cache-Control": "no-store"})

    async def read_zone(request):
        d = await request.json()
        name = str(d.get("name", "")).strip()[:60]
        try:
            fee = int(d.get("fee"))
        except (TypeError, ValueError):
            fee = -1
        if not name or fee < 0:
            raise web.HTTPBadRequest(text="Nom va narx kerak")
        return name, fee, 1 if d.get("pickup") else 0

    async def zone_create(request):
        guard(request)
        name, fee, pickup = await read_zone(request)
        pos = (db.execute("SELECT MAX(pos) FROM zones").fetchone()[0] or 0) + 1
        db.execute("INSERT INTO zones VALUES (?,?,?,?,?)", (uuid.uuid4().hex[:8], name, fee, pickup, pos))
        db.commit()
        return web.json_response({"ok": True})

    async def zone_update(request):
        guard(request)
        name, fee, pickup = await read_zone(request)
        db.execute("UPDATE zones SET name=?, fee=?, pickup=? WHERE id=?", (name, fee, pickup, request.match_info["id"]))
        db.commit()
        return web.json_response({"ok": True})

    async def zone_delete(request):
        guard(request)
        db.execute("DELETE FROM zones WHERE id=?", (request.match_info["id"],))
        db.commit()
        return web.json_response({"ok": True})

    async def broadcast(text):
        for (uid,) in db.execute("SELECT id FROM users").fetchall():
            try:
                await bot.send_message(uid, text)
            except Exception:
                pass
            await asyncio.sleep(0.06)

    async def menu_sold(request):
        guard(request)
        d = await request.json()
        mid, sold = request.match_info["id"], 1 if d.get("sold") else 0
        row = db.execute("SELECT name FROM menu WHERE id=?", (mid,)).fetchone()
        if not row:
            raise web.HTTPNotFound()
        db.execute("UPDATE menu SET sold=? WHERE id=?", (sold, mid))
        db.commit()
        sent = 0
        if d.get("notify"):
            text = (f"⚠️ Kechirasiz, «{row[0]}» hozircha tugadi." if sold
                    else f"✅ «{row[0]}» yana bor! Buyurtma berishingiz mumkin. 🌭")
            sent = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            t = asyncio.create_task(broadcast(text))
            tasks.add(t)
            t.add_done_callback(tasks.discard)
        return web.json_response({"ok": True, "sent": sent})

    app = web.Application(middlewares=[auth])
    app.add_routes([
        web.get("/", index),
        web.get("/api/stats", stats),
        web.get("/api/users", users),
        web.get("/api/orders", orders),
        web.post("/api/orders/{id}/status", set_status),
        web.get("/api/menu", menu_list),
        web.post("/api/menu", menu_create),
        web.put("/api/menu/{id}", menu_update),
        web.delete("/api/menu/{id}", menu_delete),
        web.post("/api/menu/{id}/sold", menu_sold),
        web.get("/api/zones", zones_list),
        web.post("/api/zones", zone_create),
        web.put("/api/zones/{id}", zone_update),
        web.delete("/api/zones/{id}", zone_delete),
    ])
    return app


async def run(db, bot, kb_for):
    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        print("ADMIN_PASSWORD o'rnatilmagan, admin panel o'chiq.")
        return
    host = os.environ.get("ADMIN_HOST", "127.0.0.1")
    port = int(os.environ.get("ADMIN_PORT", "8080"))
    runner = web.AppRunner(make_app(db, bot, password, kb_for))
    await runner.setup()
    await web.TCPSite(runner, host, port).start()
    print(f"Admin panel: http://{'localhost' if host == '127.0.0.1' else host}:{port}")