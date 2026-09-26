"""Generate the vector brand mark and multi-resolution Windows icon."""
from pathlib import Path
import math
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
assets = ROOT / 'desktop' / 'ui' / 'assets'
assets.mkdir(parents=True, exist_ok=True)
size = 1024
scale = size / 256
image = Image.new('RGBA', (size, size))
mask = Image.new('L', (size, size))
ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=60 * scale, fill=255)
draw = ImageDraw.Draw(image)
for y in range(size):
    t = y / (size - 1)
    color = tuple(round(a + (b - a) * t) for a, b in zip((83, 111, 249), (53, 77, 205)))
    draw.line((0, y, size, y), fill=(*color, 255))
image.putalpha(mask)
paths = []
for center in (85, 128, 171):
    points = [(x, center - 13 * math.sin((x - 51) / 154 * 2 * math.pi)) for x in range(51, 206)]
    draw.line([(round(x * scale), round(y * scale)) for x, y in points], fill='white', width=round(13 * scale), joint='curve')
    for x, y in (points[0], points[-1]):
        r = 6.5 * scale
        draw.ellipse((x * scale-r, y * scale-r, x * scale+r, y * scale+r), fill='white')
    paths.append('M ' + ' L '.join(f'{x},{y:.3f}' for x, y in points))
svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><defs><linearGradient id="blue" x2="0" y2="1"><stop stop-color="#536ff9"/><stop offset="1" stop-color="#354dcd"/></linearGradient></defs><rect width="256" height="256" rx="60" fill="url(#blue)"/>'
svg += ''.join(f'<path d="{path}" fill="none" stroke="white" stroke-width="13" stroke-linecap="round" stroke-linejoin="round"/>' for path in paths)
svg += '</svg>\n'
(assets / 'frequencia.svg').write_text(svg, encoding='utf-8')
image.resize((512, 512), Image.Resampling.LANCZOS).save(assets / 'frequencia.png')
image.save(assets / 'frequencia.ico', sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
print('Generated SVG, PNG and ICO in', assets)
