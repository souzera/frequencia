"""Generate the vector brand mark and multi-resolution Windows icon."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
assets = ROOT / 'desktop' / 'ui' / 'assets'
assets.mkdir(parents=True, exist_ok=True)

CANVAS = 256
size = 1024
scale = size / CANVAS

BLUE_TOP = (91, 123, 255)
BLUE_BOTTOM = (52, 74, 199)

image = Image.new('RGBA', (size, size))
mask = Image.new('L', (size, size))
ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=60 * scale, fill=255)
draw = ImageDraw.Draw(image)
for y in range(size):
    t = y / (size - 1)
    color = tuple(round(a + (b - a) * t) for a, b in zip(BLUE_TOP, BLUE_BOTTOM))
    draw.line((0, y, size, y), fill=(*color, 255))
image.putalpha(mask)

# Equalizer bars: an odd count peaking in the middle, evoking an audio frequency display.
bar_width = 20
gap = 14
heights = (56, 96, 140, 96, 56)
center_y = CANVAS / 2
total_width = bar_width * len(heights) + gap * (len(heights) - 1)
start_x = (CANVAS - total_width) / 2

bars_svg = []
for i, h in enumerate(heights):
    x0 = start_x + i * (bar_width + gap)
    x1 = x0 + bar_width
    y0 = center_y - h / 2
    y1 = center_y + h / 2
    draw.rounded_rectangle(
        (x0 * scale, y0 * scale, x1 * scale, y1 * scale),
        radius=bar_width / 2 * scale,
        fill='white',
    )
    bars_svg.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{bar_width}" height="{h}" rx="{bar_width / 2}" fill="white"/>')

svg = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">'
    '<defs><linearGradient id="blue" x2="0" y2="1">'
    f'<stop stop-color="rgb{BLUE_TOP}"/><stop offset="1" stop-color="rgb{BLUE_BOTTOM}"/></linearGradient></defs>'
    '<rect width="256" height="256" rx="60" fill="url(#blue)"/>'
    + ''.join(bars_svg) +
    '</svg>\n'
)
(assets / 'frequencia.svg').write_text(svg, encoding='utf-8')
image.resize((512, 512), Image.Resampling.LANCZOS).save(assets / 'frequencia.png')
image.save(assets / 'frequencia.ico', sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
print('Generated SVG, PNG and ICO in', assets)
