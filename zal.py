"""
Zal tizimi (ofitsantlar uchun): ro'yxatdan o'tish, kirish, stollar, stol buyurtmalari, menyu rasmlari.
admin.py ichidan ulanadi.
"""
import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
import time

from aiohttp import web

BASE = os.path.dirname(os.path.abspath(__file__))
WAITER_HTML = os.path.join(BASE, "waiter.html")
SESSION_SECONDS = 30 * 24 * 3600
fails = {}  # login -> [urinishlar vaqti]


def init_zal(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS waiters(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT,
        login TEXT UNIQUE, salt TEXT, pwhash TEXT, status TEXT DEFAULT 'pending', created TEXT);
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, waiter_id INTEGER, created INTEGER);
    CREATE TABLE IF NOT EXISTS zal_tables(id INTEGER PRIMARY KEY AUTOINCREMENT, zal TEXT, number INTEGER,
        UNIQUE(zal, number));
    CREATE TABLE IF NOT EXISTS zal_orders(id INTEGER PRIMARY KEY AUTOINCREMENT, table_id INTEGER, zal TEXT,
        number INTEGER, waiter_id INTEGER, created TEXT, items TEXT, total INTEGER, comment TEXT,
        status TEXT DEFAULT 'open', printed INTEGER DEFAULT 0, closed TEXT);
    """)
    if not db.execute("SELECT 1 FROM zal_tables LIMIT 1").fetchone():
        db.executemany("INSERT INTO zal_tables(zal, number) VALUES (?,?)",
                       [("1-zal", n) for n in range(1, 6)] + [("2-zal", n) for n in range(6, 11)])
    db.commit()


def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(8)
    return salt, hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120_000).hex()


def err(msg, status=400):
    return web.json_response({"error": msg}, status=status)


def add_routes(app, db, now, get_menu, guard):
    def rows(sql, args=()):
        cur = db.execute(sql, args)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def waiter_from(request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise web.HTTPUnauthorized()
        r = db.execute("SELECT w.id, w.name, w.phone, w.status, s.created FROM sessions s "
                       "JOIN waiters w ON w.id = s.waiter_id WHERE s.token=?", (header[7:],)).fetchone()
        if not r or r[3] != "approved" or time.time() - r[4] > SESSION_SECONDS:
            raise web.HTTPUnauthorized()
        return {"id": r[0], "name": r[1], "phone": r[2]}

    # ------------------------- ofitsant tomoni -------------------------
    async def page(request):
        return web.FileResponse(WAITER_HTML)

    async def register(request):
        d = await request.json()
        name = str(d.get("name", "")).strip()[:60]
        digits = re.sub(r"\D", "", str(d.get("phone", "")))
        if len(digits) == 9:
            digits = "998" + digits
        login = str(d.get("login", "")).strip().lower()
        pw = str(d.get("password", ""))
        if len(name) < 3:
            return err("Ism va familiyangizni to'liq yozing.")
        if len(digits) != 12 or not digits.startswith("998"):
            return err("Telefon raqami noto'g'ri. Masalan: +998 90 123 45 67")
        if not re.fullmatch(r"[a-z0-9_.]{3,20}", login):
            return err("Login 3–20 ta belgi bo'lsin: kichik lotin harflari, raqam, nuqta yoki pastki chiziq.")
        if len(pw) < 6:
            return err("Parol kamida 6 ta belgidan iborat bo'lsin.")
        if db.execute("SELECT COUNT(*) FROM waiters WHERE status='pending'").fetchone()[0] >= 30:
            return err("Hozircha ro'yxatdan o'tish yopiq. Admin bilan bog'laning.", 429)
        if db.execute("SELECT 1 FROM waiters WHERE login=?", (login,)).fetchone():
            return err("Bu login band. Boshqasini tanlang.", 409)
        salt, h = hash_pw(pw)
        db.execute("INSERT INTO waiters(name, phone, login, salt, pwhash, created) VALUES (?,?,?,?,?,?)",
                   (name, "+" + digits, login, salt, h, now().strftime("%Y-%m-%d %H:%M:%S")))
        db.commit()
        return web.json_response({"ok": True})

    async def login(request):
        d = await request.json()
        login_, pw = str(d.get("login", "")).strip().lower(), str(d.get("password", ""))
        recent = [t for t in fails.get(login_, []) if time.time() - t < 600]
        if len(recent) >= 5:
            return err("Juda ko'p urinish. 10 daqiqadan keyin qayta urinib ko'ring.", 429)
        r = db.execute("SELECT id, name, salt, pwhash, status FROM waiters WHERE login=?", (login_,)).fetchone()
        if not r or not hmac.compare_digest(hash_pw(pw, r[2])[1], r[3]):
            fails[login_] = recent + [time.time()]
            return err("Login yoki parol noto'g'ri.", 401)
        if r[4] == "pending":
            return err("Hisobingiz hali admin tomonidan tasdiqlanmagan.", 403)
        if r[4] != "approved":
            return err("Hisobingiz bloklangan. Admin bilan bog'laning.", 403)
        fails.pop(login_, None)
        db.execute("DELETE FROM sessions WHERE created < ?", (int(time.time()) - SESSION_SECONDS,))
        token = secrets.token_urlsafe(32)
        db.execute("INSERT INTO sessions VALUES (?,?,?)", (token, r[0], int(time.time())))
        db.commit()
        return web.json_response({"token": token, "name": r[1]})

    async def w_tables(request):
        w = waiter_from(request)
        tables = rows("SELECT id, zal, number FROM zal_tables ORDER BY zal, number")
        opened = {o["table_id"]: o for o in rows(
            "SELECT o.id, o.table_id, o.total, o.created, o.items, o.comment, w.name AS waiter "
            "FROM zal_orders o LEFT JOIN waiters w ON w.id = o.waiter_id WHERE o.status='open'")}
        for t in tables:
            o = opened.get(t["id"])
            t["busy"] = bool(o)
            if o:
                o["items"] = json.loads(o["items"])
            t["order"] = o
        return web.json_response({"waiter": w, "tables": tables})

    async def w_order(request):
        w = waiter_from(request)
        d = await request.json()
        t = db.execute("SELECT id, zal, number FROM zal_tables WHERE id=?", (d.get("table_id"),)).fetchone()
        if not t:
            return err("Stol topilmadi.", 404)
        if db.execute("SELECT 1 FROM zal_orders WHERE table_id=? AND status='open'", (t[0],)).fetchone():
            return err("Bu stol band: mijozlar hali ovqatlanmoqda.", 409)
        menu = {m["id"]: m for m in get_menu(db)}
        items = []
        for it in d.get("items", []):
            m = menu.get(it.get("id"))
            try:
                qty = int(it.get("qty", 0))
            except (TypeError, ValueError):
                qty = 0
            if not m or not 0 < qty <= 50:
                return err("Menyu o'zgargan. Sahifani yangilab, qaytadan tanlang.")
            if m["sold"]:
                return err(f"«{m['name']}» hozircha tugagan.", 409)
            items.append({"id": m["id"], "name": m["name"], "qty": qty, "price": m["price"]})
        if not items:
            return err("Buyurtma bo'sh.")
        total = sum(i["price"] * i["qty"] for i in items)
        cur = db.execute(
            "INSERT INTO zal_orders(table_id, zal, number, waiter_id, created, items, total, comment) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (t[0], t[1], t[2], w["id"], now().strftime("%Y-%m-%d %H:%M:%S"),
             json.dumps(items, ensure_ascii=False), total, str(d.get("comment", ""))[:200]))
        db.commit()
        return web.json_response({"ok": True, "id": cur.lastrowid, "total": total})

    async def w_free(request):
        waiter_from(request)
        db.execute("UPDATE zal_orders SET status='closed', closed=? WHERE table_id=? AND status='open'",
                   (now().strftime("%Y-%m-%d %H:%M:%S"), int(request.match_info["id"])))
        db.commit()
        return web.json_response({"ok": True})

    async def img(request):
        r = db.execute("SELECT mime, data FROM menu_images WHERE id=?", (request.match_info["id"],)).fetchone()
        if not r:
            raise web.HTTPNotFound()
        return web.Response(body=r[1], content_type=r[0], headers={"Cache-Control": "public, max-age=86400"})

    # ------------------------- admin tomoni -------------------------
    async def a_waiters(request):
        return web.json_response(rows("SELECT id, name, phone, login, status, created FROM waiters ORDER BY id DESC"))

    async def a_waiter_status(request):
        guard(request)
        wid, status = int(request.match_info["id"]), (await request.json()).get("status")
        if status not in ("approved", "pending", "blocked"):
            raise web.HTTPBadRequest()
        db.execute("UPDATE waiters SET status=? WHERE id=?", (status, wid))
        if status != "approved":
            db.execute("DELETE FROM sessions WHERE waiter_id=?", (wid,))
        db.commit()
        return web.json_response({"ok": True})

    async def a_waiter_password(request):
        guard(request)
        wid = int(request.match_info["id"])
        pw = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(8))
        salt, h = hash_pw(pw)
        db.execute("UPDATE waiters SET salt=?, pwhash=? WHERE id=?", (salt, h, wid))
        db.execute("DELETE FROM sessions WHERE waiter_id=?", (wid,))
        db.commit()
        return web.json_response({"password": pw})

    async def a_waiter_delete(request):
        guard(request)
        wid = int(request.match_info["id"])
        db.execute("DELETE FROM sessions WHERE waiter_id=?", (wid,))
        db.execute("DELETE FROM waiters WHERE id=?", (wid,))
        db.commit()
        return web.json_response({"ok": True})

    async def a_tables(request):
        return web.json_response(rows(
            "SELECT t.id, t.zal, t.number, EXISTS(SELECT 1 FROM zal_orders o WHERE o.table_id=t.id AND o.status='open') "
            "AS busy FROM zal_tables t ORDER BY t.zal, t.number"))

    async def a_table_add(request):
        guard(request)
        d = await request.json()
        zal = str(d.get("zal", "")).strip()[:30]
        try:
            a, b = int(d.get("from")), int(d.get("to"))
        except (TypeError, ValueError):
            raise web.HTTPBadRequest(text="Raqamlar kerak")
        if not zal or a < 1 or b < a or b - a > 100:
            raise web.HTTPBadRequest(text="Zal nomi va to'g'ri oraliq kerak")
        for n in range(a, b + 1):
            db.execute("INSERT OR IGNORE INTO zal_tables(zal, number) VALUES (?,?)", (zal, n))
        db.commit()
        return web.json_response({"ok": True})

    async def a_table_delete(request):
        guard(request)
        tid = int(request.match_info["id"])
        if db.execute("SELECT 1 FROM zal_orders WHERE table_id=? AND status='open'", (tid,)).fetchone():
            raise web.HTTPConflict(text="Stol band")
        db.execute("DELETE FROM zal_tables WHERE id=?", (tid,))
        db.commit()
        return web.json_response({"ok": True})

    async def a_zal_orders(request):
        data = rows(
            "SELECT o.id, o.zal, o.number, o.created, o.items, o.total, o.comment, o.status, o.printed, "
            "w.name AS waiter, w.phone AS waiter_phone FROM zal_orders o LEFT JOIN waiters w ON w.id = o.waiter_id "
            "ORDER BY (o.status='open') DESC, o.id DESC LIMIT 100")
        for o in data:
            o["items"] = json.loads(o["items"])
        return web.json_response(data)

    async def a_zal_printed(request):
        guard(request)
        db.execute("UPDATE zal_orders SET printed=1 WHERE id=?", (int(request.match_info["id"]),))
        db.commit()
        return web.json_response({"ok": True})

    async def a_zal_close(request):
        guard(request)
        db.execute("UPDATE zal_orders SET status='closed', closed=? WHERE id=?",
                   (now().strftime("%Y-%m-%d %H:%M:%S"), int(request.match_info["id"])))
        db.commit()
        return web.json_response({"ok": True})

    async def a_image_set(request):
        guard(request)
        mid = request.match_info["id"]
        m = re.match(r"data:(image/(?:jpeg|png|webp));base64,(.+)", str((await request.json()).get("image", "")), re.S)
        if not m or not db.execute("SELECT 1 FROM menu WHERE id=?", (mid,)).fetchone():
            raise web.HTTPBadRequest(text="Rasm noto'g'ri")
        try:
            data = base64.b64decode(m.group(2), validate=False)
        except (binascii.Error, ValueError):
            raise web.HTTPBadRequest(text="Rasm noto'g'ri")
        if len(data) > 700_000:
            raise web.HTTPRequestEntityTooLarge(max_size=700_000, actual_size=len(data))
        db.execute("INSERT OR REPLACE INTO menu_images VALUES (?,?,?,?)", (mid, m.group(1), data, int(time.time())))
        db.commit()
        return web.json_response({"ok": True})

    async def a_image_delete(request):
        guard(request)
        db.execute("DELETE FROM menu_images WHERE id=?", (request.match_info["id"],))
        db.commit()
        return web.json_response({"ok": True})

    app.add_routes([
        web.get("/waiter", page),
        web.post("/api/w/register", register),
        web.post("/api/w/login", login),
        web.get("/api/w/tables", w_tables),
        web.post("/api/w/orders", w_order),
        web.post("/api/w/tables/{id}/free", w_free),
        web.get("/img/{id}", img),
        web.get("/api/waiters", a_waiters),
        web.post("/api/waiters/{id}/status", a_waiter_status),
        web.post("/api/waiters/{id}/password", a_waiter_password),
        web.delete("/api/waiters/{id}", a_waiter_delete),
        web.get("/api/tables", a_tables),
        web.post("/api/tables", a_table_add),
        web.delete("/api/tables/{id}", a_table_delete),
        web.get("/api/zal/orders", a_zal_orders),
        web.post("/api/zal/orders/{id}/printed", a_zal_printed),
        web.post("/api/zal/orders/{id}/close", a_zal_close),
        web.post("/api/menu/{id}/image", a_image_set),
        web.delete("/api/menu/{id}/image", a_image_delete),
    ])