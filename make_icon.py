"""
Generate a Windows 95-style journal .ico file using Pillow.
Run once: py make_icon.py
"""

from PIL import Image, ImageDraw
from pathlib import Path

OUT = Path(__file__).parent / "messagelog.ico"


def draw_journal(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size

    # ── Scale helpers ──────────────────────────────────────────────
    def p(v): return max(1, round(v * s / 32))   # scale from 32-px base

    # ── Cover ─────────────────────────────────────────────────────
    cover_l = p(5)
    cover_r = s - p(3)
    cover_t = p(2)
    cover_b = s - p(2)

    # Main cover body (tan/parchment)
    d.rectangle([cover_l, cover_t, cover_r, cover_b], fill="#c8a86b")
    # Right-edge highlight
    d.rectangle([cover_r - p(1), cover_t, cover_r, cover_b], fill="#e8c88b")
    # Bottom shadow
    d.rectangle([cover_l, cover_b - p(1), cover_r, cover_b], fill="#8b6914")
    # Outer border
    d.rectangle([cover_l, cover_t, cover_r, cover_b], outline="#3d2000", width=max(1, p(1)))

    # ── Spine (left binding strip) ────────────────────────────────
    spine_r = cover_l + p(4)
    d.rectangle([cover_l, cover_t, spine_r, cover_b], fill="#8b4513")
    d.rectangle([cover_l, cover_t, spine_r, cover_b], outline="#3d2000", width=max(1, p(1)))

    # Spine ridges
    num_ridges = 5
    for i in range(1, num_ridges + 1):
        ry = cover_t + i * (cover_b - cover_t) // (num_ridges + 1)
        d.rectangle([cover_l + p(1), ry - max(1, p(0.5)),
                     spine_r - p(1), ry + max(1, p(0.5))],
                    fill="#5c2800")

    # ── Page area (inner cream rectangle) ────────────────────────
    page_l = spine_r + p(2)
    page_r = cover_r - p(2)
    page_t = cover_t + p(2)
    page_b = cover_b - p(2)
    d.rectangle([page_l, page_t, page_r, page_b], fill="#fff8dc")
    d.rectangle([page_l, page_t, page_r, page_b], outline="#c8a86b", width=1)

    # ── Ruled lines ───────────────────────────────────────────────
    line_margin_l = page_l + p(2)
    line_margin_r = page_r - p(2)
    num_lines = 5
    line_area_t = page_t + p(3)
    line_area_b = page_b - p(2)
    for i in range(num_lines):
        ly = line_area_t + i * (line_area_b - line_area_t) // (num_lines)
        d.line([(line_margin_l, ly), (line_margin_r, ly)], fill="#a0c0e0", width=1)

    # ── Red margin line ───────────────────────────────────────────
    margin_x = page_l + p(4)
    d.line([(margin_x, page_t + p(1)), (margin_x, page_b - p(1))],
           fill="#e05050", width=max(1, p(0.5)))

    # ── Pencil ────────────────────────────────────────────────────
    px1 = cover_r - p(3)
    px2 = cover_r - p(1)
    py1 = cover_t + p(4)
    py2 = cover_b - p(6)
    d.rectangle([px1, py1, px2, py2], fill="#f5e642")
    d.rectangle([px1, py1, px2, py2], outline="#b8a000", width=1)
    # Eraser
    d.rectangle([px1, py1, px2, py1 + p(2)], fill="#f4a0a0")
    # Tip
    d.polygon([(px1, py2), (px2, py2),
               ((px1 + px2) // 2, py2 + p(3))], fill="#d4a070")

    return img


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [draw_journal(sz) for sz in sizes]
    frames[0].save(
        OUT,
        format="ICO",
        sizes=[(sz, sz) for sz in sizes],
        append_images=frames[1:],
    )
    print(f"Icon saved to {OUT}")


if __name__ == "__main__":
    main()
