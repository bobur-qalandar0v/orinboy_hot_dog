const MENU = [
    {
        cat: "Sosiskali",
        id: "s2",
        name: "2x sosiska",
        desc: "Faqat sosiska va chimchi",
        price: 18000,
    },
    {
        cat: "Sosiskali",
        id: "s3",
        name: "3x sosiska",
        desc: "Faqat sosiska va chimchi",
        price: 22000,
    },
    {
        cat: "Sosiskali",
        id: "s4",
        name: "4x sosiska",
        desc: "Faqat sosiska va chimchi",
        price: 25000,
    },
    {
        cat: "Sosiskali",
        id: "s5",
        name: "5x sosiska",
        desc: "Faqat sosiska va chimchi",
        price: 28000,
    },
    {
        cat: "Ijjonli",
        id: "i1",
        name: "2x sosiska + ijjon",
        desc: "",
        price: 28000,
    },
    {
        cat: "Ijjonli",
        id: "i2",
        name: "2x sosiska + 2x ijjon",
        desc: "",
        price: 35000,
    },
    {
        cat: "Ijjonli",
        id: "i3",
        name: "3x sosiska + ijjon",
        desc: "",
        price: 35000,
    },
    {
        cat: "Ijjonli",
        id: "i4",
        name: "3x sosiska + 2x ijjon",
        desc: "",
        price: 40000,
    },
    {
        cat: "Ijjonli",
        id: "i5",
        name: "2x sosiska + ijjon + sir",
        desc: "",
        price: 35000,
    },
    {
        cat: "Cheezdog",
        id: "c1",
        name: "Cheezdog",
        desc: "Standart",
        price: 35000,
    },
    {
        cat: "Cheezdog",
        id: "c2",
        name: "Cheezdog",
        desc: "Katta",
        price: 40000,
    },
    {
        cat: "Tushonkali",
        id: "t2",
        name: "Tushonkali 2x sosiska",
        desc: "",
        price: 35000,
    },
    {
        cat: "Tushonkali",
        id: "t3",
        name: "Tushonkali 3x sosiska",
        desc: "",
        price: 40000,
    },
    {
        cat: "Toshkent xot dog",
        id: "tk1",
        name: "Toshkent xot dog",
        desc: "Go'sht assorti, standart",
        price: 30000,
    },
    {
        cat: "Toshkent xot dog",
        id: "tk2",
        name: "Toshkent xot dog",
        desc: "Go'sht assorti, katta",
        price: 35000,
    },
    {
        cat: "Mangalga xot dog",
        id: "m1",
        name: "Mangalga xot dog sirniy katlet",
        desc: "",
        price: 45000,
    },
    {
        cat: "Mangalga xot dog",
        id: "m2",
        name: "Mangalga xot dog shashlikli",
        desc: "",
        price: 35000,
    },
    {
        cat: "Ichimliklar",
        id: "d1",
        name: "Cola 0.5 l",
        desc: "",
        price: 8000,
    },
    {
        cat: "Ichimliklar",
        id: "d2",
        name: "Fanta 0.5 l",
        desc: "",
        price: 8000,
    },
    {
        cat: "Ichimliklar",
        id: "d3",
        name: "Sprite 0.5 l",
        desc: "",
        price: 8000,
    },
    {
        cat: "Ichimliklar",
        id: "d4",
        name: "Cola 1.5 l",
        desc: "",
        price: 14000,
    },
    {
        cat: "Ichimliklar",
        id: "d5",
        name: "Suv 0.5 l",
        desc: "",
        price: 4000,
    },
];
const P = new URLSearchParams(location.search),
    NAME = P.get("n") || "",
    ADDR = P.get("a") || "";
const $ = (id) => document.getElementById(id),
    fmt = (n) =>
        n.toLocaleString("ru-RU").replace(/\u00a0/g, " ") + " so'm";
const RM = matchMedia("(prefers-reduced-motion:reduce)").matches,
    G = window.gsap && !RM ? window.gsap : null;
const W = window.Telegram && Telegram.WebApp,
    tg = W && W.platform && W.platform !== "unknown" ? W : null;
if (tg) {
    tg.ready();
    tg.expand();
}
const cart = {},
    tot = { v: 0 };
const total = () =>
    MENU.reduce((s, m) => s + (cart[m.id] || 0) * m.price, 0),
    count = () => Object.values(cart).reduce((a, b) => a + b, 0);

$("hello").textContent = NAME ? `Salom, ${NAME}!` : "Xush kelibsiz!";
const cats = [...new Set(MENU.map((m) => m.cat))];
$("chips").innerHTML = cats
    .map((c, i) => `<button data-i="${i}">${c}</button>`)
    .join("");
$("list").innerHTML = cats
    .map(
        (c, i) =>
            `<section class="sec" id="c${i}"><h2 class="cat">${c}</h2>` +
            MENU.filter((m) => m.cat === c)
                .map(
                    (m) =>
                        `<div class="item" id="i-${m.id}"><div class="t"><b>${m.name}</b>${m.desc ? `<small>${m.desc}</small>` : ""}<div class="price">${fmt(m.price)}</div></div>
 <div class="step"><button class="minus" data-id="${m.id}" data-d="-1" aria-label="Kamaytirish" hidden>−</button><span class="q" hidden>0</span><button class="plus" data-id="${m.id}" data-d="1" aria-label="${m.name} qo'shish">+</button></div></div>`,
                )
                .join("") +
            `</section>`,
    )
    .join("");

function bar() {
    const c = count(),
        t = total();
    $("bar").classList.toggle("show", c > 0 && !$("menu").hidden);
    $("cnt").textContent = c;
    if (G)
        G.to(tot, {
            v: t,
            duration: 0.45,
            ease: "power2.out",
            onUpdate: () => ($("total").textContent = fmt(Math.round(tot.v))),
        });
    else $("total").textContent = fmt(t);
}
function upd(id) {
    const n = cart[id] || 0,
        r = $("i-" + id),
        q = r.querySelector(".q"),
        mi = r.querySelector(".minus");
    q.hidden = mi.hidden = !n;
    q.textContent = n;
    r.classList.toggle("on", !!n);
    if (G) {
        G.fromTo(
            q,
            { scale: 1.7 },
            { scale: 1, duration: 0.4, ease: "back.out(3)" },
        );
        G.fromTo(
            r.querySelector(".plus"),
            { scale: 0.75 },
            { scale: 1, duration: 0.35, ease: "back.out(4)" },
        );
    }
    bar();
}
$("list").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    const id = b.dataset.id;
    cart[id] = Math.max(0, (cart[id] || 0) + Number(b.dataset.d));
    if (!cart[id]) delete cart[id];
    upd(id);
});
function show(v) {
    ["menu", "checkout", "done"].forEach((x) => ($(x).hidden = x !== v));
    bar();
    scrollTo(0, 0);
    if (G)
        G.fromTo(
            "#" + v,
            { opacity: 0, y: 26 },
            { opacity: 1, y: 0, duration: 0.5, ease: "power3.out" },
        );
    if (v === "done" && G)
        G.fromTo(
            "#ck",
            { strokeDashoffset: 60 },
            {
                strokeDashoffset: 0,
                duration: 0.7,
                delay: 0.25,
                ease: "power2.out",
            },
        );
}
$("go").onclick = () => {
    $("summary").innerHTML =
        MENU.filter((m) => cart[m.id])
            .map(
                (m) =>
                    `<div class="row"><span>${m.name}${m.desc && /Standart|Katta/.test(m.desc) ? " (" + m.desc.toLowerCase() + ")" : ""} × ${cart[m.id]}</span><b>${fmt(m.price * cart[m.id])}</b></div>`,
            )
            .join("") +
        `<div class="row" style="font-size:20px"><b>Jami</b><b>${fmt(total())}</b></div>`;
    $("addr").value = $("addr").value || ADDR;
    show("checkout");
    if (G)
        G.from("#summary .row", {
            x: -24,
            opacity: 0,
            stagger: 0.07,
            duration: 0.4,
            delay: 0.1,
            ease: "power2.out",
        });
};
$("back").onclick = () => show("menu");
$("again").onclick = () => {
    for (const k in cart) {
        delete cart[k];
        upd(k);
    }
    show("menu");
};
$("send").onclick = () => {
    const address = $("addr").value.trim();
    if (address.length < 3) {
        $("err").textContent = "Yetkazish manzilini kiriting.";
        if (G)
            G.fromTo(
                "#addr",
                { x: -8 },
                { x: 0, duration: 0.5, ease: "elastic.out(1,.3)" },
            );
        return;
    }
    $("err").textContent = "";
    const order = {
        address,
        comment: $("note").value.trim(),
        pay,
        total: total(),
        items: MENU.filter((m) => cart[m.id]).map((m) => ({
            id: m.id,
            name:
                m.name +
                (/Standart|Katta/.test(m.desc)
                    ? " (" + m.desc.toLowerCase() + ")"
                    : ""),
            qty: cart[m.id],
            price: m.price,
        })),
    };
    if (tg && tg.sendData) tg.sendData(JSON.stringify(order));
    else {
        console.log(order);
        show("done");
    }
};

// To'lov turi
let pay = "cash";
const hints = {
    cash: "Kuryerga naqd pul to'laysiz.",
    card: "Buyurtmadan keyin bot karta raqamini yuboradi. Pulni o'tkazib, chekni botga yuboring.",
};
$("payhint").textContent = hints.cash;
$("pay").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    pay = b.dataset.p;
    [...$("pay").children].forEach((x) => {
        const on = x === b;
        x.classList.toggle("on", on);
        x.setAttribute("aria-checked", on);
    });
    $("payhint").textContent = hints[pay];
    if (G)
        G.fromTo(
            b,
            { scale: 0.92 },
            { scale: 1, duration: 0.4, ease: "back.out(3)" },
        );
});

// Bo'lim tugmalari
const chipBtns = [...document.querySelectorAll("#chips button")];
chipBtns.forEach(
    (b) =>
    (b.onclick = () =>
        $("c" + b.dataset.i).scrollIntoView({
            behavior: RM ? "auto" : "smooth",
        })),
);
const so = new IntersectionObserver(
    (es) =>
        es.forEach((en) => {
            if (!en.isIntersecting) return;
            chipBtns.forEach((b) =>
                b.classList.toggle("on", b.dataset.i === en.target.id.slice(1)),
            );
            const a = chipBtns.find((b) => b.classList.contains("on"));
            if (a)
                $("chips").scrollTo({
                    left: a.offsetLeft - 24,
                    behavior: "smooth",
                });
        }),
    { rootMargin: "-30% 0px -65% 0px" },
);
document.querySelectorAll(".sec").forEach((s) => so.observe(s));

// Animatsiyalar (GSAP)
if (G) {
    G.set(".item,.cat", { opacity: 0, y: 30 });
    G.timeline({ defaults: { ease: "power3.out" } })
        .from(".logo", {
            scale: 0.4,
            rotate: -14,
            opacity: 0,
            duration: 1,
            ease: "elastic.out(1,.55)",
        })
        .from(
            ".hero .t",
            { y: 18, opacity: 0, stagger: 0.1, duration: 0.5 },
            "-=.6",
        )
        .from(
            "#chips button",
            { y: -14, opacity: 0, stagger: 0.05, duration: 0.35 },
            "-=.3",
        );
    G.to(".logo", {
        y: -6,
        duration: 1.7,
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut",
        delay: 1.2,
    });
    const io = new IntersectionObserver(
        (es) =>
            es.forEach((en) => {
                if (en.isIntersecting) {
                    G.to(en.target, {
                        opacity: 1,
                        y: 0,
                        duration: 0.55,
                        ease: "power3.out",
                    });
                    io.unobserve(en.target);
                }
            }),
        { threshold: 0.12 },
    );
    document.querySelectorAll(".item,.cat").forEach((el) => io.observe(el));
}