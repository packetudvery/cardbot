"""Генерирует 5 тестовых PNG-картинок в папку docs/cards/. Замените их своими артами с теми же именами."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "docs" / "cards"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 600, 840
CARDS = [  # файл, название, (цвет сверху, цвет снизу)
    ("ash_fox.png", "Пепельный лис", ((90, 90, 110), (30, 30, 45))),
    ("moon_owl.png", "Лунная сова", ((70, 100, 160), (20, 25, 60))),
    ("crystal_golem.png", "Кристальный голем", ((40, 170, 190), (10, 50, 70))),
    ("storm_dragon.png", "Штормовой дракон", ((150, 70, 210), (40, 15, 80))),
    ("gold_phoenix.png", "Золотой феникс", ((255, 190, 60), (170, 50, 20))),
]

def font(size):
    for name in ("DejaVuSans-Bold.ttf", "arial.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size)

for fname, title, (top, bot) in CARDS:
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    d.ellipse((150, 200, 450, 500), fill=(255, 255, 255))
    d.rounded_rectangle((20, 20, W - 20, H - 20), radius=30, outline=(255, 255, 255), width=6)
    f = font(46)
    w = d.textlength(title, font=f)
    d.text(((W - w) / 2, 620), title, font=f, fill=(255, 255, 255))
    img.save(OUT / fname)
    print("ok", fname)
