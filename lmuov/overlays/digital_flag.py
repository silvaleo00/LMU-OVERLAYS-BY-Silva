"""Digital Flag: painel de LEDs como os painéis digitais à beira da pista."""

from __future__ import annotations

from .. import theme as T
from ..canvas import alpha
from ..flagcalc import FLAG_DEFAULTS, active_flags
from ..i18n import tr
from .base import Overlay

COLS, ROWS = 20, 11
OFF = (34, 36, 41, 255)
WHITE = (240, 242, 246, 255)
GLYPHS = {  # 5x7
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
}


def _text_mask(word: str) -> set[tuple[int, int]]:
    w = len(word) * 5 + (len(word) - 1) * 1
    x0, y0 = (COLS - w) // 2, (ROWS - 7) // 2
    cells = set()
    for i, ch in enumerate(word):
        for r, line in enumerate(GLYPHS[ch]):
            for k, bit in enumerate(line):
                if bit == "1":
                    cells.add((x0 + i * 6 + k, y0 + r))
    return cells


FCY_MASK = _text_mask("FCY")


def led_color(kind: str, color, col: int, row: int):
    if kind == "chequered":
        return WHITE if (col // 3 + row // 3) % 2 == 0 else None
    if kind == "penalty":
        return WHITE if col / COLS + row / ROWS < 1.0 else None
    if kind == "fcy":
        return None if (col, row) in FCY_MASK else color
    if kind == "formation":
        return WHITE
    return color


class DigitalFlagOverlay(Overlay):
    key = "digital_flag"
    defaults = {**FLAG_DEFAULTS, "show_when_clear": False}
    default_pos = (1210, 16)
    contextual = True

    def has_content(self, snap, ctx):
        return bool(self.cfg["show_when_clear"]) or bool(active_flags(snap, ctx, self.cfg))

    def size(self, snap, ctx):
        return (220, 136)

    def draw(self, c, snap, ctx, w, h):
        flags = active_flags(snap, ctx, self.cfg)
        if not flags and not self.cfg["show_when_clear"]:
            if ctx.edit_mode:
                T.placeholder(c, w, h, tr("dflag.placeholder"))
            return
        f = flags[0] if flags else None
        lit = f is not None and not (f.blink and not ctx.blink)
        # caixa do painel
        if f is not None:
            T.neon_frame(c, 0, 0, w, h, f.color if f.kind not in ('chequered', 'penalty') else (230, 232, 236, 255),
                         1.4 if lit else 0.6)
        c.rect(0, 0, w, h, (20, 21, 24, 245), radius=10, stroke=(70, 72, 78, 255), stroke_w=1.5,
               fill2=(10, 11, 13, 245))
        x0, y0 = 12, 12
        pw, ph = (w - 24) / COLS, (h - 24) / ROWS
        r = min(pw, ph) * 0.36
        for row in range(ROWS):
            for col in range(COLS):
                cx, cy = x0 + (col + 0.5) * pw, y0 + (row + 0.5) * ph
                ledc = led_color(f.kind, f.color, col, row) if (f and lit) else None
                if ledc is None:
                    c.ellipse(cx, cy, r, r, OFF)
                else:
                    c.ellipse(cx, cy, r * 1.55, r * 1.55, alpha(ledc, 55))
                    c.ellipse(cx, cy, r, r, ledc)
