from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

out = Path(r'F:\project\clawd-demo\workspace\generated')
out.mkdir(parents=True, exist_ok=True)
img_path = out / 'jerusalem_weather.png'

w, h = 1280, 720
img = Image.new('RGB', (w, h), (210, 220, 235))
d = ImageDraw.Draw(img)

for y in range(h):
    c = int(210 - y * 40 / h)
    d.line([(0, y), (w, y)], fill=(c, c + 5, c + 15))

for i, color in enumerate([(150, 145, 140), (170, 160, 150), (190, 180, 170)]):
    y0 = 420 + i * 40
    d.polygon([
        (0, y0 + 40), (180, y0 - 20), (360, y0 + 30), (560, y0 - 10),
        (760, y0 + 25), (980, y0 - 15), (1280, y0 + 35), (1280, 720), (0, 720)
    ], fill=color)

blocks = [
    (120, 430, 220, 620), (240, 400, 340, 620), (360, 450, 470, 620),
    (520, 390, 650, 620), (700, 420, 810, 620), (840, 380, 960, 620),
    (990, 440, 1110, 620)
]
for b in blocks:
    d.rectangle(b, fill=(196, 185, 165), outline=(150, 140, 120))
    for wy in range(b[1] + 20, b[3] - 10, 40):
        for wx in range(b[0] + 15, b[2] - 10, 30):
            d.rectangle((wx, wy, wx + 12, wy + 18), fill=(120, 110, 95))

overlay = Image.new('RGBA', (w, h), (235, 235, 235, 0))
od = ImageDraw.Draw(overlay)
for y in range(200, 650, 8):
    a = min(int(20 + (y - 200) * 0.12), 90)
    od.rectangle((0, y, w, y + 6), fill=(230, 230, 230, a))
img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
d = ImageDraw.Draw(img)

try:
    font_big = ImageFont.truetype('arial.ttf', 56)
    font_mid = ImageFont.truetype('arial.ttf', 34)
    font_small = ImageFont.truetype('arial.ttf', 26)
except Exception:
    font_big = ImageFont.load_default()
    font_mid = ImageFont.load_default()
    font_small = ImageFont.load_default()

d.rounded_rectangle((70, 70, 760, 280), radius=24, fill=(255, 255, 255), outline=(220, 220, 220), width=2)
d.text((110, 105), 'Jerusalem Weather', fill=(60, 60, 60), font=font_big)
d.text((110, 175), 'Hazy | 11C', fill=(80, 80, 80), font=font_mid)
d.text((110, 220), 'Feels like 10C | ENE 14 km/h | Humidity 87% | Rain 0.0 mm', fill=(90, 90, 90), font=font_small)

img.save(img_path)
print(img_path)
