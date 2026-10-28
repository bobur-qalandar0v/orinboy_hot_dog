let MENU = [
    { cat: "Sosiskali", id: "s2", name: "2x sosiska", desc: "Faqat sosiska va chimchi", price: 18000 },
    { cat: "Sosiskali", id: "s3", name: "3x sosiska", desc: "Faqat sosiska va chimchi", price: 22000 },
    { cat: "Sosiskali", id: "s4", name: "4x sosiska", desc: "Faqat sosiska va chimchi", price: 25000 },
    { cat: "Sosiskali", id: "s5", name: "5x sosiska", desc: "Faqat sosiska va chimchi", price: 28000 },
    { cat: "Ijjonli", id: "i1", name: "2x sosiska + ijjon", desc: "", price: 28000 },
    { cat: "Ijjonli", id: "i2", name: "2x sosiska + 2x ijjon", desc: "", price: 35000 },
    { cat: "Ijjonli", id: "i3", name: "3x sosiska + ijjon", desc: "", price: 35000 },
    { cat: "Ijjonli", id: "i4", name: "3x sosiska + 2x ijjon", desc: "", price: 40000 },
    { cat: "Ijjonli", id: "i5", name: "2x sosiska + ijjon + sir", desc: "", price: 35000 },
    { cat: "Cheezdog", id: "c1", name: "Cheezdog", desc: "Standart", price: 35000 },
    { cat: "Cheezdog", id: "c2", name: "Cheezdog", desc: "Katta", price: 40000 },
    { cat: "Tushonkali", id: "t2", name: "Tushonkali 2x sosiska", desc: "", price: 35000 },
    { cat: "Tushonkali", id: "t3", name: "Tushonkali 3x sosiska", desc: "", price: 40000 },
    { cat: "Toshkent xot dog", id: "tk1", name: "Toshkent xot dog", desc: "Go'sht assorti, standart", price: 30000 },
    { cat: "Toshkent xot dog", id: "tk2", name: "Toshkent xot dog", desc: "Go'sht assorti, katta", price: 35000 },
    { cat: "Mangalga xot dog", id: "m1", name: "Mangalga xot dog sirniy katlet", desc: "", price: 45000 },
    { cat: "Mangalga xot dog", id: "m2", name: "Mangalga xot dog shashlikli", desc: "", price: 35000 },
    { cat: "Ichimliklar", id: "d1", name: "Cola 0.5 l", desc: "", price: 8000 },
    { cat: "Ichimliklar", id: "d2", name: "Fanta 0.5 l", desc: "", price: 8000 },
    { cat: "Ichimliklar", id: "d3", name: "Sprite 0.5 l", desc: "", price: 8000 },
    { cat: "Ichimliklar", id: "d4", name: "Cola 1.5 l", desc: "", price: 14000 },
    { cat: "Ichimliklar", id: "d5", name: "Suv 0.5 l", desc: "", price: 4000 }
];
const P = new URLSearchParams(location.search), NAME = P.get("n") || "", ADDR = P.get("a") || "";
const API = (P.get("api") || (/^(localhost|127\.)/.test(location.hostname) ? "http://localhost:8080" : "")).replace(/\/$/, ""), EDIT = Number(P.get("e")) || 0;
const esc0 = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// Menyu botning serveridan olinadi (PUBLIC_URL berilgan bo'lsa); bo'lmasa yuqoridagi ro'yxat ishlatiladi
if (API) {
    try {
        const ac = new AbortController(); setTimeout(() => ac.abort(), 4000);
        const r = await fetch(API + "/api/menu", { signal: ac.signal, cache: "no-store" }), m = await r.json();
        if (r.ok && Array.isArray(m) && m.length) MENU = m.map(x => ({ ...x, cat: esc0(x.cat), name: esc0(x.name), desc: esc0(x.desc) }));
    } catch (e) { }
}
// Yetkazib berish hududlari (xuddi shunday botdan olinadi; narxni baribir bot qayta hisoblaydi)
let ZONES = [{ id: "z1", name: "Yaqin hududlar", fee: 10000, pickup: false }, { id: "z2", name: "O'rta masofa", fee: 15000, pickup: false }, { id: "z3", name: "Uzoq hududlar", fee: 20000, pickup: false }, { id: "z0", name: "Olib ketaman", fee: 0, pickup: true }];
if (API) { try { const r = await fetch(API + "/api/zones", { cache: "no-store" }), z = await r.json(); if (r.ok && Array.isArray(z) && z.length) ZONES = z.map(x => ({ ...x, raw: x.name, name: esc0(x.name) })); } catch (e) { } }
// Ish vaqti: do'kon yopiq bo'lsa buyurtma berib bo'lmaydi (bot baribir tekshiradi)
let SHOP = { open: true, message: "" };
if (API) { try { const r = await fetch(API + "/api/status", { cache: "no-store" }), s = await r.json(); if (r.ok) SHOP = s; } catch (e) { } }
ZONES.forEach(z => { z.raw = z.raw ?? z.name; });
let zone = ZONES.some(x => x.id === P.get("z")) ? P.get("z") : "";
const $ = id => document.getElementById(id), fmt = n => n.toLocaleString("ru-RU").replace(/\u00a0/g, " ") + " so'm";
const RM = matchMedia("(prefers-reduced-motion:reduce)").matches, G = (window.gsap && !RM) ? window.gsap : null;
const W = window.Telegram && Telegram.WebApp, tg = (W && W.platform && W.platform !== "unknown") ? W : null;
if (tg) { tg.ready(); tg.expand(); }
const cart = {}, tot = { v: 0 };
const total = () => MENU.reduce((s, m) => s + (cart[m.id] || 0) * m.price, 0), count = () => Object.values(cart).reduce((a, b) => a + b, 0);

$("hello").textContent = NAME ? `Salom, ${NAME}!` : "Xush kelibsiz!";
const cats = [...new Set(MENU.map(m => m.cat))];
$("chips").innerHTML = cats.map((c, i) => `<button data-i="${i}">${c}</button>`).join("");
$("list").innerHTML = cats.map((c, i) => `<section class="sec" id="c${i}"><h2 class="cat">${c}</h2>` + MENU.filter(m => m.cat === c).map(m =>
    `<div class="item${m.sold ? " sold" : ""}" id="i-${m.id}"><div class="t"><b>${m.name}</b>${m.desc ? `<small>${m.desc}</small>` : ""}<div class="price">${m.sold ? '<span class="soldtag">Tugadi</span>' : fmt(m.price)}</div></div>
 <div class="step"><button class="minus" data-id="${m.id}" data-d="-1" aria-label="Kamaytirish" hidden>−</button><span class="q" hidden>0</span><button class="plus" data-id="${m.id}" data-d="1" aria-label="${m.name} qo'shish"${m.sold || !SHOP.open ? " disabled" : ""}>+</button></div></div>`).join("") + `</section>`).join("");

function bar() {
    const c = count(), t = total();
    $("bar").classList.toggle("show", c > 0 && !$("menu").hidden);
    $("cnt").textContent = c;
    if (G) G.to(tot, { v: t, duration: .45, ease: "power2.out", onUpdate: () => $("total").textContent = fmt(Math.round(tot.v)) });
    else $("total").textContent = fmt(t);
}
function upd(id) {
    const n = cart[id] || 0, r = $("i-" + id), q = r.querySelector(".q"), mi = r.querySelector(".minus");
    q.hidden = mi.hidden = !n; q.textContent = n; r.classList.toggle("on", !!n);
    if (G) { G.fromTo(q, { scale: 1.7 }, { scale: 1, duration: .4, ease: "back.out(3)" }); G.fromTo(r.querySelector(".plus"), { scale: .75 }, { scale: 1, duration: .35, ease: "back.out(4)" }); }
    bar();
}
$("list").addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    const id = b.dataset.id; cart[id] = Math.max(0, (cart[id] || 0) + Number(b.dataset.d));
    if (!cart[id]) delete cart[id]; upd(id);
});
function show(v) {
    ["menu", "checkout", "done"].forEach(x => $(x).hidden = x !== v);
    bar(); scrollTo(0, 0);
    if (G) G.fromTo("#" + v, { opacity: 0, y: 26 }, { opacity: 1, y: 0, duration: .5, ease: "power3.out" });
    if (v === "done" && G) G.fromTo("#ck", { strokeDashoffset: 60 }, { strokeDashoffset: 0, duration: .7, delay: .25, ease: "power2.out" });
}
const ts = { v: 0 };
function renderSummary() {
    const z = ZONES.find(x => x.id === zone), fee = z ? z.fee : 0, t = total() + fee;
    $("summary").innerHTML = MENU.filter(m => cart[m.id]).map(m => `<div class="row"><span>${m.name}${m.desc && /Standart|Katta/.test(m.desc) ? " (" + m.desc.toLowerCase() + ")" : ""} × ${cart[m.id]}</span><b>${fmt(m.price * cart[m.id])}</b></div>`).join("")
        + (z ? `<div class="row"><span>${z.pickup ? "Olib ketish" : "Yetkazib berish"}</span><b>${z.pickup ? "bepul" : fmt(fee)}</b></div>` : "")
        + `<div class="row" style="font-size:20px"><b>Jami</b><b>${fmt(t)}</b></div>`;
    $("topl").textContent = z ? "Umumiy summa" : "Umumiy summa (yetkazishsiz)";
    if (G) G.to(ts, { v: t, duration: .45, ease: "power2.out", onUpdate: () => $("topv").textContent = fmt(Math.round(ts.v)) });
    else $("topv").textContent = fmt(t);
}
const norm = s => String(s ?? "").trim().toLowerCase();
let zact = -1;
function zItems(q) { const k = norm(q); return ZONES.filter(z => !k || norm(z.raw).includes(k)).sort((a, b) => (b.pickup - a.pickup) || a.raw.localeCompare(b.raw, "uz")); }
function openList() {
    const cur = ZONES.find(z => z.id === zone), v = $("zq").value;
    const items = zItems(cur && cur.raw === v ? "" : v);   // tanlangan hudud turganda butun ro'yxat ko'rinadi
    $("zlist").innerHTML = items.length ? items.map((z, i) => `<li role="option" data-z="${z.id}" class="${i === zact ? "act" : ""}"><span>${z.pickup ? "🏃 " : ""}${z.name}</span><b>${z.pickup ? "bepul" : fmt(z.fee)}</b></li>`).join("") : '<li class="none">Bunday hudud yo\'q</li>';
    $("zlist").hidden = false; $("zq").setAttribute("aria-expanded", "true");
    const a = $("zlist").querySelector(".act"); if (a) a.scrollIntoView({ block: "nearest" });
}
function closeList() { $("zlist").hidden = true; $("zq").setAttribute("aria-expanded", "false"); zact = -1; }
function pickZone(id) {
    zone = id; const z = ZONES.find(x => x.id === id); $("zq").value = z ? z.raw : "";
    closeList(); zoneInfo(); renderSummary();
    if (G && z) G.fromTo("#zinfo", { y: 8, opacity: 0 }, { y: 0, opacity: 1, duration: .35, ease: "power2.out" });
}
function renderZones() { $("zq").value = (ZONES.find(x => x.id === zone) || {}).raw || ""; closeList(); zoneInfo(); }
function zoneInfo() {
    const z = ZONES.find(x => x.id === zone), t = $("zq").value.trim(), el = $("zinfo");
    el.classList.remove("bad");
    if (z) el.innerHTML = z.pickup ? "🏃 Olib ketish: bepul" : `📍 ${z.name} gacha yetkazib berish: ${fmt(z.fee)}`;
    else if (t) { const n = zItems(t).length; el.classList.toggle("bad", !n); el.textContent = n ? "Ro'yxatdan hududni tanlang." : "❌ Bunday hudud yo'q."; }
    else el.textContent = "Hududni yozing yoki ro'yxatdan tanlang, yetkazib berish narxi shu yerda chiqadi.";
    const ai = $("addrinfo"); ai.hidden = !(ADDR && z && !z.pickup); ai.textContent = `Manzil: ${ADDR} (o'zgartirish uchun botda /yangilash)`;
}
$("zq").addEventListener("input", () => {
    const t = norm($("zq").value), ex = ZONES.find(z => norm(z.raw) === t);
    zone = t && ex ? ex.id : ""; zact = -1; openList(); zoneInfo(); renderSummary();
});
$("zq").addEventListener("focus", openList);
$("zq").addEventListener("click", openList);
$("ztog").addEventListener("click", () => { if ($("zlist").hidden) openList(); else closeList(); });
$("zlist").addEventListener("mousedown", e => e.preventDefault());
$("zlist").addEventListener("click", e => { const li = e.target.closest("li[data-z]"); if (li) pickZone(li.dataset.z); });
$("zq").addEventListener("keydown", e => {
    const items = zItems($("zq").value);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); zact = Math.max(0, Math.min(items.length - 1, zact + (e.key === "ArrowDown" ? 1 : -1))); openList(); }
    else if (e.key === "Enter") { e.preventDefault(); const z = items[zact >= 0 ? zact : (items.length === 1 ? 0 : -1)]; if (z) pickZone(z.id); }
    else if (e.key === "Escape") closeList();
});
document.addEventListener("click", e => { if (!e.target.closest("#combo")) closeList(); });
$("go").onclick = () => {
    renderZones(); renderSummary(); show("checkout");
    if (G) G.from("#summary .row", { x: -24, opacity: 0, stagger: .07, duration: .4, delay: .1, ease: "power2.out" });
};
$("back").onclick = () => show("menu");
$("again").onclick = () => { for (const k in cart) { delete cart[k]; upd(k); } show("menu"); };
$("send").onclick = () => {
    if (!SHOP.open) { $("err").textContent = SHOP.message || "Hozir buyurtma qabul qilinmaydi."; return; }
    const zn = ZONES.find(x => x.id === zone);
    if (!zn) { const t = $("zq").value.trim(); $("err").textContent = t ? `Bunday hudud yo'q: «${t}». Ro'yxatdan tanlang.` : "Yetkazib berish hududini tanlang."; if (G) G.fromTo("#zq", { x: -8 }, { x: 0, duration: .5, ease: "elastic.out(1,.3)" }); return; }
    const address = "";  // manzilni bot ro'yxatdan o'tishdagi ma'lumotdan oladi
    $("err").textContent = "";
    const order = {
        address, zone, comment: $("note").value.trim(), pay, edit: EDIT, total: total(),
        items: MENU.filter(m => cart[m.id]).map(m => ({ id: m.id, name: m.name + (/Standart|Katta/.test(m.desc) ? " (" + m.desc.toLowerCase() + ")" : ""), qty: cart[m.id], price: m.price }))
    };
    if (tg && tg.sendData) tg.sendData(JSON.stringify(order)); else { console.log(order); show("done"); }
};

// To'lov turi
let pay = "cash";
const hints = { cash: "Kuryerga naqd pul to'laysiz.", card: "Buyurtmadan keyin bot karta raqamini yuboradi. Pulni o'tkazib, chekni botga yuboring." };
$("payhint").textContent = hints.cash;
$("pay").addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    pay = b.dataset.p;
    [...$("pay").children].forEach(x => { const on = x === b; x.classList.toggle("on", on); x.setAttribute("aria-checked", on); });
    $("payhint").textContent = hints[pay];
    if (G) G.fromTo(b, { scale: .92 }, { scale: 1, duration: .4, ease: "back.out(3)" });
});

// Bo'lim tugmalari
const chipBtns = [...document.querySelectorAll("#chips button")];
chipBtns.forEach(b => b.onclick = () => $("c" + b.dataset.i).scrollIntoView({ behavior: RM ? "auto" : "smooth" }));
const so = new IntersectionObserver(es => es.forEach(en => {
    if (!en.isIntersecting) return;
    chipBtns.forEach(b => b.classList.toggle("on", b.dataset.i === en.target.id.slice(1)));
    const a = chipBtns.find(b => b.classList.contains("on"));
    if (a) $("chips").scrollTo({ left: a.offsetLeft - 24, behavior: "smooth" });
}), { rootMargin: "-30% 0px -65% 0px" });
document.querySelectorAll(".sec").forEach(s => so.observe(s));

// Animatsiyalar (GSAP)
if (G) {
    G.set(".item,.cat", { opacity: 0, y: 30 });
    G.timeline({ defaults: { ease: "power3.out" } })
        .from(".logo", { scale: .4, rotate: -14, opacity: 0, duration: 1, ease: "elastic.out(1,.55)" })
        .from(".hero .t", { y: 18, opacity: 0, stagger: .1, duration: .5 }, "-=.6")
        .from("#chips button", { y: -14, opacity: 0, stagger: .05, duration: .35 }, "-=.3");
    G.to(".logo", { y: -6, duration: 1.7, repeat: -1, yoyo: true, ease: "sine.inOut", delay: 1.2 });
    const io = new IntersectionObserver(es => es.forEach(en => {
        if (en.isIntersecting) { G.to(en.target, { opacity: 1, y: 0, duration: .55, ease: "power3.out" }); io.unobserve(en.target); }
    }), { threshold: .12 });
    document.querySelectorAll(".item,.cat").forEach(el => io.observe(el));
}
if (!SHOP.open) { $("closedbar").hidden = false; $("closedbar").textContent = SHOP.message || "⏰ Hozir buyurtma qabul qilinmaydi."; }
// Tahrirlash rejimi: mavjud buyurtma savatga oldindan yuklanadi
if (EDIT) {
    for (const part of (P.get("c") || "").split(",")) { const [id, n] = part.split(":"); if (MENU.some(m => m.id === id && !m.sold) && +n > 0) { cart[id] = +n; upd(id); } }
    $("editbar").hidden = false; $("editbar").textContent = "✏️ Buyurtma #" + EDIT + " tahrirlanmoqda";
    $("send").textContent = "O'zgarishlarni saqlash";
}