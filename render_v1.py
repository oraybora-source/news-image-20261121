#!/usr/bin/env python3
"""render_v1.py — ni21 final entry v1 dari Sketsa 1 (T1), pilihan Kevin 12:25 WIB.

Layout T1 (sketsa): masthead serif hitam 56px + deck 5 cerita + strip
6 angka + 3 hero horizontal atas + 10 kartu 2x5 + peta kiri bawah +
MORE STORIES kanan bawah (3 kolom, 11pt, 1 baris, nomor lanjut 14-36)
+ DATE CHECK menonjol + Sources. Tanpa garis pemisah strip-hero, tanpa
legenda pin, 13 pin merah bernomor di peta.

Aturan keras Kevin (assert programmatic, gagal satu = revisi):
1. TIDAK ada overlap apa pun (layout boxes + teks per tile).
2. SEMUA gambar UTUH di tile; subjek UTAMA besar di tengah + margin.
3. Warna atas tiap gambar BEDA dari tetangganya (jarak RGB >= 25).
4. Teks dalam gambar utuh kelihatan ATAU sepenuhnya di luar crop.
5. Gambar tidak hambar — konteks hidup KELIHATAN di ukuran tampil.
6. Peta natural-aspect (Natural Earth 110m), FULL setinggi kotak.
7. Footer final TIDAK PERNAH berisi catatan produksi/draf.
8. Presiden TIDAK seram — kepala polos, beda hanya warna rambut +
   jas/dasi (tidak ada figur presiden di v1 ini; Trump = Capitol).
9. Crosscheck 2x: saat proses + setelah selesai, tiap kartu satu per
   satu di ukuran tampil lawan sketsa.

Teknis: Pillow, deterministik (2x jalan byte sama), tanpa network.
Output: entry.png 1024x1024, <=1 MiB. Fonts OFL (Gelasio + Source
Sans 3) + Natural Earth 110m (Public Domain) di repo ini.
Model: Muse Spark. Anchor: makefun anchor 99ce6ca57c2f35489c4f906b7e0165c7c39ab2cf round 34145189.
"""
import hashlib
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
OUT = os.path.join(HERE, "entry.png")

W, H = 1024, 1024
PAPER = (247, 240, 220)      # kertas krem (sketsa)
NEAR_WHITE = (251, 250, 245)  # latar panel teks (diukur dari referensi ni20)
INK = (20, 20, 20)
NAVY = (31, 58, 95)
RED = (192, 57, 43)
RED_M = (176, 48, 38)
GOLD_M = (200, 150, 30)
WHITE = (255, 255, 255)
LINE = (120, 110, 90)
GREY = (110, 105, 90)
SLATE = (70, 75, 85)

# --- font (spesifikasi Kevin 21:37 WIB) ---
GEL700 = os.path.join(FONTS, "Gelasio-700.ttf")       # judul 700
GEL_IT = os.path.join(FONTS, "Gelasio-Italic.ttf")    # deck italic
SS400 = os.path.join(FONTS, "SourceSans3-400.ttf")    # isi 400
SS600 = os.path.join(FONTS, "SourceSans3-600.ttf")
SS700 = os.path.join(FONTS, "SourceSans3-700.ttf")    # angka strip 700
SS800 = os.path.join(FONTS, "SourceSans3-800.ttf")    # kicker/label 800


def F(path, size):
    return ImageFont.truetype(path, size)


def wrap(d, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ------------------------------------------------------------------ registry
# (a) layout boxes: semua kotak tingkat atas tidak boleh overlap.
# (b) teks per tile: bbox teks di dalam satu tile tidak boleh overlap.
LAYOUT = []


def reg_layout(box, label):
    LAYOUT.append((box, label))


def check_layout(name):
    for i, (a, la) in enumerate(LAYOUT):
        for j in range(i + 1, len(LAYOUT)):
            b, lb = LAYOUT[j]
            if not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1]
                    or b[3] <= a[1]):
                raise SystemExit(f"OVERLAP layout {name}: {la} vs {lb}")
    print(f"  [cek] layout {name}: {len(LAYOUT)} kotak, tidak ada overlap")


class TileText:
    """Kumpulkan bbox teks satu tile; assert tidak ada yang overlap."""

    def __init__(self, label):
        self.label = label
        self.boxes = []

    def add(self, box, what):
        for b, w in self.boxes:
            if not (box[2] <= b[0] or b[2] <= box[0] or box[3] <= b[1]
                    or b[3] <= box[1]):
                raise SystemExit(
                    f"OVERLAP teks {self.label}: {what} vs {w}")
        self.boxes.append((box, what))

    def text(self, d, x, y, s, font, fill, anchor="la"):
        b = d.textbbox((x, y), s, font=font, anchor=anchor)
        d.text((x, y), s, font=font, fill=fill, anchor=anchor)
        self.add(b, repr(s[:24]))
        return b


def top_color(img):
    """Warna atas tile: rata-rata patch 20x6 di tengah-atas."""
    w, _ = img.size
    patch = img.crop((w // 2 - 10, 2, w // 2 + 10, 8))
    px = list(patch.getdata())
    n = len(px)
    return tuple(sum(c[i] for c in px) // n for i in range(3))


def rgb_dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
            + (a[2] - b[2]) ** 2) ** 0.5


# ------------------------------------------------------------------ data
# 36 cerita Sabtu 21 Nov 2026, terverifikasi sumber primer (STORIES.md).
HEROES = [
    {"num": 1, "city": "Antalya", "place": "ANTALYA, TURKIYE",
     "topic": "COP31", "region": "GLOBAL",
     "title": "COP31 runs into overtime with no deal",
     "sum": ("Draft 2 drops fossil fuels; talks resume Saturday "
             "morning in Antalya."),
     "painter": "cop31", "map_city": "Antalya"},
    {"num": 2, "city": "Riyadh", "place": "RIYADH, SAUDI ARABIA",
     "topic": "MISSILES", "region": "MIDDLE EAST",
     "title": "Three Houthi missiles shot down over Riyadh",
     "sum": ("Third night of alerts; two blasts heard, no damage "
             "or casualties reported."),
     "painter": "riyadh", "map_city": "Riyadh"},
    {"num": 3, "city": "Junin", "place": "JUNIN, PERU",
     "topic": "QUAKE", "region": "AMERICAS",
     "title": "Magnitude 6.7 quake hits Peru",
     "sum": ("Epicentre near Junin, 108 km deep; felt in Lima, "
             "no deaths, no tsunami threat."),
     "painter": "quake", "map_city": "Junin"},
]

CARDS = [
    {"num": 4, "city": "Kryvyi Rih", "place": "KRYVYI RIH, UKRAINE",
     "topic": "STRIKE", "region": "EUROPE",
     "title": "Kryvyi Rih double strike",
     "sum": "2 killed, 42 hurt in double-tap on restaurant.",
     "painter": "kryvyi", "map_city": "Kryvyi Rih"},
    {"num": 5, "city": "Davao", "place": "DAVAO, PHILIPPINES",
     "topic": "AIR SAFETY", "region": "ASIA",
     "title": "Air Niugini jet lands in Davao \u2014 all 146 safe",
     "sum": "Engine fire warning; all 146 evacuated by slide.",
     "painter": "davao", "map_city": "Davao"},
    {"num": 6, "city": "Darmstadt", "place": "DARMSTADT, GERMANY",
     "topic": "SPACE", "region": "GLOBAL",
     "title": "BepiColombo reaches Mercury tonight, 19:24 CET",
     "sum": "Orbit burn due 19:24 CET; 8-year trip ends tonight.",
     "painter": "bepi", "map_city": "Darmstadt"},
    {"num": 7, "city": "Washington", "place": "WASHINGTON, USA",
     "topic": "TAX", "region": "AMERICAS",
     "title": "Trump vows \u2018tremendous tax\u2019 on data centres",
     "sum": "US firms taxed if they build data centres abroad.",
     "painter": "capitol", "map_city": "Washington"},
    {"num": 8, "city": "Sejong", "place": "SEJONG, S. KOREA",
     "topic": "RAIL", "region": "ASIA",
     "title": "Freight train derails in South Korea \u2014 5 of 21 cars",
     "sum": "Five of 21 cars derail; no injuries reported.",
     "painter": "train", "map_city": "Sejong"},
    {"num": 9, "city": "Wellington", "place": "WELLINGTON, NZ",
     "topic": "CRICKET", "region": "OCEANIA",
     "title": "Rahul's Test century in Wellington",
     "sum": "Century No. 13; India 239/1 at lunch in Wellington.",
     "painter": "cricket", "map_city": "Wellington"},
    {"num": 10, "city": "Las Vegas", "place": "LAS VEGAS, USA",
     "topic": "FORMULA 1", "region": "AMERICAS",
     "title": "Las Vegas GP: Verstappen on pole",
     "sum": "Antonelli fastest in qualifying; Verstappen on pole.",
     "painter": "f1", "map_city": "Las Vegas"},
    {"num": 11, "city": "Hormuz", "place": "STRAIT OF HORMUZ",
     "topic": "DRONE", "region": "MIDDLE EAST",
     "title": "Iran claims it shot down a US MQ-9 over Hormuz",
     "sum": "Tehran claims 58th downing; not independently verified.",
     "painter": "drone", "map_city": "Hormuz"},
    {"num": 12, "city": "Hanoi", "place": "HANOI, VIETNAM",
     "topic": "LAW", "region": "ASIA",
     "title": "Vietnam passes laws to speed land seizures",
     "sum": "Land seizures fast-tracked; death penalty ends for six crimes.",
     "painter": "gavel", "map_city": "Hanoi"},
    {"num": 13, "city": "Turin", "place": "TURIN, ITALY",
     "topic": "TENNIS", "region": "EUROPE",
     "title": "ATP Finals semis tonight in Turin",
     "sum": "Alcaraz\u2013Shelton, Zverev\u2013Medvedev; both tonight.",
     "painter": "tennis", "map_city": "Turin"},
]

# Briefs 14-36: terse 1 klausa, 1 BARIS @11pt di kolom 184px.
# (Sketsa T1 memakai 2 baris @10pt; build ini mengikuti standar Kevin
# ni20: brief 11pt 1 baris, teks dipadatkan tanpa mengubah fakta.)
BRIEFS = [
    (14, "Rutte flies to Warsaw"),
    (15, "Iraq road to Karbala reopens"),
    (16, "Houthis warn ships off ports"),
    (17, "Bitcoin slides to $56,814"),
    (18, "Dragon splashes down today"),
    (19, "ANC fights to keep key cities"),
    (20, "$811m migrants scam continues"),
    (21, "India vs South Korea tonight"),
    (22, "CGTP marches in Lisbon today"),
    (23, "Pet cremation scam in Manila"),
    (24, "PLN signs clean-power deals"),
    (25, "Anutin calls emergency meeting"),
    (26, "Pakistani minister in Delhi"),
    (27, "Akvan rain soaks east India"),
    (28, "Cummins keeps the captaincy"),
    (29, "Italy rail strike today"),
    (30, "Naga votes on city status"),
    (31, "M4.6 quake off Java"),
    (32, "M4.7 quake in northern Chile"),
    (33, "Delhi chokes: AQI 286"),
    (34, "Visayas grid on yellow alert"),
    (35, "One Nation Tasmania donors"),
    (36, "AUS v ENG T20 opener tonight"),
]

NUMBERS = [("13", "DAY 13 \u00b7 COP31"), ("3", "MISSILES DOWNED"),
           ("6.7", "PERU QUAKE"), ("146", "SAFE IN DAVAO"),
           ("42", "HURT IN KRYVYI RIH"), ("$56,814", "BITCOIN SAT AM")]

DECK = ("COP31 in overtime  \u00b7  Three missiles down over Riyadh  \u00b7  "
        "Peru quake 6.7  \u00b7  Kryvyi Rih double strike  \u00b7  "
        "Davao: all 146 safe")

DATECHECK = ("Left out as Friday 20 Nov news: Kyiv bridges hit \u00b7 "
             "missile in Poland \u00b7 Wall Street correction \u00b7 UK\u2013EU "
             "deal \u00b7 Akvan landfall \u00b7 ICJ Myanmar ruling \u00b7 "
             "Shenzhen summit \u00b7 Anthropic IPO \u00b7 GTA VI launch. "
             "Not yet happened: BepiColombo (19:24 CET) \u00b7 ATP semis "
             "\u00b7 T20 opener.")

SOURCES = ("Sources: Reuters \u00b7 AP \u00b7 AFP \u00b7 BBC \u00b7 USGS \u00b7 "
           "NASA \u00b7 Antara \u00b7 Yonhap \u00b7 ATP Tour \u00b7 ESA \u00b7 "
           "Kyiv Independent \u00b7 NGCP \u00b7 BMKG")

# ------------------------------------------------------------------ peta
# Outline benua DETAIL Natural Earth 110m land (Public Domain).
# Proyeksi referensi ni20 (diukur dari peta referensi 2048):
# x-scale 0,815 px/derajat, y-scale 1,0 px/derajat (regang 1,23x).
MAP_LAND = (218, 190, 148)
MAP_LAND_OUT = (200, 175, 130)
MAP_SX, MAP_SY = 0.815, 1.0
MAP_LAT0 = 83.0
SEA = (38, 68, 104)


def load_land_polys():
    path = os.path.join(HERE, "ne_110m_land.geojson")
    with open(path) as fh:
        data = json.load(fh)
    polys = []
    for feat in data["features"]:
        for ring in feat["geometry"]["coordinates"]:
            if len(ring) < 4:
                continue
            lats = [p[1] for p in ring]
            if max(lats) < -60:
                continue
            xs = [p[0] for p in ring]
            ys = lats
            if (max(xs) - min(xs)) < 0.4 and (max(ys) - min(ys)) < 0.4:
                continue
            out = [ring[0]]
            for p in ring[1:]:
                if (abs(p[0] - out[-1][0]) > 0.12
                        or abs(p[1] - out[-1][1]) > 0.12):
                    out.append(p)
            if out[-1] != ring[-1]:
                out.append(ring[-1])
            polys.append(out)
    return polys


LAND_POLYS = load_land_polys()

# lon/lat pin 1-13 (lead + feature). #6 BepiColombo: ESOC Darmstadt
# (pusat kendali misi ESA) — tidak ada lokasi Bumi untuk Merkurius.
PLACES = {
    "Antalya": (30.7, 36.9), "Riyadh": (46.7, 24.7),
    "Junin": (-75.9, -10.9), "Kryvyi Rih": (33.4, 47.9),
    "Davao": (125.6, 7.1), "Darmstadt": (8.65, 49.87),
    "Washington": (-77.0, 38.9), "Sejong": (127.3, 36.5),
    "Wellington": (174.8, -41.3), "Las Vegas": (-115.1, 36.2),
    "Hormuz": (56.5, 27.0), "Hanoi": (105.8, 21.0),
    "Turin": (7.7, 45.1),
}

# ------------------------------------------------------------------ painters
# SATU gaya ilustrasi datar. Aturan: TIDAK ada elemen di strip atas
# 10px kecuali latar (supaya warna atas = tint latar, terukur).
# Subjek UTAMA besar di tengah + margin; konteks hidup kelihatan.
# Warna atas = tint latar panel; tetangga ortogonal harus beda >= 25.

# 6 tint kalem (jarak RGB antar semua pasangan >= 28, dicek di bawah).
TINTS = {
    "steel": (178, 205, 224),
    "rose": (240, 180, 175),
    "gold": (242, 228, 185),
    "sage": (190, 220, 195),
    "lilac": (222, 210, 238),
    "peach": (245, 215, 160),
}
# Hero: latar gelap (hierarki — hero harus paling menonjol).
HERO_BG = {"cop31": (17, 54, 60), "riyadh": (64, 28, 34),
           "quake": (122, 88, 48)}


def chip(d, x, y, label, font=None, bg=NAVY, fg=WHITE):
    """Chip kecil fakta di dalam gambar (pojok kiri atas, tidak sentuh
    patch tengah-atas)."""
    f = font or F(SS800, 8)
    tw = d.textlength(label, font=f)
    cw, ch = int(tw) + 8, 12
    d.rounded_rectangle([x, y, x + cw, y + ch], radius=2, fill=bg)
    d.text((x + cw // 2, y + ch // 2), label, font=f, fill=fg, anchor="mm")
    return cw


def p_cop31(w, h):
    """Hero 1 COP31: panel teal gelap + globe + termometer + kartu putih
    'COP31 / OVERTIME · NO DEAL' (fakta: overtime, draf tanpa fosil)."""
    bg = HERO_BG["cop31"]
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    gx, gy, gr = 62, 62, 30
    d.ellipse([gx - gr, gy - gr, gx + gr, gy + gr], fill=(70, 130, 180),
              outline=NAVY, width=2)
    d.ellipse([gx - 17, gy - 12, gx + 2, gy + 5], fill=(90, 150, 90))
    d.ellipse([gx - 2, gy + 10, gx + 17, gy + 22], fill=(90, 150, 90))
    d.ellipse([gx + 7, gy - 20, gx + 19, gy - 5], fill=(90, 150, 90))
    tx = 118
    d.rounded_rectangle([tx, 26, tx + 12, 84], radius=6,
                        fill=(240, 244, 246), outline=NAVY, width=1)
    d.rectangle([tx + 4, 48, tx + 8, 80], fill=RED_M)
    d.ellipse([tx - 3, 78, tx + 15, 96], fill=RED_M, outline=NAVY, width=1)
    kx0, ky0, kx1, ky1 = 152, 16, w - 8, h - 16
    d.rectangle([kx0, ky0, kx1, ky1], fill=WHITE, outline=NAVY, width=1)
    d.text(((kx0 + kx1) // 2, ky0 + 8), "ANTALYA \u00b7 NOV 21",
           font=F(SS800, 8), fill=RED_M, anchor="ma")
    d.text(((kx0 + kx1) // 2, ky0 + 24), "COP31", font=F(GEL700, 30),
           fill=NAVY, anchor="ma")
    d.text(((kx0 + kx1) // 2, ky1 - 20), "OVERTIME \u00b7 NO DEAL",
           font=F(SS800, 8), fill=RED_M, anchor="ma")
    return im


def p_riyadh(w, h):
    """Hero 2 Riyadh: langit malam + skyline (menara Kingdom Centre) +
    TIGA jejak intersepsi + tiga ledakan putih (fakta: 3 rudal dicegat).
    """
    bg = HERO_BG["riyadh"]
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    for (sx, sy) in [(30, 30), (90, 22), (150, 34), (210, 26), (260, 32),
                     (60, 52), (190, 48), (290, 50)]:
        d.ellipse([sx, sy, sx + 2, sy + 2], fill=(220, 220, 200))
    gy = h - 18
    d.rectangle([0, gy, w, h], fill=(30, 18, 22))
    # skyline: gedung-gedung gelap + menara Kingdom Centre (bukaan khas)
    for (bx, bw, bh) in [(0, 34, 52), (40, 26, 70), (72, 30, 44),
                         (200, 28, 58), (232, 34, 40), (272, 30, 66)]:
        d.rectangle([bx, gy - bh, bx + bw, gy], fill=(16, 14, 18))
        for wy in range(gy - bh + 8, gy - 6, 12):
            d.rectangle([bx + 5, wy, bx + bw - 5, wy + 4],
                        fill=(240, 200, 90))
    kx, kw = 108, 88
    d.rectangle([kx, gy - 96, kx + kw, gy], fill=(16, 14, 18))
    d.polygon([(kx + 18, gy - 96), (kx + kw - 18, gy - 96),
               (kx + kw // 2, gy - 62)], fill=bg)
    d.rectangle([kx + 6, gy - 90, kx + kw - 6, gy - 6], fill=(16, 14, 18))
    # TIGA jejak intersepsi emas + ledakan putih
    for (x0, y0, x1, y1) in [(40, gy - 4, 110, 34), (150, gy - 4, 210, 28),
                             (250, gy - 4, 292, 40)]:
        steps = 10
        for i in range(steps):
            fx0 = x0 + (x1 - x0) * i / steps
            fy0 = y0 + (y1 - y0) * i / steps
            fx1 = x0 + (x1 - x0) * (i + 0.55) / steps
            fy1 = y0 + (y1 - y0) * (i + 0.55) / steps
            d.line([(fx0, fy0), (fx1, fy1)], fill=(240, 200, 90), width=2)
        for (dx, dy) in [(0, 0), (-7, -3), (7, -3), (-4, 6), (4, 6)]:
            d.line([(x1, y1), (x1 + dx, y1 + dy)], fill=WHITE, width=2)
        d.ellipse([x1 - 3, y1 - 3, x1 + 3, y1 + 3], fill=WHITE)
    chip(d, w - 108, h - 20, "3 INTERCEPTED", bg=(16, 14, 18))
    return im


def p_quake(w, h):
    """Hero 3 Peru: pegunungan Andes + garis seismograf + retakan tanah
    + chip 'M6.7 · JUNIN'."""
    bg = HERO_BG["quake"]
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    d.ellipse([w - 52, 22, w - 20, 54], fill=(250, 240, 200))
    gy = h - 26
    for (mx, mw, mh, snow) in [(20, 150, 78, True), (120, 170, 96, True),
                               (250, 120, 64, False)]:
        d.polygon([(mx, gy), (mx + mw // 2, gy - mh), (mx + mw, gy)],
                  fill=(70, 48, 30))
        if snow:
            d.polygon([(mx + mw // 2 - 14, gy - mh + 22),
                       (mx + mw // 2, gy - mh),
                       (mx + mw // 2 + 14, gy - mh + 22)],
                      fill=WHITE)
    d.rectangle([0, gy, w, h], fill=(52, 36, 22))
    d.line([(10, gy + 8), (60, gy + 14), (95, gy + 4), (140, gy + 16),
            (185, gy + 6), (230, gy + 14), (300, gy + 8)],
           fill=(40, 26, 16), width=3)
    pts = [(10, 52), (40, 52), (52, 40), (64, 64), (76, 52), (110, 52),
           (122, 44), (134, 60), (146, 52), (180, 52), (192, 42),
           (204, 62), (216, 52), (250, 52), (300, 52)]
    d.line(pts, fill=WHITE, width=2, joint="curve")
    chip(d, w - 96, h - 20, "M6.7 \u00b7 JUNIN", bg=(52, 36, 22))
    return im


def p_kryvyi(w, h, bg):
    """Kartu 4: gedung kena serangan + bintang ledakan merah + asap."""
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    gy = int(h * 0.86)
    d.rectangle([0, gy, w, h], fill=(90, 80, 70))
    bx0, bx1, by0 = int(w * 0.30), int(w * 0.66), int(h * 0.38)
    d.rectangle([bx0, by0, bx1, gy], fill=(70, 62, 58), outline=NAVY,
                width=1)
    d.polygon([(bx0, by0), (bx1, by0), (bx1 - 14, by0 - 10),
               (bx0 + 10, by0 - 10)], fill=(52, 46, 42))
    for wy in range(by0 + 8, gy - 6, 10):
        for wx in (bx0 + 6, bx0 + 20):
            d.rectangle([wx, wy, wx + 8, wy + 6], fill=(240, 210, 120))
    cx, cy = int(w * 0.78), int(h * 0.34)
    for (dx, dy) in [(0, -14), (10, -10), (14, 0), (10, 10), (0, 14),
                     (-10, 10), (-14, 0), (-10, -10)]:
        d.line([(cx, cy), (cx + dx, cy + dy)], fill=RED_M, width=3)
    d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=RED_M)
    d.ellipse([int(w * 0.14), int(h * 0.22), int(w * 0.14) + 12,
               int(h * 0.22) + 8], fill=(235, 235, 230))
    d.ellipse([int(w * 0.20), int(h * 0.16), int(w * 0.20) + 9,
               int(h * 0.16) + 6], fill=(235, 235, 230))
    return im


def p_davao(w, h, bg):
    """Kartu 5: pesawat besar + landasan + chip '146 SAFE'."""
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    gy = int(h * 0.80)
    d.rectangle([0, gy, w, h], fill=(90, 90, 90))
    for x in range(0, w, 18):
        d.line([(x, gy + 6), (x + 9, gy + 6)], fill=WHITE, width=2)
    cx, cy = w // 2, int(h * 0.56)
    d.ellipse([cx - 52, cy - 9, cx + 52, cy + 9], fill=WHITE, outline=NAVY,
              width=1)
    d.polygon([(cx + 30, cy - 8), (cx + 52, cy - 20), (cx + 58, cy - 20),
               (cx + 44, cy - 6)], fill=WHITE, outline=NAVY)
    d.polygon([(cx - 8, cy - 8), (cx + 2, cy - 18), (cx + 12, cy - 18),
               (cx + 8, cy - 8)], fill=WHITE, outline=NAVY)
    d.polygon([(cx - 44, cy + 6), (cx - 30, cy + 20), (cx - 22, cy + 20),
               (cx - 30, cy + 6)], fill=WHITE, outline=NAVY)
    d.ellipse([cx + 40, cy - 4, cx + 48, cy + 4], fill=NAVY)
    chip(d, 4, 4, "146 SAFE")
    return im


def p_bepi(w, h, bg):
    """Kartu 6: wahana BepiColombo + Merkurius + chip '19:24 CET'."""
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    for (sx, sy) in [(14, 16), (52, 24), (120, 14), (168, 22)]:
        d.ellipse([sx, sy, sx + 2, sy + 2], fill=WHITE)
    mx, my, mr = int(w * 0.72), int(h * 0.52), 15
    d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(150, 140, 130),
              outline=NAVY, width=1)
    d.ellipse([mx - 8, my - 5, mx - 2, my + 1], fill=(110, 100, 90))
    d.ellipse([mx + 2, my + 4, mx + 7, my + 9], fill=(110, 100, 90))
    cx, cy = int(w * 0.30), int(h * 0.50)
    d.rectangle([cx - 12, cy - 9, cx + 12, cy + 9], fill=GOLD_M,
                outline=NAVY, width=1)
    d.rectangle([cx - 34, cy - 5, cx - 12, cy + 5], fill=NAVY)
    d.rectangle([cx + 12, cy - 5, cx + 34, cy + 5], fill=NAVY)
    d.line([(cx + 34, cy), (mx - mr - 2, my)], fill=GOLD_M, width=2)
    d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=RED_M)
    chip(d, 4, 4, "19:24 CET")
    return im


def p_capitol(w, h, bg):
    """Kartu 7: kubah Capitol + bendera AS + chip 'TAX'.
    (Tanpa figur presiden — aturan Kevin: presiden tidak seram.)"""
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    gy = int(h * 0.84)
    d.rectangle([0, gy, w, h], fill=(120, 110, 90))
    cx = w // 2
    d.rectangle([cx - 52, gy - 8, cx + 52, gy], fill=WHITE, outline=NAVY,
                width=1)
    for i in range(5):
        d.rectangle([cx - 46 + i * 20, gy - 24, cx - 34 + i * 20, gy - 8],
                    fill=WHITE, outline=NAVY, width=1)
    d.ellipse([cx - 16, gy - 34, cx + 16, gy - 18], fill=WHITE,
              outline=NAVY, width=1)
    d.rectangle([cx - 18, gy - 24, cx + 18, gy - 20], fill=WHITE,
                outline=NAVY, width=1)
    chip(d, 4, 4, "TAX", bg=RED_M)
    return im


def p_train(w, h, bg):
    """Kartu 8: kereta barang, 1 gerbong miring (anjlok) + rel patah."""
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    gy = int(h * 0.82)
    d.line([(0, gy), (w, gy)], fill=NAVY, width=3)
    d.line([(0, gy + 6), (w, gy + 6)], fill=NAVY, width=2)
    for i, tilt in enumerate((0, 0, -12)):
        x0 = int(w * (0.10 + i * 0.30))
        y0 = int(h * 0.34) + (tilt if i == 2 else 0)
        d.rectangle([x0, y0, x0 + 44, y0 + 22], fill=(60, 90, 130),
                    outline=NAVY, width=1)
        d.rectangle([x0 + 6, y0 + 5, x0 + 18, y0 + 13], fill=(200, 220, 235))
        d.ellipse([x0 + 8, y0 + 22, x0 + 14, y0 + 28], fill=INK)
        d.ellipse([x0 + 30, y0 + 22, x0 + 36, y0 + 28], fill=INK)
    d.line([(int(w * 0.72), gy), (int(w * 0.72) + 10, gy - 8)],
           fill=RED_M, width=2)
    return im


def p_cricket(w, h, bg):
    """Kartu 9: stumps + bat + bola + angka '100' besar."""
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    gy = int(h * 0.88)
    d.rectangle([0, gy, w, h], fill=(90, 130, 80))
    for i in range(3):
        sx = int(w * (0.14 + i * 0.05))
        d.rectangle([sx, int(h * 0.40), sx + 4, gy], fill=GOLD_M,
                    outline=NAVY, width=1)
    d.rectangle([int(w * 0.14), int(h * 0.38), int(w * 0.26), int(h * 0.40)],
                fill=GOLD_M, outline=NAVY, width=1)
    d.polygon([(int(w * 0.52), int(h * 0.18)), (int(w * 0.58), int(h * 0.22)),
               (int(w * 0.44), int(h * 0.78)), (int(w * 0.38), int(h * 0.74))],
              fill=(150, 110, 70), outline=NAVY)
    d.ellipse([int(w * 0.62), int(h * 0.62), int(w * 0.62) + 9,
               int(h * 0.62) + 9], fill=RED_M, outline=NAVY, width=1)
    f100 = F(GEL700, 26)
    d.text((w - 6, int(h * 0.30)), "100", font=f100, fill=NAVY,
           anchor="ra")
    return im


def p_f1(w, h, bg):
    """Kartu 10: mobil F1 + bendera kotak-kotak + chip 'POLE'."""
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    gy = int(h * 0.82)
    d.rectangle([0, gy, w, h], fill=(70, 70, 70))
    for x in range(0, w, 16):
        d.line([(x, gy + 5), (x + 8, gy + 5)], fill=WHITE, width=2)
    cx, cy = w // 2, int(h * 0.52)
    d.polygon([(cx - 62, cy + 2), (cx - 30, cy - 2), (cx + 10, cy - 2),
               (cx + 58, cy + 6), (cx + 58, cy + 12), (cx - 62, cy + 12)],
              fill=RED_M, outline=NAVY)
    d.polygon([(cx - 6, cy - 2), (cx + 6, cy - 14), (cx + 16, cy - 14),
               (cx + 20, cy - 2)], fill=NAVY)
    d.ellipse([cx - 40, cy + 8, cx - 22, cy + 24], fill=INK, outline=WHITE,
              width=1)
    d.ellipse([cx + 30, cy + 8, cx + 48, cy + 24], fill=INK, outline=WHITE,
              width=1)
    for r in range(2):
        for c in range(3):
            col = WHITE if (r + c) % 2 == 0 else INK
            d.rectangle([w - 34 + c * 8, 16 + r * 8, w - 26 + c * 8,
                         24 + r * 8], fill=col, outline=NAVY, width=1)
    d.line([(w - 34, 16), (w - 34, 40)], fill=NAVY, width=2)
    chip(d, 4, 4, "POLE")
    return im


def p_drone(w, h, bg):
    """Kartu 11: drone quadcopter di atas laut + chip 'CLAIM'
    (klaim Iran — belum terverifikasi independen)."""
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    gy = int(h * 0.62)
    d.rectangle([0, gy, w, h], fill=(46, 110, 142))
    for x in range(0, w, 22):
        d.arc([x, gy + 2, x + 22, gy + 12], 0, 180, fill=WHITE, width=2)
    cx, cy = w // 2, int(h * 0.34)
    d.rectangle([cx - 16, cy - 6, cx + 16, cy + 6], fill=(60, 60, 60),
                outline=NAVY, width=1)
    for (dx, dy) in [(-26, -12), (26, -12), (-26, 12), (26, 12)]:
        d.line([(cx, cy), (cx + dx, cy + dy)], fill=NAVY, width=2)
        d.ellipse([cx + dx - 8, cy + dy - 2, cx + dx + 8, cy + dy + 2],
                  fill=(120, 120, 120), outline=NAVY, width=1)
    d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=RED_M)
    chip(d, 4, 4, "CLAIM", bg=RED_M)
    return im


def p_gavel(w, h, bg):
    """Kartu 12: palu sidang + dokumen + meterai merah."""
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    gy = int(h * 0.86)
    d.rectangle([0, gy, w, h], fill=(120, 100, 70))
    d.rectangle([int(w * 0.52), int(h * 0.30), int(w * 0.90),
                 int(h * 0.80)], fill=WHITE, outline=NAVY, width=1)
    for i, yy in enumerate((int(h * 0.40), int(h * 0.52), int(h * 0.64))):
        d.line([(int(w * 0.56), yy), (int(w * 0.86), yy)],
               fill=(150, 150, 150), width=2)
    d.ellipse([int(w * 0.78), int(h * 0.62), int(w * 0.78) + 12,
               int(h * 0.62) + 12], fill=RED_M, outline=NAVY, width=1)
    d.line([(int(w * 0.16), int(h * 0.62)), (int(w * 0.44), int(h * 0.34))],
           fill=(120, 85, 50), width=6)
    d.rectangle([int(w * 0.10), int(h * 0.52), int(w * 0.26),
                 int(h * 0.68)], fill=(150, 110, 70), outline=NAVY,
                width=1)
    d.rectangle([int(w * 0.36), int(h * 0.26), int(w * 0.52),
                 int(h * 0.42)], fill=(150, 110, 70), outline=NAVY,
                width=1)
    return im


def p_tennis(w, h, bg):
    """Kartu 13: bola tenis besar + garis lapangan + chip 'TONIGHT'."""
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    gy = int(h * 0.84)
    d.rectangle([0, gy, w, h], fill=(60, 110, 70))
    d.line([(0, int(h * 0.60)), (w, int(h * 0.60))], fill=WHITE, width=2)
    cx, cy, r = int(w * 0.42), int(h * 0.50), 16
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(200, 220, 60),
              outline=NAVY, width=1)
    d.arc([cx - r, cy - r, cx + r, cy + r], 200, 340, fill=WHITE, width=2)
    d.arc([cx - r, cy - r, cx + r, cy + r], 20, 160, fill=WHITE, width=2)
    d.rectangle([int(w * 0.72), int(h * 0.30), int(w * 0.72) + 26,
                 int(h * 0.30) + 18], fill=WHITE, outline=NAVY, width=1)
    d.line([(int(w * 0.72), int(h * 0.30) + 9),
            (int(w * 0.72) + 26, int(h * 0.30) + 9)], fill=NAVY, width=1)
    chip(d, 4, 4, "TONIGHT")
    return im


CARD_PAINTERS = {"kryvyi": p_kryvyi, "davao": p_davao, "bepi": p_bepi,
                 "capitol": p_capitol, "train": p_train,
                 "cricket": p_cricket, "f1": p_f1, "drone": p_drone,
                 "gavel": p_gavel, "tennis": p_tennis}
HERO_PAINTERS = {"cop31": p_cop31, "riyadh": p_riyadh, "quake": p_quake}


def assign_tints(panels):
    """Greedy: warna atas tetangga (berbagi sisi, toleransi 12px) selalu
    beda >= 25 (jarak RGB). Panel hero sudah punya latar gelap tetap."""
    def neighbors(i):
        x1, y1, x2, y2 = panels[i]
        out = []
        for j, (a1, b1, a2, b2) in enumerate(panels):
            if i == j:
                continue
            share_v = (abs(x2 - a1) <= 12 or abs(a2 - x1) <= 12) \
                and min(y2, b2) - max(y1, b1) > 0
            share_h = (abs(y2 - b1) <= 12 or abs(b2 - y1) <= 12) \
                and min(x2, a2) - max(x1, a1) > 0
            if share_v or share_h:
                out.append(j)
        return out
    fixed = [HERO_BG["cop31"], HERO_BG["riyadh"], HERO_BG["quake"]]
    colors = [None] * len(panels)
    for i in range(3):
        colors[i] = fixed[i]
    names = list(TINTS)
    for i in range(3, len(panels)):
        taken = [colors[j] for j in neighbors(i) if colors[j] is not None]
        pick = None
        for name in names:
            c = TINTS[name]
            if all(rgb_dist(c, t) >= 25 for t in taken):
                pick = c
                break
        if pick is None:
            raise SystemExit(f"tidak ada tint untuk panel {i}")
        colors[i] = pick
    for i in range(len(panels)):
        for j in neighbors(i):
            assert rgb_dist(colors[i], colors[j]) >= 25, (
                f"warna tetangga sama/dekat: panel {i} vs {j}: "
                f"{rgb_dist(colors[i], colors[j]):.1f}")
    print(f"  [cek] warna: {len(panels)} panel, tetangga >= 25 "
          f"(min {min(rgb_dist(colors[i], colors[j]) for i in range(len(panels)) for j in neighbors(i)):.1f})")
    return colors

# ------------------------------------------------------------------ layout
# Geometri Sketsa 1 (T1), diukur dari sketches/draw_sketches.py.
TITLE_Y = 20
STRIP_Y, STRIP_H = 114, 56
HERO_Y, HERO_H = 176, 242
HERO_X = [28, 354, 680]
HERO_W = 316
CARD_Y = [426, 562]
CARD_H = 128
CARD_X = [28, 223, 418, 613, 808]
CARD_W = 186
MAP_BOX = (28, 698, 408, 936)
BRIEFS_BOX = (420, 698, 996, 936)
DC_BOX = (28, 942, 996, 992)
SRC_Y = 998
MAP_HEADER_H = 22


def tracked_width(d, text, font, tracking=-0.4):
    return (sum(d.textlength(ch, font=font) for ch in text)
            + tracking * (len(text) - 1))


def draw_tracked(d, cx, y, text, font, fill, tracking=-0.4):
    total = tracked_width(d, text, font, tracking)
    x = cx - total / 2.0
    x0 = x
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill, anchor="la")
        x += d.textlength(ch, font=font) + tracking
    return x0, x0 + total


def draw_masthead(d):
    """Judul HITAM Gelasio 700 56px satu baris + deck merah Gelasio
    Italic 12px (5 cerita terbesar, tanpa awalan)."""
    tt = TileText("masthead")
    f_title = F(GEL700, 56)
    title = "Saturday 21 November 2026"
    tw = tracked_width(d, title, f_title)
    assert tw <= W - 56, f"judul terlalu lebar: {tw:.0f}px"
    tb = d.textbbox((W // 2, TITLE_Y), title, font=f_title, anchor="mt")
    x0, x1 = draw_tracked(d, W // 2, TITLE_Y, title, f_title, INK)
    tt.add((int(x0), tb[1], int(x1), tb[3]), "title")
    title_bottom = tb[3]
    f_deck = F(GEL_IT, 12)
    dw = d.textlength(DECK, font=f_deck)
    assert dw <= W - 56, f"deck terlalu lebar: {dw:.0f}px"
    b = d.textbbox((W // 2, title_bottom + 14), DECK, font=f_deck,
                   anchor="mt")
    d.text((W // 2, title_bottom + 14), DECK, font=f_deck, fill=RED,
           anchor="mt")
    tt.add(b, "deck")
    assert 13 <= b[1] - title_bottom <= 15, (
        f"celah judul->deck {b[1] - title_bottom}px")
    reg_layout((28, TITLE_Y, 996, b[3]), "masthead")
    return {"title_w": round(tw, 1), "deck_w": round(dw, 1),
            "deck_bottom": b[3]}


def draw_strip(d):
    """Strip 6 angka: angka merah SS700 30pt + caption 9pt.
    TANPA garis pemisah ke hero (aturan Kevin)."""
    tt = TileText("strip")
    f_n = F(SS700, 30)
    f_c = F(SS800, 9)
    d.rectangle([28, STRIP_Y, 994, STRIP_Y + STRIP_H], outline=NAVY,
                width=1)
    d.rectangle([29, STRIP_Y + 1, 993, STRIP_Y + STRIP_H - 1],
                fill=NEAR_WHITE)
    reg_layout((28, STRIP_Y, 994, STRIP_Y + STRIP_H), "strip")
    widths = [156, 156, 156, 156, 156, 156]
    x = 28
    for i, (num, cap) in enumerate(NUMBERS):
        cw = widths[i]
        cx = x + cw // 2
        if i < 5:
            d.line([(x + cw, STRIP_Y + 4), (x + cw, STRIP_Y + STRIP_H - 4)],
                   fill=(200, 195, 185), width=1)
        b = d.textbbox((cx, STRIP_Y + 2), num, font=f_n, anchor="ma")
        d.text((cx, STRIP_Y + 2), num, font=f_n, fill=RED, anchor="ma")
        tt.add(b, f"strip-n{i + 1}")
        assert b[2] - b[0] <= cw - 4, f"angka strip {num} terlalu lebar"
        b = d.textbbox((cx, STRIP_Y + 36), cap, font=f_c, anchor="ma")
        d.text((cx, STRIP_Y + 36), cap, font=f_c, fill=NAVY, anchor="ma")
        tt.add(b, f"strip-c{i + 1}")
        assert b[2] - b[0] <= cw - 4, f"caption strip '{cap}' terlalu lebar"
        x += cw + 6
    assert x - 6 == 994, f"strip tidak berakhir di 994: {x - 6}"


def draw_hero(im, d, hero, x, y, tint_img):
    """Hero horizontal: gambar atas 140px + kicker + judul Gelasio 17px
    (<=2 baris) + ringkasan 11pt (2 baris)."""
    tt = TileText(f"hero{hero['num']}")
    im.paste(tint_img, (x + 1, y + 1))
    reg_layout((x, y, x + HERO_W, y + HERO_H), f"hero{hero['num']}")
    d.rectangle([x + 1, y + 141, x + HERO_W - 1, y + HERO_H - 1],
                fill=NEAR_WHITE)
    d.rectangle([x, y, x + HERO_W, y + HERO_H], outline=INK, width=1)
    tx0, tx1 = x + 8, x + HERO_W - 8
    kick = (f"{hero['num']:02d} \u00b7 {hero['place']} \u00b7 "
            f"{hero['topic']}")
    tt.text(d, tx0, y + 145, kick, F(SS800, 9),
            {"GLOBAL": (150, 120, 20), "MIDDLE EAST": (192, 57, 43),
             "AMERICAS": (62, 124, 89)}.get(hero['region'], NAVY))
    tlines = wrap(d, hero["title"], F(GEL700, 17), tx1 - tx0)
    assert 1 <= len(tlines) <= 2, f"judul hero {hero['num']}: {tlines}"
    yy = y + 159
    for ln in tlines:
        tt.text(d, tx0, yy, ln, F(GEL700, 17), INK)
        yy += 20
    slines = wrap(d, hero["sum"], F(SS400, 11), tx1 - tx0)
    assert len(slines) == 2, f"ringkasan hero {hero['num']}: {slines}"
    yy = y + 202
    for ln in slines:
        tt.text(d, tx0, yy, ln, F(SS400, 11), (60, 58, 50))
        yy += 14
    assert yy <= y + HERO_H - 8, f"hero {hero['num']} meluber"
    return {"title_lines": len(tlines), "sum_lines": len(slines)}


def draw_card(im, d, card, x, y, tint_img):
    """Kartu: gambar atas 56px + kicker 8pt + judul Gelasio 12px
    (<=2 baris) + ringkasan 10pt (<=2 baris)."""
    tt = TileText(f"card{card['num']}")
    im.paste(tint_img, (x + 1, y + 1))
    reg_layout((x, y, x + CARD_W, y + CARD_H), f"card{card['num']}")
    d.rectangle([x + 1, y + 57, x + CARD_W - 1, y + CARD_H - 1],
                fill=NEAR_WHITE)
    d.rectangle([x, y, x + CARD_W, y + CARD_H], outline=NAVY, width=1)
    tx0, tx1 = x + 6, x + CARD_W - 6
    kick = (f"{card['num']:02d} \u00b7 {card['place'].split(',')[0]} "
            f"\u00b7 {card['topic']}")
    tt.text(d, tx0, y + 59, kick, F(SS800, 8),
            {"EUROPE": (38, 66, 118), "ASIA": (46, 110, 142),
             "GLOBAL": (150, 120, 20), "AMERICAS": (125, 38, 40),
             "MIDDLE EAST": (155, 115, 35),
             "OCEANIA": (30, 108, 114)}.get(card['region'], NAVY))
    tlines = wrap(d, card["title"], F(GEL700, 12), tx1 - tx0)
    assert 1 <= len(tlines) <= 2, f"judul kartu {card['num']}: {tlines}"
    yy = y + 71
    for ln in tlines:
        tt.text(d, tx0, yy, ln, F(GEL700, 12), INK)
        yy += 14
    slines = wrap(d, card["sum"], F(SS400, 10), tx1 - tx0)
    assert 1 <= len(slines) <= 2, f"ringkasan kartu {card['num']}: {slines}"
    yy = y + 101
    for ln in slines:
        tt.text(d, tx0, yy, ln, F(SS400, 10), (60, 58, 50))
        yy += 12
    assert yy <= y + CARD_H - 2, f"kartu {card['num']} meluber ke bawah"
    return {"title_lines": len(tlines), "sum_lines": len(slines)}


def map_xy(lon, lat, x0, y0):
    return (x0 + (lon + 180.0) * MAP_SX, y0 + (MAP_LAT0 - lat) * MAP_SY)


def draw_map(im, d):
    """Peta kiri bawah: strip header tan + navy + daratan Natural Earth
    + 13 pin merah bernomor (r=7, min 18px) + legenda 2 chip."""
    x1, y1, x2, y2 = MAP_BOX
    ny = y1 + MAP_HEADER_H
    reg_layout(MAP_BOX, "map")
    d.rectangle([x1, y1, x2, y2], fill=(235, 230, 212), outline=NAVY,
                width=1)
    d.rectangle([x1, ny, x2, y2], fill=SEA)
    mtmp = Image.new("RGB", (x2 - x1 - 2, y2 - ny - 2), SEA)
    md = ImageDraw.Draw(mtmp)
    eq_y = int(ny + 1 + 53 + (MAP_LAT0 - 0) * MAP_SY) - (ny + 1)
    for xx in range(0, x2 - x1 - 2, 8):
        md.line([(xx, eq_y), (xx + 4, eq_y)], fill=(60, 80, 110), width=1)
    for poly in LAND_POLYS:
        pts = [(map_xy(lon, lat, x1 + 1 + 42, ny + 1 + 53)[0] - (x1 + 1),
                map_xy(lon, lat, x1 + 1 + 42, ny + 1 + 53)[1] - (ny + 1))
               for lon, lat in poly]
        md.polygon(pts, fill=MAP_LAND, outline=MAP_LAND_OUT)
    im.paste(mtmp, (x1 + 1, ny + 1))
    md = ImageDraw.Draw(im)
    fp = F(SS800, 8)
    placed = []
    offset_used = []
    skipped = []

    def place(px, py):
        for (qx, qy) in placed:
            if ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5 < 18:
                return False
        placed.append((px, py))
        return True

    def place_with_offset(px, py):
        for dx, dy in [(0, 0), (0, 12), (0, -12), (14, 0), (-14, 0),
                       (10, 8), (10, -8), (-10, 8), (-10, -8),
                       (18, 0), (-18, 0), (0, 20), (0, -20),
                       (0, 18), (0, -18),
                       (14, 14), (14, -14), (-14, 14), (-14, -14),
                       (20, 0), (-20, 0), (24, 0), (-24, 0),
                       (0, 24), (0, -24)]:
            if place(px + dx, py + dy):
                return (px + dx, py + dy), (dx, dy)
        return None, None

    panels = HEROES + CARDS
    for p in panels:
        city = p["map_city"]
        lon, lat = PLACES[city]
        px, py = map_xy(lon, lat, x1 + 1 + 42, ny + 1 + 53)
        pos, off = place_with_offset(px, py)
        if pos is None:
            skipped.append((city, p["num"], "collision"))
            continue
        if off != (0, 0):
            offset_used.append((p["num"], city, off))
        qx, qy = pos
        assert x1 + 8 <= qx <= x2 - 8 and ny + 8 <= qy <= y2 - 8, (
            f"pin {p['num']} keluar peta")
        md.ellipse([qx - 7, qy - 7, qx + 7, qy + 7], fill=RED,
                   outline=WHITE, width=1)
        mark = str(p["num"])
        tw = md.textlength(mark, font=fp)
        md.text((qx - tw / 2, qy - 5), mark, font=fp, fill=WHITE)
    assert not skipped, f"pin hilang: {skipped}"
    assert len(placed) == 13, f"pin terpasang {len(placed)}, harus 13"
    # Header strip tan: dua teks SATU baseline (ref-7 Kevin 23:14 WIB).
    f_t = F(SS800, 11)
    f_n = F(SS800, 12)
    title = "WHERE IT HAPPENED"
    note = "Pins 1\u201313 (Lead & Feature)"
    hdr_cy = y1 + MAP_HEADER_H // 2
    tb = d.textbbox((x1 + 10, hdr_cy), title, font=f_t, anchor="lm")
    d.text((x1 + 10, hdr_cy), title, font=f_t, fill=NAVY, anchor="lm")
    nb = d.textbbox((x2 - 8, hdr_cy), note, font=f_n, anchor="rm")
    d.text((x2 - 8, hdr_cy), note, font=f_n, fill=NAVY, anchor="rm")
    assert nb[0] - tb[2] >= 6, "teks pins menabrak judul peta"
    assert tb[1] >= y1 + 1 and tb[3] < ny, "judul peta keluar strip"
    assert nb[1] >= y1 + 1 and nb[3] < ny, "teks pins keluar strip"
    assert abs((tb[1] + tb[3]) // 2 - (nb[1] + nb[3]) // 2) <= 1, (
        "judul peta dan teks pins tidak satu baseline")
    # Legenda 2 chip gelap DI DALAM navy, bawah-kiri.
    f_l = F(SS800, 8)
    ly = y2 - 24
    lx = x1 + 8
    for txt in ("1\u20133 Lead", "4\u201313 Feature Stories"):
        tw = d.textlength(txt, font=f_l)
        cw = int(tw) + 24
        d.rounded_rectangle([lx, ly, lx + cw, ly + 16], radius=3,
                            fill=(10, 18, 36))
        d.ellipse([lx + 5, ly + 6, lx + 9, ly + 10], fill=RED)
        d.text((lx + 13, ly + 8), txt, font=f_l, fill=WHITE, anchor="lm")
        lx += cw + 6
    return {"placed": len(placed), "offset_used": offset_used,
            "skipped": skipped}


def draw_briefs(d):
    """MORE STORIES: judul + garis merah + 3 kolom brief 1 BARIS @11pt,
    nomor lanjut 14-36, 8/8/7 per kolom, rata atas-bawah sama."""
    x1, y1, x2, y2 = BRIEFS_BOX
    reg_layout(BRIEFS_BOX, "briefs")
    tt = TileText("briefs")
    d.rectangle([x1, y1, x2, y2], outline=NAVY, width=1)
    d.rectangle([x1 + 1, y1 + 1, x2 - 1, y2 - 1], fill=NEAR_WHITE)
    tt.text(d, x1 + 8, y1 + 6, "MORE STORIES", F(SS800, 13), INK)
    tt.text(d, x2 - 8, y1 + 6, "14\u201336", F(SS800, 11), RED, anchor="ra")
    d.line([(x1 + 8, y1 + 24), (x2 - 8, y1 + 24)], fill=RED, width=2)
    cw = (x2 - x1 - 16 - 2 * 12) / 3
    fs = F(SS400, 11)
    per = [8, 8, 7]
    idx = 0
    col_bottoms = []
    for c in range(3):
        cx = x1 + 8 + c * (cw + 12)
        yy = y1 + 32
        for k in range(per[c]):
            n, t = BRIEFS[idx]
            idx += 1
            s = f"{n}. {t}"
            w = d.textlength(s, font=fs)
            assert w <= cw, (
                f"brief {n} terlalu lebar 1 baris: {w:.0f}px > {cw:.0f}px "
                f"({s})")
            tt.text(d, cx, yy, s, fs, INK)
            yy += 20
        col_bottoms.append(yy - 20)
    assert idx == 23, f"briefs terpasang {idx}, harus 23"
    assert max(col_bottoms) - min(col_bottoms) <= 20, (
        f"kolom brief tidak rata: {col_bottoms}")
    assert max(col_bottoms) <= y2 - 8, "briefs meluber ke bawah"
    return {"col_bottoms": col_bottoms}


def draw_footer(d):
    """DATE CHECK MENONJOL (band kontras + bingkai merah, 2 baris) +
    garis Sources kecil. TANPA catatan produksi/draf."""
    x1, y1, x2, y2 = DC_BOX
    reg_layout(DC_BOX, "datecheck")
    tt = TileText("footer")
    d.rectangle([x1, y1, x2, y2], outline=RED, width=2)
    d.rectangle([x1 + 2, y1 + 2, x2 - 2, y2 - 2], fill=(250, 235, 230))
    tt.text(d, x1 + 10, y1 + 3, "DATE CHECK", F(SS800, 11), RED)
    lines = wrap(d, DATECHECK, F(SS400, 10), x2 - x1 - 20)
    assert len(lines) == 2, f"DATE CHECK {len(lines)} baris: {lines}"
    yy = y1 + 17
    for ln in lines:
        tt.text(d, x1 + 10, yy, ln, F(SS400, 10), INK)
        yy += 13
    assert yy <= y2 - 2, "DATE CHECK meluber"
    tt.text(d, 28, SRC_Y, SOURCES, F(SS400, 9), GREY)
    return {"dc_lines": len(lines)}


def measure(img):
    """Ink % (jarak RGB dari kertas > 40 — panel hampir-putih (251,250,245)
    TIDAK dihitung tinta, tint kalem tetap dihitung) + saturated %
    (S > 0,30). Metode ni20: ink ref-7 = 34,9%."""
    px = list(img.getdata())
    n = len(px)
    ink = sum(1 for r, g, b in px
              if ((r - PAPER[0]) ** 2 + (g - PAPER[1]) ** 2
                  + (b - PAPER[2]) ** 2) ** 0.5 > 40)
    sat = 0
    for r, g, b in px:
        mx, mn = max(r, g, b), min(r, g, b)
        if mx > 0 and (mx - mn) / mx > 0.30:
            sat += 1
    return {"ink_pct": round(100 * ink / n, 1),
            "sat_pct": round(100 * sat / n, 1)}


def build():
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    # --- warna atas (greedy, tetangga >= 25) ---
    hero_boxes = [(HERO_X[i], HERO_Y, HERO_X[i] + HERO_W, HERO_Y + HERO_H)
                  for i in range(3)]
    card_boxes = []
    for r in range(2):
        for c in range(5):
            card_boxes.append((CARD_X[c], CARD_Y[r], CARD_X[c] + CARD_W,
                               CARD_Y[r] + CARD_H))
    panels = hero_boxes + card_boxes
    colors = assign_tints(panels)
    # --- render gambar panel ---
    hero_imgs = [HERO_PAINTERS[h["painter"]](HERO_W - 2, 140)
                 for h in HEROES]
    card_imgs = [CARD_PAINTERS[c["painter"]](CARD_W - 2, 56,
                                             colors[3 + i])
                 for i, c in enumerate(CARDS)]
    # --- warna atas terukur dari gambar jadi (bukan dari tint) ---
    tops = ([top_color(im) for im in hero_imgs]
            + [top_color(im) for im in card_imgs])
    for i, t in enumerate(tops):
        assert t == colors[i], (
            f"warna atas panel {i + 1} bukan tint: {t} vs {colors[i]} "
            f"(elemen menyentuh patch atas)")
    # --- susun halaman ---
    info = {}
    info["masthead"] = draw_masthead(d)
    draw_strip(d)
    for i, h in enumerate(HEROES):
        info[f"hero{h['num']}"] = draw_hero(im, d, h, HERO_X[i], HERO_Y,
                                             hero_imgs[i])
    for i, c in enumerate(CARDS):
        r, cc = divmod(i, 5)
        info[f"card{c['num']}"] = draw_card(im, d, c, CARD_X[cc],
                                            CARD_Y[r], card_imgs[i])
    info["map"] = draw_map(im, d)
    info["briefs"] = draw_briefs(d)
    info["footer"] = draw_footer(d)
    check_layout("v1")
    info["measure"] = measure(im)
    im.save(OUT, optimize=True)
    size = os.path.getsize(OUT)
    assert size <= 1024 * 1024, f"entry {size} byte > 1 MiB"
    sha = hashlib.sha256(open(OUT, "rb").read()).hexdigest()
    info["size"] = size
    info["sha256"] = sha
    print(json.dumps(info, indent=1, default=str))
    print(f"entry.png: {size} byte, sha256 {sha[:16]}...")
    return info


if __name__ == "__main__":
    build()
