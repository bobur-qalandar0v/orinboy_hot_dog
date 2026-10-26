"""
Dastavchiklar (kuryerlar) tizimi: ro'yxatdan o'tish, kirish, navbatdagi yetkazishlar ro'yxati,
holatlarni o'zgartirish (Tayyorlanmoqda → Yo'lda → Yetkazildi). admin.py ichidan ulanadi.
"""
import hmac
import json
import os
import re
import secrets
import sqlite3
import time

from aiohttp import web

import zal

BASE = os.path.dirname(os.path.abspath(__file__))
COURIER_HTML = os.path.join(BASE, "courier.html")
SESSION_SECONDS = 30 * 24 * 3600
fails = {}
# Dastavchik faqat shu o'tishlarni qila oladi (bekor qilish va orqaga qaytish yo'q)
STEPS = {"new": "cooking", "cooking": "delivering", "delivering": "done"}


def init_courier(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS couriers(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT,
        login TEXT UNIQUE, salt TEXT, pwhash TEXT, pw_plain TEXT, car_number TEXT, car_model TEXT,
        status TEXT DEFAULT 'pending', created TEXT);
    CREATE TABLE IF NOT EXISTS courier_sessions(token TEXT PRIMARY KEY, courier_id INTEGER, created INTEGER);
    """)
    try:
        db.execute("ALTER TABLE orders ADD COLUMN courier_id INTEGER")
    except sqlite3.OperationalError:
        pass
    db.commit()


def err(msg, status=400):
    return web.json_response({"error": msg}, status=status)


def add_routes(app, db, now, change_status, guard):
    def rows(sql, args=()):
        cur = db.execute(sql, args)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def courier_from(request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise web.HTTPUnauthorized()
        r = db.execute("SELECT c.id, c.name, c.phone, c.car_model, c.car_number, c.status, s.created "
                       "FROM courier_sessions s JOIN couriers c ON c.id = s.courier_id WHERE s.token=?",
                       (header[7:],)).fetchone()
        if not r or r[5] != "approved" or time.time() - r[6] > SESSION_SECONDS:
            raise web.HTTPUnauthorized()
        return {"id": r[0], "name": r[1], "phone": r[2], "car": f"{r[3]} {r[4]}".strip()}

    # ------------------------- dastavchik tomoni -------------------------
    async def page(request):
        return web.FileResponse(COURIER_HTML)

    async def register(request):
        d = await request.json()
        name = str(d.get("name", "")).strip()[:60]
        digits = re.sub(r"\D", "", str(d.get("phone", "")))
        if len(digits) == 9:
            digits = "998" + digits
        login = str(d.get("login", "")).strip().lower()
        pw = str(d.get("password", ""))
        car_number = re.sub(r"\s+", " ", str(d.get("car_number", "")).strip().upper())[:15]
        car_model = str(d.get("car_model", "")).strip()[:40]
        if len(name) < 3:
            return err("Ism va familiyangizni to'liq yozing.")
        if len(digits) != 12 or not digits.startswith("998"):
            return err("Telefon raqami noto'g'ri. Masalan: +998 90 123 45 67")
        if not re.fullmatch(r"[a-z0-9_.]{3,20}", login):
            return err("Login 3–20 ta belgi bo'lsin: kichik lotin harflari, raqam, nuqta yoki pastki chiziq.")
        if len(pw) < 6:
            return err("Parol kamida 6 ta belgidan iborat bo'lsin.")
        if len(car_number) < 4:
            return err("Mashina davlat raqamini yozing. Masalan: 01 A 123 BC")
        if len(car_model) < 2:
            return err("Mashina rusumini yozing. Masalan: Chevrolet Nexia")
        if db.execute("SELECT COUNT(*) FROM couriers WHERE status='pending'").fetchone()[0] >= 30:
            return err("Hozircha ro'yxatdan o'tish yopiq. Admin bilan bog'laning.", 429)
        if db.execute("SELECT 1 FROM couriers WHERE login=?", (login,)).fetchone():
            return err("Bu login band. Boshqasini tanlang.", 409)
        salt, h = zal.hash_pw(pw)
        db.execute("INSERT INTO couriers(name, phone, login, salt, pwhash, pw_plain, car_number, car_model, created) "
                   "VALUES (?,?,?,?,?,?,?,?,?)",
                   (name, "+" + digits, login, salt, h, pw, car_number, car_model, now().strftime("%Y-%m-%d %H:%M:%S")))
        db.commit()
        return web.json_response({"ok": True})

    async def login(request):
        d = await request.json()
        login_, pw = str(d.get("login", "")).strip().lower(), str(d.get("password", ""))
        recent = [t for t in fails.get(login_, []) if time.time() - t < 600]
        if len(recent) >= 5:
            return err("Juda ko'p urinish. 10 daqiqadan keyin qayta urinib ko'ring.", 429)
        r = db.execute("SELECT id, name, salt, pwhash, status FROM couriers WHERE login=?", (login_,)).fetchone()
        if not r or not hmac.compare_digest(zal.hash_pw(pw, r[2])[1], r[3]):
            fails[login_] = recent + [time.time()]
            return err("Login yoki parol noto'g'ri.", 401)
        if r[4] == "pending":
            return err("Hisobingiz hali admin tomonidan tasdiqlanmagan.", 403)
        if r[4] != "approved":
            return err("Hisobingiz bloklangan. Admin bilan bog'laning.", 403)
        fails.pop(login_, None)
        db.execute("DELETE FROM courier_sessions WHERE created < ?", (int(time.time()) - SESSION_SECONDS,))
        token = secrets.token_urlsafe(32)
        db.execute("INSERT INTO courier_sessions VALUES (?,?,?)", (token, r[0], int(time.time())))
        db.commit()
        return web.json_response({"token": token, "name": r[1]})

    SELECT = ("SELECT o.id, o.created, o.items, o.total, o.delivery, o.pay, o.address, o.zone, o.comment, o.status, "
              "o.courier_id, u.name AS customer, u.phone AS phone, c.name AS courier, "
              "TRIM(COALESCE(c.car_model,'') || ' ' || COALESCE(c.car_number,'')) AS car "
              "FROM orders o LEFT JOIN users u ON u.id = o.uid LEFT JOIN couriers c ON c.id = o.courier_id "
              "LEFT JOIN zones z ON z.id = o.zone_id ")

    async def c_orders(request):
        me = courier_from(request)
        active = rows(SELECT + "WHERE o.status IN ('new','cooking','delivering') AND COALESCE(z.pickup,0)=0 ORDER BY o.id")
        mine = rows(SELECT + "WHERE o.courier_id=? AND o.status IN ('done','completed') ORDER BY o.id DESC LIMIT 20", (me["id"],))
        for o in active + mine:
            o["items"] = json.loads(o["items"])
        return web.json_response({"courier": me, "active": active, "mine": mine})

    async def c_status(request):
        me = courier_from(request)
        oid = int(request.match_info["id"])
        status = (await request.json()).get("status")
        row = db.execute("SELECT status, courier_id FROM orders WHERE id=?", (oid,)).fetchone()
        if not row:
            return err("Buyurtma topilmadi.", 404)
        if STEPS.get(row[0]) != status:
            return err("Bu buyurtma holati allaqachon o'zgargan. Ro'yxat yangilanadi.", 409)
        if row[1] not in (None, me["id"]):
            return err("Bu buyurtmani boshqa dastavchik olgan.", 409)
        db.execute("UPDATE orders SET courier_id=? WHERE id=?", (me["id"], oid))  # birinchi bosgan dastavchikka tegadi
        db.commit()
        try:
            await change_status(oid, status)
        except ValueError as e:
            return err(str(e), 409)
        return web.json_response({"ok": True})

    async def c_me(request):
        me = courier_from(request)
        return web.json_response(rows(
            "SELECT name, phone, login, car_model, car_number, created, status, "
            "(SELECT COUNT(*) FROM orders o WHERE o.courier_id = couriers.id AND o.status IN ('done','completed')) "
            "AS delivered FROM couriers WHERE id=?", (me["id"],))[0])

    async def c_me_update(request):
        me = courier_from(request)
        d = await request.json()
        digits = re.sub(r"\D", "", str(d.get("phone", "")))
        if len(digits) == 9:
            digits = "998" + digits
        car_number = re.sub(r"\s+", " ", str(d.get("car_number", "")).strip().upper())[:15]
        car_model = str(d.get("car_model", "")).strip()[:40]
        if len(digits) != 12 or not digits.startswith("998"):
            return err("Telefon raqami noto'g'ri. Masalan: +998 90 123 45 67")
        if len(car_number) < 4:
            return err("Mashina davlat raqamini yozing. Masalan: 01 A 123 BC")
        if len(car_model) < 2:
            return err("Mashina rusumini yozing. Masalan: Chevrolet Nexia")
        db.execute("UPDATE couriers SET phone=?, car_number=?, car_model=? WHERE id=?",
                   ("+" + digits, car_number, car_model, me["id"]))
        db.commit()
        return web.json_response({"ok": True})

    async def c_password(request):
        me = courier_from(request)
        d = await request.json()
        old, new = str(d.get("old", "")), str(d.get("new", ""))
        salt, h = db.execute("SELECT salt, pwhash FROM couriers WHERE id=?", (me["id"],)).fetchone()
        if not hmac.compare_digest(zal.hash_pw(old, salt)[1], h):
            return err("Joriy parol noto'g'ri.", 403)
        if len(new) < 6:
            return err("Yangi parol kamida 6 ta belgidan iborat bo'lsin.")
        salt, h = zal.hash_pw(new)
        db.execute("UPDATE couriers SET salt=?, pwhash=?, pw_plain=? WHERE id=?", (salt, h, new, me["id"]))
        db.execute("DELETE FROM courier_sessions WHERE courier_id=? AND token != ?",
                   (me["id"], request.headers["Authorization"][7:]))
        db.commit()
        return web.json_response({"ok": True})

    # ------------------------- admin tomoni -------------------------
    async def a_couriers(request):
        return web.json_response(rows(
            "SELECT c.id, c.name, c.phone, c.login, c.pw_plain AS password, c.car_number, c.car_model, c.status, "
            "c.created, (SELECT COUNT(*) FROM orders o WHERE o.courier_id = c.id AND o.status IN ('done','completed')) "
            "AS delivered FROM couriers c ORDER BY c.id DESC"))

    async def a_status(request):
        guard(request)
        cid, status = int(request.match_info["id"]), (await request.json()).get("status")
        if status not in ("approved", "pending", "blocked"):
            raise web.HTTPBadRequest()
        db.execute("UPDATE couriers SET status=? WHERE id=?", (status, cid))
        if status != "approved":
            db.execute("DELETE FROM courier_sessions WHERE courier_id=?", (cid,))
        db.commit()
        return web.json_response({"ok": True})

    async def a_password(request):
        guard(request)
        cid = int(request.match_info["id"])
        try:
            pw = str((await request.json()).get("password", "")).strip()
        except Exception:
            pw = ""
        if pw and len(pw) < 6:
            return err("Parol kamida 6 ta belgidan iborat bo'lsin.")
        if not pw:
            pw = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(8))
        salt, h = zal.hash_pw(pw)
        db.execute("UPDATE couriers SET salt=?, pwhash=?, pw_plain=? WHERE id=?", (salt, h, pw, cid))
        db.execute("DELETE FROM courier_sessions WHERE courier_id=?", (cid,))
        db.commit()
        return web.json_response({"password": pw})

    async def a_delete(request):
        guard(request)
        cid = int(request.match_info["id"])
        db.execute("DELETE FROM courier_sessions WHERE courier_id=?", (cid,))
        db.execute("DELETE FROM couriers WHERE id=?", (cid,))
        db.commit()
        return web.json_response({"ok": True})

    app.add_routes([
        web.get("/courier", page),
        web.post("/api/c/register", register),
        web.post("/api/c/login", login),
        web.get("/api/c/orders", c_orders),
        web.post("/api/c/orders/{id}/status", c_status),
        web.get("/api/c/me", c_me),
        web.post("/api/c/me", c_me_update),
        web.post("/api/c/password", c_password),
        web.get("/api/couriers", a_couriers),
        web.post("/api/couriers/{id}/status", a_status),
        web.post("/api/couriers/{id}/password", a_password),
        web.delete("/api/couriers/{id}", a_delete),
    ])