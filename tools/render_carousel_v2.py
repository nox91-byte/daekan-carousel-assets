#!/usr/bin/env python3
"""
Daekan Carousel renderer v2 — desain 100% buatan sendiri (tanpa foto stok / aset pihak ketiga).

Pemakaian:
    python3 tools/render_carousel_v2.py spec.json OUT_DIR

Spec:
{
  "theme": "paper",                      # (opsional) "paper" (krem, default) — slide isi selalu krem; cover & cta selalu gelap
  "slides": [
    {"type": "cover", "kicker": "LAGI RAME", "headline": "GAME JAGA WARUNG INI BIKIN *CURHAT PANJANG*:", "art": ART},
    {"type": "note",  "headline": "Namanya *Warung Life Simulator*.", "body": "Subline pendek.", "doodle": "star"},
    {"type": "stat",  "big": "3", "label": "PELAJARAN", "headline": "Satu kalimat penjelas", "body": "Subline"},
    {"type": "ui",    "headline": "Hari-harinya *ya begini*", "card_title": "Buku Utang", "rows": [{"icon":"book","title":"...","sub":"...","tag":"Dicatat","tone":"ok|warn|bad"}], "caption": "Ilustrasi mekanik game"},
    {"type": "grid",  "headline": "Simpan bagian ini", "items": [{"icon":"book","text":"..."}, ...]},
    {"type": "cta",   "headline": "Simpan ini biar *nggak ketinggalan*", "body": "...", "pill": "Simpan & follow @daekan.app"}
  ]
}

ART (khusus cover, opsional) — pilih salah satu:
  {"kind":"phone","title":"Hari ke-12","meta":"Rp 184rb","scene":"<fragmen SVG digambar sendiri, koordinat 0..384 x 0..560>"}
      -> bingkai HP siap pakai; kamu hanya menggambar ISI LAYAR (ilustrasi konsep, BUKAN screenshot / logo / karakter pihak ketiga)
  {"kind":"tiles","icons":["coin","chart","clock"],"labels":["Utang","Untung","Waktu"]}
      -> tiga ubin ikon besar (aman untuk topik yang tidak cocok digambar sebagai layar HP)
  {"kind":"none"} -> cover poster tipografi murni
  {"kind":"svg","svg":"<svg width=1080 height=800 ...>","tilt":-6,"dy":70} -> SVG bebas (lanjutan)

Icon yang tersedia (untuk ui.rows[].icon dan grid.items[].icon):
  coin, book, store, wave, qr, bolt, chart, heart, clock, check, star, phone, tag

Doodle (note.doodle): star, squiggle, arrow, circle, spark, none (default: arrow swipe di semua slide non-terakhir)

Aturan:
- Frasa aksen ditandai *bintang* (maks 1 per headline) -> disorot oranye.
- Slide pertama "cover", terakhir "cta". Counter n/total otomatis di slide isi.
- Teks otomatis dikecilkan (min 70%) kalau overflow; WARNING kalau tetap tidak muat -> perpendek teks.
- Logo dari brand/daekan-logo.png (jangan diganti); di slide krem logo ditaruh di lencana gelap.
Output: slide_01.png ... slide_NN.png (1080x1350) + ringkasan JSON.
"""
import html
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE) if os.path.basename(HERE) == "tools" else HERE
LOGO = os.path.join(REPO, "brand", "daekan-logo.png")
if not os.path.exists(LOGO):
    LOGO = os.path.join(HERE, "daekan-logo.png")
FONTS = os.path.join(HERE, "fonts")
import glob
CHROMIUM_CANDIDATES = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"), reverse=True)


def furl(p):
    return "file://" + os.path.abspath(p)


FONT_CSS = f"""
@font-face{{font-family:'Gochi';src:url('{furl(FONTS)}/gochi.woff2') format('woff2')}}
@font-face{{font-family:'Patrick';src:url('{furl(FONTS)}/patrick.woff2') format('woff2')}}
@font-face{{font-family:'Anton';src:url('{furl(FONTS)}/anton.woff2') format('woff2')}}
@font-face{{font-family:'Jakarta';font-weight:500;src:url('{furl(FONTS)}/jakarta500.woff2') format('woff2')}}
@font-face{{font-family:'Jakarta';font-weight:800;src:url('{furl(FONTS)}/jakarta800.woff2') format('woff2')}}
"""

CSS = FONT_CSS + """
*{margin:0;padding:0;box-sizing:border-box}
:root{--k:1;--ink:#17130F;--paper:#F3EADB;--paper2:#EADFCB;--or:#F97316;--ord:#E2600A;--muted:#6E6354;--dark:#0A0A0A}
body{width:1080px;height:1350px;overflow:hidden;position:relative;font-family:'Jakarta',sans-serif;color:var(--ink)}
.paper{background:var(--paper)}
.paper::before{content:'';position:absolute;inset:0;opacity:.5;pointer-events:none;
 background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 .45  0 0 0 0 .35  0 0 0 0 .2  0 0 0 .09 0'/></filter><rect width='300' height='300' filter='url(%23n)'/></svg>")}
.dark{background:var(--dark);color:#fff}
.wrap{position:absolute;inset:0;padding:78px 84px 84px;display:flex;flex-direction:column}
.top{display:flex;justify-content:space-between;align-items:center;flex:none;position:relative;z-index:3}
.badge{background:var(--dark);border-radius:999px;padding:14px 26px;display:inline-flex;align-items:center}
.badge img{height:34px;display:block}
.logo{height:44px;display:block}
.counter{font-family:'Gochi';font-size:44px;color:var(--muted)}
.dark .counter{color:#8A8A8A}
em{font-style:normal}
.hl-hand em{background:linear-gradient(transparent 52%,rgba(249,115,22,.40) 52%,rgba(249,115,22,.40) 90%,transparent 90%);color:var(--ink);padding:0 6px;margin:0 -6px;-webkit-box-decoration-break:clone;box-decoration-break:clone}
.hl-poster em{color:var(--or)}
/* cover */
.cover .wrap{padding-bottom:0}
.kicker{align-self:flex-start;font-family:'Jakarta';font-weight:800;font-size:28px;letter-spacing:4px;color:var(--or);border:3px solid var(--or);border-radius:999px;padding:12px 28px;margin-top:46px;flex:none;position:relative;z-index:3}
.cover .hl-poster{font-family:'Anton';font-size:calc(132px * var(--k));line-height:1.02;text-transform:uppercase;margin-top:34px;flex:none;position:relative;z-index:3;letter-spacing:.5px}
.glow{position:absolute;right:-260px;top:-200px;width:900px;height:900px;border-radius:50%;background:radial-gradient(circle,rgba(249,115,22,.55),rgba(249,115,22,0) 65%)}
.dots{position:absolute;inset:0;opacity:.5;background-image:radial-gradient(rgba(255,255,255,.13) 2px,transparent 2.5px);background-size:44px 44px}
.art{position:absolute;left:0;right:0;bottom:0;display:flex;justify-content:center;z-index:2}
.art svg{display:block}
/* note */
.note .mid{flex:1;display:flex;flex-direction:column;justify-content:center;position:relative;z-index:2;padding-bottom:40px}
.note .hl-hand{font-family:'Gochi';font-size:calc(124px * var(--k));line-height:1.16;letter-spacing:-.5px}
.note .sub{font-family:'Patrick';font-size:calc(52px * var(--k));line-height:1.32;color:var(--muted);margin-top:44px}
.doodle{position:absolute;right:70px;bottom:90px;z-index:1}
.swipe{position:absolute;right:84px;bottom:88px;z-index:3;display:flex;align-items:center;gap:14px;font-family:'Gochi';font-size:44px;color:var(--ord)}
/* stat */
.stat .mid{flex:1;display:flex;flex-direction:column;justify-content:center;position:relative;z-index:2}
.stat .big{font-family:'Anton';font-size:calc(420px * var(--k));line-height:.9;color:var(--or)}
.stat .label{font-family:'Anton';font-size:calc(96px * var(--k));line-height:1;text-transform:uppercase;margin-top:10px}
.stat .hl-hand{font-family:'Gochi';font-size:calc(74px * var(--k));line-height:1.2;margin-top:44px}
.stat .sub{font-family:'Patrick';font-size:calc(48px * var(--k));line-height:1.3;color:var(--muted);margin-top:26px}
/* ui */
.ui .hl-hand{font-family:'Gochi';font-size:calc(96px * var(--k));line-height:1.12;margin-top:54px;flex:none}
.uimid{flex:1;display:flex;flex-direction:column;justify-content:center;padding-bottom:40px;min-height:0}
.phone{margin-top:0;background:#fff;border-radius:44px;box-shadow:0 26px 60px rgba(60,40,10,.22),0 0 0 14px #17130F;overflow:hidden;flex:none;position:relative;z-index:2}
.phone .bar{background:var(--dark);color:#fff;padding:26px 36px;display:flex;justify-content:space-between;align-items:center;font-weight:800;font-size:32px}
.phone .bar span:last-child{color:var(--or);font-size:28px}
.row{display:flex;align-items:center;gap:26px;padding:38px 36px;border-bottom:2px solid #EFE7D8}
.row:last-child{border-bottom:none}
.ico{flex:none;width:84px;height:84px;border-radius:24px;background:#FFF1E4;display:flex;align-items:center;justify-content:center}
.row .t{flex:1}
.row .t b{display:block;font-weight:800;font-size:calc(36px * var(--k));line-height:1.2}
.row .t i{display:block;font-style:normal;font-weight:500;font-size:calc(28px * var(--k));color:var(--muted);margin-top:4px}
.tag{flex:none;font-weight:800;font-size:26px;border-radius:999px;padding:12px 24px}
.tag.ok{background:#DDF3E3;color:#17703A}.tag.warn{background:#FFE9C7;color:#9A5A00}.tag.bad{background:#FFD9D4;color:#B3261E}
.caption{font-family:'Patrick';font-size:32px;color:var(--muted);margin-top:40px;text-align:center;flex:none}
/* grid */
.grid .stamp{align-self:flex-start;font-family:'Anton';font-size:40px;letter-spacing:5px;color:var(--ord);border:5px solid var(--ord);border-radius:14px;padding:10px 26px;transform:rotate(-4deg);margin-top:54px;flex:none}
.grid .hl-hand{font-family:'Gochi';font-size:calc(100px * var(--k));line-height:1.12;margin-top:34px;flex:none}
.cards{display:flex;flex-direction:column;gap:30px;margin-top:40px;flex:1;min-height:0;justify-content:center;padding-bottom:20px}
.gcard{background:#fff;border-radius:34px;padding:50px 40px;display:flex;align-items:center;gap:32px;box-shadow:0 14px 34px rgba(60,40,10,.12)}
.dense .gcard{padding:30px 40px}
.dense .cards{gap:22px}
.gcard .num{flex:none;width:78px;height:78px;border-radius:50%;background:var(--or);color:#fff;font-family:'Anton';font-size:46px;display:flex;align-items:center;justify-content:center}
.gcard p{font-weight:800;font-size:calc(42px * var(--k));line-height:1.25;flex:1}
.gcard .ico{background:#FFF1E4;width:92px;height:92px}
/* cta */
.cta .wrap{justify-content:flex-end}
.cta .hl-poster{font-family:'Anton';font-size:calc(124px * var(--k));line-height:1.04;text-transform:uppercase;margin:34px 0 34px;flex:none;position:relative;z-index:3}
.cta .sub{font-family:'Jakarta';font-weight:500;font-size:calc(40px * var(--k));line-height:1.4;color:#C9C9C9;margin-bottom:46px;flex:none;position:relative;z-index:3}
.pill{display:inline-flex;align-items:center;background:#fff;color:#0A0A0A;font-weight:800;font-size:calc(38px * var(--k));padding:30px 52px;border-radius:999px;align-self:flex-start;flex:none;position:relative;z-index:3}
.ctalogo{position:absolute;left:84px;top:78px;z-index:3}
"""

# ---------- ikon (stroke 5, 64x64) ----------
ICONS = {
    "coin": "<circle cx='32' cy='32' r='22'/><path d='M32 18v28M24 26c0-4 16-4 16 0s-16 4-16 8 16 4 16 0'/>",
    "book": "<path d='M12 14h18a6 6 0 0 1 6 6v32a5 5 0 0 0-5-5H12z'/><path d='M52 14H34v38a5 5 0 0 1 5-5h13z'/>",
    "store": "<path d='M10 24l6-12h32l6 12z'/><path d='M14 24v28h36V24'/><path d='M26 52V38h12v14'/>",
    "wave": "<path d='M6 38c6-8 10-8 16 0s10 8 16 0 10-8 20 0'/><path d='M6 50c6-8 10-8 16 0s10 8 16 0 10-8 20 0'/><path d='M20 24a12 12 0 0 1 24 0'/>",
    "qr": "<rect x='10' y='10' width='18' height='18' rx='2'/><rect x='36' y='10' width='18' height='18' rx='2'/><rect x='10' y='36' width='18' height='18' rx='2'/><path d='M38 38h6v6h-6zM48 48h6v6h-6zM38 50h4M50 38h4'/>",
    "bolt": "<path d='M36 8L16 36h14l-4 20 22-30H34z'/>",
    "chart": "<path d='M10 52V12M10 52h44'/><path d='M18 42l10-12 8 8 14-18'/>",
    "heart": "<path d='M32 54S8 40 8 24a12 12 0 0 1 24-4 12 12 0 0 1 24 4c0 16-24 30-24 30z'/>",
    "clock": "<circle cx='32' cy='32' r='22'/><path d='M32 18v15l10 7'/>",
    "check": "<circle cx='32' cy='32' r='22'/><path d='M21 33l8 8 15-17'/>",
    "star": "<path d='M32 8l7 16 17 2-13 12 4 17-15-9-15 9 4-17L8 26l17-2z'/>",
    "phone": "<rect x='18' y='6' width='28' height='52' rx='6'/><path d='M28 50h8'/>",
    "tag": "<path d='M8 30L30 8h22v22L30 52z'/><circle cx='42' cy='18' r='4'/>",
}


def icon(name, size=48, color="#F97316"):
    body = ICONS.get(name, ICONS["star"])
    return (f"<svg width='{size}' height='{size}' viewBox='0 0 64 64' fill='none' stroke='{color}' "
            f"stroke-width='5' stroke-linecap='round' stroke-linejoin='round'>{body}</svg>")


DOODLES = {
    "star": "<svg width='190' height='190' viewBox='0 0 64 64' fill='none' stroke='#F97316' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'>" + ICONS["star"] + "</svg>",
    "squiggle": "<svg width='300' height='80' viewBox='0 0 300 80' fill='none' stroke='#F97316' stroke-width='9' stroke-linecap='round'><path d='M10 40c20-40 40 40 60 0s40 40 60 0 40 40 60 0 40 40 60 0'/></svg>",
    "circle": "<svg width='220' height='220' viewBox='0 0 220 220' fill='none' stroke='#F97316' stroke-width='9' stroke-linecap='round'><path d='M112 16C48 12 12 62 20 118s64 90 122 76 72-76 52-124S150 14 96 24'/></svg>",
    "spark": "<svg width='170' height='170' viewBox='0 0 170 170' fill='none' stroke='#F97316' stroke-width='10' stroke-linecap='round'><path d='M85 12v44M85 114v44M12 85h44M114 85h44M34 34l28 28M108 108l28 28M136 34l-28 28M62 108l-28 28'/></svg>",
}
SWIPE = ("<div class='swipe'>geser<svg width='96' height='40' viewBox='0 0 96 40' fill='none' stroke='#E2600A' "
         "stroke-width='6' stroke-linecap='round' stroke-linejoin='round'><path d='M4 22c20-8 44-6 84-2M70 6l20 14-18 16'/></svg></div>")


def phone_art(a):
    """Bingkai HP siap pakai. a = {"kind":"phone","title":"Hari ke-12","meta":"Rp 184rb","scene":"<fragmen SVG, koordinat 0..384 x 0..560>"}"""
    title = html.escape(a.get("title", ""), quote=False)
    meta = html.escape(a.get("meta", ""), quote=False)
    scene = a.get("scene", "")
    return (
        "<svg width='1080' height='800' viewBox='0 0 1080 800' xmlns='http://www.w3.org/2000/svg'>"
        "<defs><clipPath id='scr'><rect x='0' y='0' width='384' height='560'/></clipPath></defs>"
        "<g transform='translate(-135 0) scale(1.25)'>"
        "<rect x='330' y='20' width='420' height='700' rx='56' fill='#1B1B1B' stroke='#3A3A3A' stroke-width='6'/>"
        "<rect x='348' y='40' width='384' height='660' rx='42' fill='#FFE3BE'/>"
        "<rect x='490' y='48' width='100' height='22' rx='11' fill='#1B1B1B'/>"
        "<rect x='348' y='86' width='384' height='54' fill='#0A0A0A'/>"
        f"<text x='372' y='123' font-family='Jakarta' font-weight='800' font-size='26' fill='#fff'>{title}</text>"
        f"<text x='708' y='123' text-anchor='end' font-family='Jakarta' font-weight='800' font-size='26' fill='#F97316'>{meta}</text>"
        f"<g transform='translate(348 140)' clip-path='url(#scr)'><rect width='384' height='560' fill='#FFE3BE'/>{scene}</g>"
        "</g></svg>")


def tiles_art(a):
    """Tiga ubin ikon besar. a = {"kind":"tiles","icons":["coin","chart","clock"],"labels":["a","b","c"]}"""
    icons = (a.get("icons") or ["star", "coin", "chart"])[:3]
    labels = a.get("labels") or []
    pos = [(110, 150, -7), (410, 70, 3), (710, 170, 8)]
    out = ["<svg width='1080' height='640' viewBox='0 0 1080 640' xmlns='http://www.w3.org/2000/svg'>"]
    for i, name in enumerate(icons):
        x, y, rot = pos[i]
        body = ICONS.get(name, ICONS["star"])
        out.append(f"<g transform='rotate({rot} {x+130} {y+150})'>"
                   f"<rect x='{x}' y='{y}' width='260' height='300' rx='56' fill='#fff' stroke='#F97316' stroke-width='8'/>"
                   f"<svg x='{x+55}' y='{y+40}' width='150' height='150' viewBox='0 0 64 64' fill='none' stroke='#F97316' "
                   f"stroke-width='4' stroke-linecap='round' stroke-linejoin='round'>{body}</svg>")
        if i < len(labels):
            lab = html.escape(labels[i], quote=False)
            out.append(f"<text x='{x+130}' y='{y+250}' text-anchor='middle' font-family='Jakarta' font-weight='800' font-size='34' fill='#17130F'>{lab}</text>")
        out.append("</g>")
    out.append("</svg>")
    return "".join(out)


def fmt(text):
    t = html.escape(text or "", quote=False)
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)


def logo_dark():
    return f"<div class='badge'><img src='{furl(LOGO)}'></div>"


def top(idx, total, on_dark=False):
    left = f"<img class='logo' src='{furl(LOGO)}'>" if on_dark else logo_dark()
    return f"<div class='top'>{left}<div class='counter'>{idx}/{total}</div></div>"


def build(s, idx, total):
    t = s["type"]
    hl = fmt(s.get("headline"))
    body = fmt(s.get("body"))
    last = idx == total
    if t == "cover":
        art = s.get("art") or {"kind": "none"}
        art_html = ""
        kind = art.get("kind")
        if kind in ("svg", "phone", "tiles"):
            if kind == "svg":
                body, tilt, dy = art["svg"], art.get("tilt", -6), art.get("dy", 70)
            elif kind == "phone":
                body, tilt, dy = phone_art(art), art.get("tilt", -5), art.get("dy", 130)
            else:
                body, tilt, dy = tiles_art(art), art.get("tilt", 0), art.get("dy", 40)
            art_html = f"<div class='art'><div style='transform:rotate({tilt}deg) translateY({dy}px);transform-origin:50% 100%'>{body}</div></div>"
        kicker = html.escape(s.get("kicker", ""), quote=False)
        inner = (f"<div class='glow'></div><div class='dots'></div>{art_html}"
                 f"<div class='wrap'><div class='top'><img class='logo' src='{furl(LOGO)}'></div>"
                 f"<div class='kicker'>{kicker}</div><div class='hl-poster'>{hl}</div></div>")
        cls = "dark cover"
    elif t == "note":
        doodle = s.get("doodle", "swipe")
        d = SWIPE if (doodle == "swipe" and not last) else (f"<div class='doodle'>{DOODLES[doodle]}</div>" if doodle in DOODLES else "")
        sub = f"<div class='sub'>{body}</div>" if body else ""
        inner = (f"<div class='wrap'>{top(idx, total)}<div class='mid'><div class='hl-hand'>{hl}</div>{sub}</div></div>{d}")
        cls = "paper note"
    elif t == "stat":
        big = html.escape(str(s.get("big", "")), quote=False)
        label = html.escape(s.get("label", ""), quote=False)
        sub = f"<div class='sub'>{body}</div>" if body else ""
        inner = (f"<div class='wrap'>{top(idx, total)}<div class='mid'><div class='big'>{big}</div>"
                 f"<div class='label'>{label}</div><div class='hl-hand'>{hl}</div>{sub}</div></div>{SWIPE if not last else ''}")
        cls = "paper stat"
    elif t == "ui":
        rows = ""
        for r in s.get("rows", []):
            tone = r.get("tone", "ok")
            tag = f"<span class='tag {tone}'>{html.escape(r.get('tag',''), quote=False)}</span>" if r.get("tag") else ""
            rows += (f"<div class='row'><div class='ico'>{icon(r.get('icon','coin'), 46)}</div>"
                     f"<div class='t'><b>{html.escape(r.get('title',''), quote=False)}</b>"
                     f"<i>{html.escape(r.get('sub',''), quote=False)}</i></div>{tag}</div>")
        cap = html.escape(s.get("caption", ""), quote=False)
        ctitle = html.escape(s.get("card_title", ""), quote=False)
        cmeta = html.escape(s.get("card_meta", ""), quote=False)
        inner = (f"<div class='wrap'>{top(idx, total)}<div class='hl-hand'>{hl}</div>"
                 f"<div class='uimid'><div class='phone'><div class='bar'><span>{ctitle}</span><span>{cmeta}</span></div>{rows}</div>"
                 f"<div class='caption'>{cap}</div></div></div>")
        cls = "paper ui"
    elif t == "grid":
        items = ""
        for n, it in enumerate(s.get("items", []), 1):
            items += (f"<div class='gcard'><div class='num'>{n}</div><p>{fmt(it.get('text',''))}</p>"
                      f"<div class='ico'>{icon(it.get('icon','star'), 54)}</div></div>")
        stamp = html.escape(s.get("stamp", "SIMPAN"), quote=False)
        inner = (f"<div class='wrap'>{top(idx, total)}<div class='stamp'>{stamp}</div>"
                 f"<div class='hl-hand'>{hl}</div><div class='cards'>{items}</div></div>")
        cls = "paper grid" + (" dense" if len(s.get("items", [])) >= 4 else "")
    elif t == "cta":
        pill = html.escape(s.get("pill", ""), quote=False)
        sub = f"<div class='sub'>{body}</div>" if body else ""
        inner = (f"<div class='glow'></div><div class='dots'></div>"
                 f"<div class='wrap'><div class='top'><img class='logo' src='{furl(LOGO)}'></div><div style='flex:1'></div>"
                 f"<div class='hl-poster'>{hl}</div>{sub}<div class='pill'>{pill}</div></div>")
        cls = "dark cta"
    else:
        raise ValueError(f"type slide tidak dikenal: {t}")
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head>"
            f"<body class='{cls}'>{inner}</body></html>")


MEASURE_JS = """
() => {
  const wrap = document.querySelector('.wrap');
  const kids = Array.from(wrap.children).filter(e => e.getBoundingClientRect().height > 0 && getComputedStyle(e).position !== 'absolute');
  const last = kids[kids.length - 1].getBoundingClientRect();
  const first = kids[0].getBoundingClientRect();
  const mid = document.querySelector('.mid');
  const cards = document.querySelector('.cards');
  const phone = document.querySelector('.phone');
  const cap = document.querySelector('.caption');
  const hl = document.querySelector('.hl-poster');
  const art = document.querySelector('.art > div');
  return {
    bottom: last.bottom, top: first.top,
    midOver: mid ? (mid.scrollHeight > mid.clientHeight + 2) : false,
    cardsOver: cards ? (cards.scrollHeight > cards.clientHeight + 2) : false,
    phoneBottom: phone ? phone.getBoundingClientRect().bottom : 0,
    capBottom: cap ? cap.getBoundingClientRect().bottom : 0,
    hlBottom: hl ? hl.getBoundingClientRect().bottom : 0,
    artTop: art ? art.getBoundingClientRect().top : 9999,
    docH: document.documentElement.scrollHeight
  };
}
"""


def fits(m, t):
    if t != "cover" and m["docH"] > 1350 + 2:
        return False
    if t in ("note", "stat") and m["midOver"]:
        return False
    if t == "grid" and m["cardsOver"]:
        return False
    if t == "ui" and m["capBottom"] > 1350 - 70:
        return False
    if t == "cover" and m["hlBottom"] > 760:
        return False
    return True


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    slides = spec["slides"]
    total = len(slides)
    errors = []
    if not os.path.exists(LOGO):
        errors.append(f"Logo tidak ditemukan: {LOGO}")
    if slides[0]["type"] != "cover":
        errors.append("Slide pertama harus 'cover'")
    if slides[-1]["type"] != "cta":
        errors.append("Slide terakhir harus 'cta'")
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        sys.exit(1)
    chromium = next((c for c in CHROMIUM_CANDIDATES if os.path.exists(c)), None)

    warnings, files = [], []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=chromium) if chromium else p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        for i, s in enumerate(slides, 1):
            html_path = os.path.join(out, f"slide_{i:02d}.html")
            open(html_path, "w", encoding="utf-8").write(build(s, i, total))
            pg.goto(f"file://{os.path.abspath(html_path)}")
            pg.wait_for_timeout(350)
            k = 1.0
            m = pg.evaluate(MEASURE_JS)
            while not fits(m, s["type"]) and k > 0.70:
                k = round(k - 0.05, 2)
                pg.evaluate(f"document.documentElement.style.setProperty('--k','{k}')")
                pg.wait_for_timeout(80)
                m = pg.evaluate(MEASURE_JS)
            if not fits(m, s["type"]):
                warnings.append(f"Slide {i}: teks masih overflow setelah font dikecilkan ke {int(k*100)}% — perpendek teksnya")
            elif k < 1.0:
                warnings.append(f"Slide {i}: font dikecilkan ke {int(k*100)}% agar muat (sebaiknya perpendek teks)")
            if s["type"] in ("note", "stat", "ui", "grid") and re.search(r"(^|[\s*(\"])G[a-z]", s.get("headline", "") or ""):
                warnings.append(f"Slide {i}: huruf G kapital di awal kata terbaca seperti angka 6 di font tulisan tangan — tulis ulang headline tanpa kata berawalan G kapital")
            png = os.path.join(out, f"slide_{i:02d}.png")
            pg.screenshot(path=png)
            files.append(png)
        b.close()
    print(json.dumps({"ok": True, "files": files, "warnings": warnings}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
