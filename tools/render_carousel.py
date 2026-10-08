#!/usr/bin/env python3
"""
Daekan Carousel renderer (desain B: cover foto full-bleed, slide cerita, slide polos, CTA pil).

Pemakaian:
    python3 tools/render_carousel.py spec.json OUT_DIR

Format spec.json:
{
  "slides": [
    {"type": "cover", "headline": "Puluhan lamaran. *Nol balasan.* Bukan kamu yang salah.", "photo": "/abs/path/cover.jpg"},
    {"type": "story", "headline": "Pintunya memang makin sempit", "body": "Paragraf pendek penjelas.", "photo": "/abs/path/a.jpg"},
    {"type": "plain", "headline": "Kalau pintunya sempit, *bikin pintu sendiri.*", "body": "Subline pendek."},
    {"type": "cta",   "headline": "Belum punya produk? Di Daekan itu *bukan masalah.*", "body": "Lihat katalog Daekan MVP.", "pill": "Kunjungi daekan.id  →", "photo": "/abs/path/cta.jpg"}
  ]
}

Aturan:
- Frasa aksen oranye ditandai dengan *tanda bintang* (maks 1 frasa per headline).
- Slide pertama harus "cover", slide terakhir harus "cta". Counter n/total otomatis (cover & cta tanpa counter).
- "cover" dan "cta" wajib punya "photo"; "story" wajib punya "photo"; "plain" tanpa foto.
- Foto = file JPG/PNG lokal. Logo diambil dari brand/daekan-logo.png di repo (jangan diganti).
- Skrip mengecilkan font otomatis (maks sampai 70%) kalau teks overflow, dan mencetak WARNING kalau tetap tidak muat.
  Kalau ada WARNING, perpendek teksnya lalu render ulang. JANGAN ubah CSS di file ini.
Output: slide_01.png ... slide_NN.png (1080x1350) + ringkasan JSON di stdout.
"""
import html
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO = os.path.join(REPO, "brand", "daekan-logo.png")
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
:root{--k:1}
body{width:1080px;height:1350px;background:#0A0A0A;font-family:'Liberation Sans',Arial,'DejaVu Sans',sans-serif;overflow:hidden;position:relative;color:#fff}
.bg{position:absolute;inset:0;background-size:cover;background-position:center}
.shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(10,10,10,.15) 0%,rgba(10,10,10,.35) 40%,rgba(10,10,10,.96) 100%)}
.wrap{position:absolute;inset:0;padding:80px;display:flex;flex-direction:column}
.logo{height:44px;width:auto;display:block;align-self:flex-start;flex:none}
.top{display:flex;justify-content:space-between;align-items:center;flex:none}
.counter{color:#8A8A8A;font-size:28px;font-weight:700}
.hl{font-weight:900;letter-spacing:-1.5px}
.hl em{color:#F97316;font-style:normal}
.sub{color:#BDBDBD;font-weight:500}
.pill{display:inline-flex;align-items:center;gap:14px;background:#fff;color:#0A0A0A;font-weight:800;font-size:calc(34px * var(--k));padding:26px 44px;border-radius:999px;align-self:flex-start;flex:none}
.cover .wrap{justify-content:flex-end}
.cover .hl{font-size:calc(104px * var(--k));line-height:1.02;margin-top:34px}
.card{width:100%;flex:1;min-height:380px;max-height:780px;border-radius:32px;background-size:cover;background-position:center;margin-top:56px}
.story .hl{font-size:calc(70px * var(--k));line-height:1.12;margin-top:52px;flex:none}
.story .sub{font-size:calc(38px * var(--k));line-height:1.4;margin-top:26px;flex:none}
.plain .mid{flex:1;display:flex;flex-direction:column;justify-content:center}
.plain .hl{font-size:calc(92px * var(--k));line-height:1.06}
.plain .sub{font-size:calc(40px * var(--k));line-height:1.4;margin-top:34px}
.cta .wrap{justify-content:flex-end}
.cta .hl{font-size:calc(96px * var(--k));line-height:1.04;margin:34px 0 38px}
.cta .sub{font-size:calc(38px * var(--k));line-height:1.4;margin-bottom:44px}
"""


def fmt(text):
    """Escape HTML, lalu ubah *frasa* jadi <em>frasa</em>."""
    t = html.escape(text or "", quote=False)
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)


def file_url(path):
    return "file://" + os.path.abspath(path)


def build(slide, idx, total):
    t = slide["type"]
    logo = f"<img class='logo' src='{file_url(LOGO)}'>"
    hl = fmt(slide.get("headline"))
    body = fmt(slide.get("body"))
    photo = slide.get("photo")
    bg = f"<div class='bg' style=\"background-image:url('{file_url(photo)}')\"></div><div class='shade'></div>" if photo else ""
    if t == "cover":
        inner = f"{bg}<div class='wrap'><div style='flex:1'></div>{logo}<div class='hl'>{hl}</div></div>"
    elif t == "story":
        inner = (f"<div class='wrap'><div class='top'>{logo}<div class='counter'>{idx}/{total}</div></div>"
                 f"<div class='card' style=\"background-image:url('{file_url(photo)}')\"></div>"
                 f"<div class='hl'>{hl}</div><div class='sub'>{body}</div></div>")
    elif t == "plain":
        inner = (f"<div class='wrap'><div class='top'>{logo}<div class='counter'>{idx}/{total}</div></div>"
                 f"<div class='mid'><div class='hl'>{hl}</div><div class='sub'>{body}</div></div></div>")
    elif t == "cta":
        pill = html.escape(slide.get("pill", ""), quote=False)
        inner = (f"{bg}<div class='wrap'>{logo}<div style='flex:1'></div><div class='hl'>{hl}</div>"
                 f"<div class='sub'>{body}</div><div class='pill'>{pill}</div></div>")
    else:
        raise ValueError(f"type slide tidak dikenal: {t}")
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='{t}'>{inner}</div></body></html>"


MEASURE_JS = """
() => {
  const wrap = document.querySelector('.wrap');
  const kids = Array.from(wrap.children).filter(e => e.getBoundingClientRect().height > 0);
  const last = kids[kids.length - 1].getBoundingClientRect();
  const first = kids[0].getBoundingClientRect();
  const hl = document.querySelector('.hl'); const sub = document.querySelector('.sub');
  const logo = document.querySelector('.logo').getBoundingClientRect();
  const card = document.querySelector('.card');
  const r = {bottom: last.bottom, top: first.top, logoBottom: logo.bottom,
             hlTop: hl ? hl.getBoundingClientRect().top : null,
             cardH: card ? card.getBoundingClientRect().height : null,
             scrollH: wrap.scrollHeight};
  return r;
}
"""


def fits(m, t):
    if m["bottom"] > 1350 - 70 + 1:
        return False
    if t in ("cover", "cta") and m["hlTop"] is not None and m["hlTop"] < m["logoBottom"] + 20:
        return False
    if t == "story" and m["cardH"] is not None and m["cardH"] < 380:
        return False
    if m["top"] < 60:
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
    for i, s in enumerate(slides, 1):
        if s["type"] in ("cover", "story", "cta") and not (s.get("photo") and os.path.exists(s["photo"])):
            errors.append(f"Slide {i} ({s['type']}) butuh file foto yang ada: {s.get('photo')}")
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        sys.exit(1)

    warnings, files = [], []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM)
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        for i, s in enumerate(slides, 1):
            html_path = os.path.join(out, f"slide_{i:02d}.html")
            open(html_path, "w", encoding="utf-8").write(build(s, i, total))
            pg.goto(f"file://{os.path.abspath(html_path)}")
            pg.wait_for_timeout(250)
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
            png = os.path.join(out, f"slide_{i:02d}.png")
            pg.screenshot(path=png)
            files.append(png)
        b.close()
    print(json.dumps({"ok": True, "files": files, "warnings": warnings}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
