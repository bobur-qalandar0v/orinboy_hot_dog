"""
Kompyuteringizdagi users.db dan hududlar va menyuni fayllarga yozadi:
  seed_zones.txt  - har qatorda "Hudud nomi - narxi"
  seed_menu.json  - menyu
Bu fayllarni GitHub'ga yuklasangiz, Render'da baza bo'sh boshlanganda ular avtomatik tiklanadi.

Ishga tushirish (users.db turgan papkada):   py -3.13 export_data.py
"""
import json
import os
import sqlite3

base = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(base, "users.db")
if not os.path.exists(path):
    raise SystemExit("users.db topilmadi. Bu fayl users.db bilan bir papkada bo'lishi kerak.")

db = sqlite3.connect(path)
zones = db.execute("SELECT name, fee FROM zones WHERE pickup = 0 ORDER BY pos, rowid").fetchall()
with open(os.path.join(base, "seed_zones.txt"), "w", encoding="utf-8") as f:
    for name, fee in zones:
        f.write(f"{name} - {fee}\n")

menu = db.execute("SELECT id, cat, name, descr, price, sold FROM menu ORDER BY pos, rowid").fetchall()
with open(os.path.join(base, "seed_menu.json"), "w", encoding="utf-8") as f:
    json.dump([{"id": r[0], "cat": r[1], "name": r[2], "desc": r[3], "price": r[4], "sold": r[5]} for r in menu],
              f, ensure_ascii=False, indent=1)

print(f"Hududlar: {len(zones)} ta  ->  seed_zones.txt")
print(f"Menyu: {len(menu)} ta mahsulot  ->  seed_menu.json")
