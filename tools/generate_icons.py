"""Generate the PWA icon set from one drawing routine.

The app ships an SVG icon, but the platforms that actually install it do not
accept SVG everywhere:

* iOS ignores ``apple-touch-icon`` when it is an SVG and refuses transparency,
  so it needs a 180x180 opaque PNG.
* Chrome and Android want 192/512 PNGs, plus a separate "maskable" PNG whose
  artwork stays inside the safe zone (the centre 80% circle).

Run this with the project's virtualenv to regenerate everything:

    .venv/Scripts/python.exe tools/generate_icons.py

Outputs are committed, so a plain checkout needs no Pillow and no network.
"""

from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw

# Palette shared with docs/icon.svg and docs/styles.css.
INK = (11, 15, 20)
GREEN = (76, 201, 160)
BLUE = (47, 143, 208)
LIGHT = (234, 246, 255)
RED = (255, 92, 108)

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"

# Silhouette of the shield, in the 64x64 coordinate space of the SVG.
SHIELD = [
    (32, 6),
    (12, 14),
    (12, 30),
    (14, 38),
    (18, 45.5),
    (24, 51),
    (32, 56.3),
    (40, 51),
    (46, 45.5),
    (50, 38),
    (52, 30),
    (52, 14),
]


def _scaled(points: list[tuple[float, float]], size: int, scale: float, offset: float) -> list[tuple[float, float]]:
    """Map viewBox coordinates onto a canvas of ``size`` px, centred and scaled."""
    unit = size / 64.0 * scale
    margin = (size - 64.0 * unit) / 2.0
    return [(p[0] * unit + margin, p[1] * unit + margin + offset) for p in points]


def _gradient(size: int) -> Image.Image:
    """Diagonal green -> blue gradient, used as the fill of the shield."""
    grad = Image.new("RGB", (64, 64))
    px = grad.load()
    for y in range(64):
        for x in range(64):
            t = (x + y) / 126.0
            px[x, y] = tuple(round(GREEN[i] + (BLUE[i] - GREEN[i]) * t) for i in range(3))
    return grad.resize((size, size), Image.Resampling.BICUBIC)


def _shield_layer(size: int, scale: float) -> Image.Image:
    """The shield with its gradient fill, dark inset and the small scene."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    outer = _scaled(SHIELD, size, scale, 0.0)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).polygon(outer, fill=245)
    layer.paste(_gradient(size), (0, 0), mask)

    # Inner shield, drawn dark so the motif reads at small sizes.
    unit = size / 64.0 * scale
    margin = (size - 64.0 * unit) / 2.0
    inner_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(inner_mask).polygon(_scaled(SHIELD, size, scale * 0.78, 1.0), fill=150)
    layer.paste(Image.new("RGBA", (size, size), (*INK, 255)), (0, 0), inner_mask)

    draw = ImageDraw.Draw(layer)

    def pt(x: float, y: float) -> tuple[float, float]:
        return (x * unit + margin, y * unit + margin)

    # Sun and mountains: the "photo" that stays inside the shield.
    sun = pt(24.5, 25.5)
    r = 3.5 * unit
    draw.ellipse([sun[0] - r, sun[1] - r, sun[0] + r, sun[1] + r], fill=LIGHT)
    mountains = [pt(20.5, 41), pt(30, 29.5), pt(36, 37), pt(40, 32.5), pt(45.5, 41)]
    draw.polygon(mountains, fill=LIGHT)

    # The red strike-through is the whole point: metadata removed.
    width = max(2, round(4.5 * unit))
    draw.line([pt(14, 50), pt(50, 12)], fill=RED, width=width)
    for cap in (pt(14, 50), pt(50, 12)):
        draw.ellipse([cap[0] - width / 2, cap[1] - width / 2, cap[0] + width / 2, cap[1] + width / 2], fill=RED)

    return layer


def rounded(size: int, radius_ratio: float, background: tuple[int, int, int], shield_scale: float) -> Image.Image:
    """A maskable/rounded icon: solid background plus a centred shield."""
    img = Image.new("RGBA", (size, size), (*background, 255))
    img.alpha_composite(_shield_layer(size, shield_scale))
    if radius_ratio:
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=round(size * radius_ratio), fill=255)
        img.putalpha(mask)
    return img


def main() -> None:
    DOCS.mkdir(exist_ok=True)

    # In-app / Android: rounded square, artwork filling most of the canvas.
    rounded(192, 14 / 64, INK, 1.0).save(DOCS / "icon-192.png")
    rounded(512, 14 / 64, INK, 1.0).save(DOCS / "icon-512.png")

    # Maskable: no rounding, artwork inside the safe zone so Android can crop
    # it to any shape without cutting the shield.
    rounded(512, 0.0, INK, 0.78).save(DOCS / "icon-maskable-512.png")

    # iOS: opaque square, iOS applies its own corner mask.
    rounded(180, 0.0, INK, 0.82).convert("RGB").save(DOCS / "apple-touch-icon.png")

    for name in ("icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png"):
        path = DOCS / name
        with Image.open(path) as im:
            print(f"{name}: {im.size[0]}x{im.size[1]} {im.mode}")


if __name__ == "__main__":
    main()
