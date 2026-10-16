"""
Admin panel (veb-sayt). bot.py bilan bir jarayonda ishlaydi va users.db dan o'qiydi.

Muhit o'zgaruvchilari:
  ADMIN_PASSWORD  - panel paroli (majburiy; bo'lmasa panel o'chiq turadi)
  ADMIN_PORT      - port (standart 8080)
  ADMIN_HOST      - manzil (standart 127.0.0.1, ya'ni faqat shu kompyuterdan)
"""
import base64
import hmac
import json
import os
from datetime import datetime, timedelta

from aiohttp import web

HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin.html")

STATUS_MSG = {
    "cooking": "👨‍🍳 buyurtmangiz tayyorlanmoqda.",
    "delivering": "🛵 buyurtmangiz yo'lda!",
    "done": "✅ buyurtmangiz yetkazildi. Yoqimli ishtaha! 🌭",
    "cancelled": "❌ buyurtmangiz bekor qilindi. Savollar bo'lsa, operator bilan bog'laning.",
}
STATUSES = {"new", *STATUS_MSG}


def make_app(db, bot, password):
    def rows(sql, args=()):
        cur = db.execute(sql, args)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    @web.middleware
    async def auth(request, handler):
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
        return web.json_response({
            "orders": n,
            "revenue": revenue,
            "avg": round(revenue / n) if n else 0,
            "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "new": db.execute("SELECT COUNT(*) FROM orders WHERE status='new'").fetchone()[0],
            "today_orders": t_orders,
            "today_revenue": t_revenue,
            "daily": [{"d": d, "orders": v[0], "revenue": v[1]} for d, v in daily.items()],
            "hours": hours,
            "pay": pay,
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
            "SELECT o.id, o.created, o.items, o.total, o.pay, o.address, o.comment, o.status, "
            "u.name, u.phone FROM orders o LEFT JOIN users u ON u.id = o.uid "
            "ORDER BY o.id DESC LIMIT 200")
        for o in data:
            o["items"] = json.loads(o["items"])
        return web.json_response(data)

    async def set_status(request):
        if request.headers.get("X-Admin") != "1":
            raise web.HTTPForbidden()
        oid = int(request.match_info["id"])
        status = (await request.json()).get("status")
        if status not in STATUSES:
            raise web.HTTPBadRequest()
        row = db.execute("SELECT uid FROM orders WHERE id=?", (oid,)).fetchone()
        if not row:
            raise web.HTTPNotFound()
        db.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
        db.commit()
        notified = False
        if status in STATUS_MSG:
            try:
                await bot.send_message(row[0], f"Buyurtma #{oid}: {STATUS_MSG[status]}")
                notified = True
            except Exception:
                pass
        return web.json_response({"ok": True, "notified": notified})

    app = web.Application(middlewares=[auth])
    app.add_routes([
        web.get("/", index),
        web.get("/api/stats", stats),
        web.get("/api/users", users),
        web.get("/api/orders", orders),
        web.post("/api/orders/{id}/status", set_status),
    ])
    return app


async def run(db, bot):
    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        print("ADMIN_PASSWORD o'rnatilmagan, admin panel o'chiq.")
        return
    host = os.environ.get("ADMIN_HOST", "127.0.0.1")
    port = int(os.environ.get("ADMIN_PORT", "8080"))
    runner = web.AppRunner(make_app(db, bot, password))
    await runner.setup()
    await web.TCPSite(runner, host, port).start()
    print(f"Admin panel: http://{'localhost' if host == '127.0.0.1' else host}:{port}")