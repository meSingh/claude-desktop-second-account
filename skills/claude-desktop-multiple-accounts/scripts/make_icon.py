#!/usr/bin/env python3
"""Build a macOS app icon (.icns) for an extra Claude instance.

Styles
  logo    (default) Your own logo on a rounded-square tile. Uses no Anthropic
          artwork, so it is the safe choice for anything you share.
  mashup  Claude's installed icon, recoloured, with your logo as a corner badge.
          Read from the user's own Claude.app at run time (never bundled).
          Altering Anthropic's logo is not allowed by their trademark
          guidelines for shared materials, so keep this to a private icon on
          your own Mac.

Usage
  make_icon.py --logo LOGO.png|svg --out NAME.icns [--style logo|mashup]
               [--bg #RRGGBB] [--fg #RRGGBB] [--accent #RRGGBB] [--preview PNG]

Logos can be a PNG/JPG with transparency, a logo on a solid background, or an
SVG (rendered with macOS Quick Look). Needs Pillow: python3 -m pip install --user pillow
"""
import argparse, os, plistlib, shutil, subprocess, sys, tempfile

try:
    from PIL import Image, ImageChops, ImageDraw, ImageOps
except ImportError:
    sys.exit("Pillow is required: python3 -m pip install --user pillow")

SIZE = 1024
CLAUDE_APP = "/Applications/Claude.app"


def hex_rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def load_logo(path, tmp):
    """Return a Pillow image of the logo, rendering SVG through Quick Look."""
    if path.lower().endswith(".svg"):
        subprocess.run(["qlmanage", "-t", "-s", str(SIZE), "-o", tmp, path],
                       check=True, capture_output=True)
        path = os.path.join(tmp, os.path.basename(path) + ".png")
    return Image.open(path).convert("RGBA")


def glyph_mask(img):
    """Grayscale mask of the logo's shape, whatever background it came on."""
    alpha = img.getchannel("A")
    if alpha.getextrema()[0] < 250:          # real transparency: trust it
        mask = alpha
    else:                                    # opaque: separate from corner colour
        rgb = img.convert("RGB")
        w, h = rgb.size
        corners = [rgb.getpixel(p) for p in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3))]
        bg = tuple(sorted(c[i] for c in corners)[1] for i in range(3))
        diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, bg)).convert("L")
        # Stretch to the logo's actual contrast: Quick Look flattens SVGs onto
        # white, so a white logo can differ from its background by only a few levels.
        peak = diff.getextrema()[1]
        if peak < 20:
            print("note: very low-contrast logo; a PNG with transparency will look cleaner", file=sys.stderr)
        gain = 255 / max(1, peak * 0.6)
        mask = diff.point(lambda v: min(255, int(v * gain)))
    box = mask.point(lambda v: 255 if v > 40 else 0).getbbox()
    if not box:
        sys.exit("Could not find a logo shape in the image.")
    return mask.crop(box)


def fit(mask, max_w, max_h):
    scale = min(max_w / mask.width, max_h / mask.height)
    return mask.resize((max(1, int(mask.width * scale)), max(1, int(mask.height * scale))), Image.LANCZOS)


def tile_mask():
    """macOS-style rounded square: 824px tile inside a 1024 canvas."""
    m = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(m).rounded_rectangle([100, 100, 924, 924], radius=185, fill=255)
    return m


def style_logo(logo, bg, fg):
    shape = tile_mask()
    grad = Image.linear_gradient("L").resize((SIZE, SIZE))
    lighter = tuple(min(255, int(c * 1.15 + 12)) for c in bg)
    base = Image.composite(Image.new("RGB", (SIZE, SIZE), bg), Image.new("RGB", (SIZE, SIZE), lighter), grad)
    out = base.convert("RGBA")
    g = fit(glyph_mask(logo), 520, 520)
    out.paste(Image.new("RGBA", g.size, fg + (255,)), ((SIZE - g.width) // 2, (SIZE - g.height) // 2), g)
    out.putalpha(shape)
    return out


def claude_icon(tmp):
    info = plistlib.load(open(os.path.join(CLAUDE_APP, "Contents/Info.plist"), "rb"))
    icns = os.path.join(CLAUDE_APP, "Contents/Resources", info["CFBundleIconFile"].removesuffix(".icns") + ".icns")
    iconset = os.path.join(tmp, "claude.iconset")
    subprocess.run(["iconutil", "-c", "iconset", icns, "-o", iconset], check=True)
    return Image.open(os.path.join(iconset, "icon_512x512@2x.png")).convert("RGBA").resize((SIZE, SIZE))


def style_mashup(logo, bg, fg, accent, tmp):
    claude = claude_icon(tmp)
    shape = claude.getchannel("A")
    # The starburst is near-white on a terracotta tile: the blue channel separates them cleanly.
    star = ImageChops.multiply(claude.getchannel("B").point(lambda v: max(0, min(255, int((v - 95) * 255 / 130)))), shape)
    grad = Image.linear_gradient("L").resize((SIZE, SIZE))
    lighter = tuple(min(255, int(c * 1.15 + 30)) for c in bg)
    base = Image.composite(Image.new("RGB", (SIZE, SIZE), bg), Image.new("RGB", (SIZE, SIZE), lighter), grad)
    out = Image.composite(Image.new("RGB", (SIZE, SIZE), accent), base, star).convert("RGBA")
    R, ring, cx, cy = 182, 20, 712, 712          # badge kept inside the tile's corner curve
    d = ImageDraw.Draw(out)
    d.ellipse([cx - R - ring, cy - R - ring, cx + R + ring, cy + R + ring], fill=bg + (255,))
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(251, 251, 251, 255))
    g = fit(glyph_mask(logo), int(R * 1.25), int(R * 1.25))
    out.paste(Image.new("RGBA", g.size, fg + (255,)), (cx - g.width // 2, cy - g.height // 2), g)
    out.putalpha(ImageChops.multiply(out.getchannel("A"), shape))
    return out


def write_icns(img, out_path, tmp):
    iconset = os.path.join(tmp, "out.iconset")
    os.makedirs(iconset, exist_ok=True)
    for s in (16, 32, 128, 256, 512):
        img.resize((s, s), Image.LANCZOS).save(f"{iconset}/icon_{s}x{s}.png")
        img.resize((s * 2, s * 2), Image.LANCZOS).save(f"{iconset}/icon_{s}x{s}@2x.png")
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", out_path], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--logo", required=True)
    ap.add_argument("--out", required=True, help="output .icns path")
    ap.add_argument("--style", choices=["logo", "mashup"], default="logo")
    ap.add_argument("--bg", default="#111114", help="tile colour")
    ap.add_argument("--fg", default=None, help="logo colour (default: white for logo style, near-black badge glyph for mashup)")
    ap.add_argument("--accent", default="#D97757", help="mashup only: starburst colour")
    ap.add_argument("--preview", help="also write a 512px PNG preview here")
    a = ap.parse_args()

    tmp = tempfile.mkdtemp()
    try:
        logo = load_logo(a.logo, tmp)
        bg = hex_rgb(a.bg)
        if a.style == "logo":
            img = style_logo(logo, bg, hex_rgb(a.fg or "#FBFBFB"))
        else:
            img = style_mashup(logo, bg, hex_rgb(a.fg or "#0A0A0C"), hex_rgb(a.accent), tmp)
        write_icns(img, a.out, tmp)
        if a.preview:
            img.resize((512, 512), Image.LANCZOS).save(a.preview)
        print(f"wrote {a.out}" + (f" and {a.preview}" if a.preview else ""))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
