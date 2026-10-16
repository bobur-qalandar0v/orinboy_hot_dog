const $ = (s) => document.querySelector(s);
const fmt = (n) =>
    Number(n || 0)
        .toLocaleString("ru-RU")
        .replace(/\u00a0/g, " ") + " so'm";
const esc = (s) =>
    String(s ?? "").replace(
        /[&<>"']/g,
        (c) =>
            ({
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#39;",
            })[c],
    );
const ST = {
    new: "Yangi",
    cooking: "Tayyorlanmoqda",
    delivering: "Yo'lda",
    done: "Yetkazildi",
    cancelled: "Bekor qilingan",
};
const MON = [
    "yan",
    "fev",
    "mar",
    "apr",
    "may",
    "iyn",
    "iyl",
    "avg",
    "sen",
    "okt",
    "noy",
    "dek",
];
let S = null,
    U = [],
    O = [],
    filter = "all",
    tab = "dash",
    q = "";

async function api(u, o) {
    const r = await fetch(u, o);
    if (!r.ok) throw new Error(r.status);
    return r.json();
}
function toast(t) {
    const e = $("#toast");
    e.textContent = t;
    e.classList.add("show");
    clearTimeout(toast.t);
    toast.t = setTimeout(() => e.classList.remove("show"), 2600);
}
const stat = (l, v, s = "") =>
    `<div class="card stat"><div class="l">${l}</div><div class="v">${v}</div><div class="s">${s}</div></div>`;

function dash() {
    const d = S.daily,
        mx = Math.max(1, ...d.map((x) => x.revenue)),
        hm = Math.max(1, ...S.hours);
    const pm = Math.max(1, ...S.products.map((p) => p.qty)),
        tot = S.pay.cash + S.pay.card || 1;
    const cp = Math.round((S.pay.cash / tot) * 100);
    const top = U.filter((u) => u.orders > 0).slice(0, 5);
    $("#dash").innerHTML = `
  <div class="grid cards">
    ${stat("Bugun", S.today_orders + " ta", fmt(S.today_revenue))}
    ${stat("Jami tushum", fmt(S.revenue), S.orders + " ta buyurtma")}
    ${stat("O'rtacha chek", fmt(S.avg))}
    ${stat("Mijozlar", S.users + " ta", "ro'yxatdan o'tgan")}
    ${stat("Yangi buyurtma", S.new + " ta", "javob kutmoqda")}
  </div>
  <div class="grid two">
    <div class="card"><h3>So'nggi 14 kun (tushum)</h3><div class="bars">${d
            .map((x) => {
                const dt = x.d.split("-");
                return `<div class="c" title="${x.d}: ${x.orders} ta, ${fmt(x.revenue)}"><div class="bar" style="height:${(x.revenue / mx) * 100}%"></div><div class="lbl">${+dt[2]}</div></div>`;
            })
            .join("")}</div></div>
    <div class="card"><h3>Qaysi soatda ko'p buyurtma</h3><div class="bars">${S.hours.map((h, i) => `<div class="c" title="${i}:00 — ${h} ta"><div class="bar m" style="height:${(h / hm) * 100}%"></div><div class="lbl">${i % 3 === 0 ? i : ""}</div></div>`).join("")}</div></div>
  </div>
  <div class="grid two">
    <div class="card"><h3>Eng ko'p buyurtma qilingan xot-doglar</h3>${S.products.length
            ? S.products
                .slice(0, 8)
                .map(
                    (p) =>
                        `<div class="hb"><div class="n" title="${esc(p.name)}">${esc(p.name)}</div><div class="t"><i style="width:${(p.qty / pm) * 100}%"></i></div><div><b>${p.qty}</b> <span class="muted">ta</span></div></div>`,
                )
                .join("")
            : "<p class=\"muted\">Hozircha ma'lumot yo'q.</p>"
        }</div>
    <div class="card"><h3>To'lov turi</h3>
      <div class="split"><i style="width:${cp}%;background:var(--mustard)"></i><i style="width:${100 - cp}%;background:var(--blue)"></i></div>
      <div>💵 Naqd: <b>${S.pay.cash}</b> ta (${cp}%)</div><div>💳 Karta: <b>${S.pay.card}</b> ta (${100 - cp}%)</div>
      <h3 style="margin-top:18px">Eng faol mijozlar</h3>
      ${top.length ? top.map((u, i) => `<div class="hb" style="grid-template-columns:24px 1fr auto"><b>${i + 1}</b><div class="n">${esc(u.name)}</div><div><b>${u.orders}</b> <span class="muted">ta · ${fmt(u.spent)}</span></div></div>`).join("") : "<p class=\"muted\">Hozircha ma'lumot yo'q.</p>"}
    </div>
  </div>
  <div class="card"><h3>Mahsulotlar bo'yicha tushum</h3><div class="tablewrap"><table><tr><th>Mahsulot</th><th>Sotilgan</th><th>Tushum</th></tr>
  ${S.products.map((p) => `<tr><td>${esc(p.name)}</td><td>${p.qty} ta</td><td>${fmt(p.revenue)}</td></tr>`).join("") || '<tr><td colspan="3" class="muted">Hozircha ma\'lumot yo\'q.</td></tr>'}</table></div></div>`;
}

function ago(s) {
    if (!s) return "—";
    const d = new Date(s.replace(" ", "T"));
    return `${d.getDate()} ${MON[d.getMonth()]}, ${s.slice(11, 16)}`;
}

function users() {
    const k = q.toLowerCase(),
        L = U.filter(
            (u) =>
                !k ||
                (u.name + " " + u.phone + " " + u.address)
                    .toLowerCase()
                    .includes(k),
        );
    $("#users").innerHTML =
        `<input type="search" id="qs" placeholder="Ism, telefon yoki manzil bo'yicha qidirish" value="${esc(q)}">
  <div class="card"><div class="tablewrap"><table><tr><th>Mijoz</th><th>Telefon</th><th>Manzil</th><th>Buyurtmalar</th><th>Jami summa</th><th>Oxirgi buyurtma</th></tr>
  ${L.map((u) => `<tr><td><b>${esc(u.name)}</b></td><td>${esc(u.phone)}</td><td>${esc(u.address)}</td><td><b>${u.orders}</b> ta</td><td>${fmt(u.spent)}</td><td>${ago(u.last)}</td></tr>`).join("") || '<tr><td colspan="6" class="muted">Mijoz topilmadi.</td></tr>'}</table></div></div>`;
    const el = $("#qs");
    el.focus();
    el.setSelectionRange(q.length, q.length);
    el.oninput = () => {
        q = el.value;
        users();
    };
}

function orders() {
    const L = O.filter((o) => filter === "all" || o.status === filter);
    const cnt = (s) =>
        O.filter((o) => s === "all" || o.status === s).length;
    $("#orders").innerHTML =
        `<div class="chips">${["all", ...Object.keys(ST)].map((s) => `<button data-f="${s}" class="${filter === s ? "on" : ""}">${s === "all" ? "Hammasi" : ST[s]} (${cnt(s)})</button>`).join("")}</div>` +
        (L.map(
            (
                o,
            ) => `<div class="card order"><div class="oh"><b>#${o.id}</b><span class="tag s-${o.status}">${ST[o.status]}</span><span class="tag">${o.pay === "card" ? "💳 Karta" : "💵 Naqd"}</span><span class="muted">${ago(o.created)}</span><b style="margin-left:auto">${fmt(o.total)}</b></div>
   <div><b>${esc(o.name || "Noma'lum")}</b> · ${esc(o.phone || "")}<br><span class="muted">📍 ${esc(o.address)}</span>${o.comment ? `<br><span class="muted">💬 ${esc(o.comment)}</span>` : ""}</div>
   <ul class="oi">${o.items.map((i) => `<li>${esc(i.name)} × ${i.qty}</li>`).join("")}</ul>
   <div class="act">${["cooking", "delivering", "done", "cancelled"].map((s) => `<button data-id="${o.id}" data-s="${s}" ${o.status === s ? "disabled" : ""}>${ST[s]}</button>`).join("")}</div></div>`,
        ).join("") || '<p class="muted">Buyurtma yo\'q.</p>');
}

async function load() {
    try {
        [S, U, O] = await Promise.all([
            api("/api/stats"),
            api("/api/users"),
            api("/api/orders"),
        ]);
    } catch (e) {
        toast("Ma'lumot olinmadi");
        return;
    }
    const b = $("#newb");
    b.hidden = !S.new;
    b.textContent = S.new;
    document.title = (S.new ? `(${S.new}) ` : "") + "O'rinboy Admin";
    if (tab === "dash") dash();
    else if (tab === "orders") orders();
    else if (document.activeElement.id !== "qs") users();
}
$("#nav").onclick = (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    tab = b.dataset.t;
    [...$("#nav").children].forEach((x) =>
        x.classList.toggle("on", x === b),
    );
    ["dash", "orders", "users"].forEach(
        (t) => ($("#" + t).hidden = t !== tab),
    );
    load();
};
$("#orders").onclick = async (e) => {
    const f = e.target.closest("[data-f]");
    if (f) {
        filter = f.dataset.f;
        orders();
        return;
    }
    const b = e.target.closest("[data-s]");
    if (!b) return;
    if (
        b.dataset.s === "cancelled" &&
        !confirm("Buyurtmani bekor qilasizmi? Mijozga xabar ketadi.")
    )
        return;
    try {
        const r = await api(`/api/orders/${b.dataset.id}/status`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-Admin": "1" },
            body: JSON.stringify({ status: b.dataset.s }),
        });
        toast(
            r.notified
                ? "Holat saqlandi, mijozga xabar yuborildi"
                : "Holat saqlandi (mijozga xabar yuborilmadi)",
        );
        load();
    } catch (err) {
        toast("Xatolik yuz berdi");
    }
};
load();
setInterval(load, 30000);