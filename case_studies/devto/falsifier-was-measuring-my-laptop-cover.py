from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 627
FONDO = (10, 13, 18)
TINTA = (247, 249, 252)
GRIS = (154, 167, 184)
ACENTO = (46, 230, 168)
MONO = "/System/Library/Fonts/Menlo.ttc"
SANS = "/System/Library/Fonts/SFNS.ttf"


def f_mono(size, bold=False):
    return ImageFont.truetype(MONO, size, index=1 if bold else 0)


def f_sans(size, bold=False):
    f = ImageFont.truetype(SANS, size)
    if bold:
        try:
            f.set_variation_by_name("Bold")
        except Exception:
            pass
    return f


img = Image.new("RGB", (W, H), FONDO)
d = ImageDraw.Draw(img)

# retícula tenue
for x in range(0, W, 40):
    d.line([(x, 0), (x, H)], fill=(18, 23, 31))
for y in range(0, H, 40):
    d.line([(0, y), (W, y)], fill=(18, 23, 31))

# viñeta cálida
glow = Image.new("RGB", (W, H), FONDO)
gd = ImageDraw.Draw(glow)
gd.ellipse([W - 520, -260, W + 260, 420], fill=(18, 46, 40))
img = Image.blend(img, glow, 0.45)
d = ImageDraw.Draw(img)

# franja de acento
d.rectangle([0, 0, 7, H], fill=ACENTO)

M = 74
# cabecera
d.text((M, 62), "AUDITOR-TOOLKIT", font=f_mono(21, True), fill=ACENTO)
cab = "case study · metrology of invariants"
w_cab = d.textlength(cab, font=f_mono(17))
d.text((W - M - w_cab, 64), cab, font=f_mono(17), fill=GRIS)

# título, ajustando tamaño a 2 líneas
titulo = "My falsifier was measuring my laptop"
for size in range(88, 44, -2):
    f = f_sans(size, True)
    if d.textlength(titulo, font=f) <= W - 2 * M:
        break
d.text((M, 138), titulo, font=f, fill=TINTA)
y = 138 + size + 26

d.line([(M, y), (M + 120, y)], fill=ACENTO, width=4)
y += 34

sub = [
    "A fixture that recorded who measured. A verifier that counted",
    "commented-out text as published. Both checks passed.",
]
f_sub = f_sans(30)
for linea in sub:
    d.text((M, y), linea, font=f_sub, fill=GRIS)
    y += 44

# pie con cifras del artículo
y_pie = H - 104
d.line([(M, y_pie - 26), (W - M, y_pie - 26)], fill=(28, 35, 46), width=2)
d.text((M, y_pie), "250 states  ·  4,270 values compared", font=f_mono(19), fill=(120, 134, 152))
d.text((M, y_pie + 30), "Monte Carlo n=8000  ·  seed 20261113", font=f_mono(19), fill=(88, 100, 116))
url = "dev.to/alexisromtz7"
w_url = d.textlength(url, font=f_mono(19))
d.text((W - M - w_url, y_pie), url, font=f_mono(19), fill=ACENTO)

img.save("/tmp/cover_falsifier.png", optimize=True)
print("guardada", img.size, "bytes", __import__("os").path.getsize("/tmp/cover_falsifier.png"))
