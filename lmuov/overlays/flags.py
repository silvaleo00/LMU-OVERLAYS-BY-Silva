"""Flags: aviso com texto, só quando há uma bandeira que te diz respeito."""

from __future__ import annotations

from .. import theme as T
from ..canvas import alpha, scale_rgb
from ..flagcalc import FLAG_DEFAULTS, active_flags
from ..i18n import tr
from .base import Overlay


def flag_tile(c, x, y, w, h, kind, color, lit=True):
    """Bandeira desenhada (cor sólida, xadrez, preto/branco)."""
    col = color if lit else scale_rgb(color, 0.6)
    if kind == "chequered":
        c.rect(x, y, w, h, (240, 242, 246, 255), radius=4)
        n = 4
        sq_w, sq_h = w / n, h / 3
        for r in range(3):
            for k in range(n):
                if (r + k) % 2 == 0:
                    c.rect(x + k * sq_w, y + r * sq_h, sq_w, sq_h, (18, 18, 20, 255))
    elif kind == "penalty":
        c.rect(x, y, w, h, (240, 242, 246, 255), radius=4)
        c.polygon([(x, y), (x + w, y), (x, y + h)], (18, 18, 20, 255))
    else:
        c.rect(x, y, w, h, col, radius=4, fill2=scale_rgb(col, 0.82))
    c.rect(x, y, w, h, None, radius=4, stroke=(255, 255, 255, 60), stroke_w=1)


class FlagsOverlay(Overlay):
    key = "flags"
    defaults = dict(FLAG_DEFAULTS)
    default_pos = (720, 116)
    contextual = True

    def has_content(self, snap, ctx):
        return bool(active_flags(snap, ctx, self.cfg))

    def size(self, snap, ctx):
        return (480, 68)

    def draw(self, c, snap, ctx, w, h):
        flags = active_flags(snap, ctx, self.cfg)
        if not flags:
            if ctx.edit_mode:
                T.placeholder(c, w, h, tr("flag.placeholder"))
            return
        f = flags[0]
        lit = not (f.blink and not ctx.blink)
        T.neon_frame(c, 0, 0, w, h, f.color, 1.6 if lit else 0.7)
        T.panel(c, w, h, accent=f.color)
        c.rect(1, 1, w - 2, 3, f.color if lit else scale_rgb(f.color, 0.6), radius=1.5)
        flag_tile(c, 10, 10, 66, h - 20, f.kind, f.color, lit)
        c.mark_static()
        title_col = f.color if f.kind not in ("chequered", "penalty", "formation") else T.TEXT
        if f.kind in ("fcy", "yellow"):
            title_col = T.WARN          # no estilo claro (Retro) o amarelo puro não se lê
        chip_w = 0
        if len(flags) > 1:
            g = flags[1]
            chip_w = 82
            T.chip(c, w - chip_w - 12, h / 2 - 11, chip_w, 22, tr(f"chip.{g.kind}"), g.color
                   if g.kind != "penalty" else (230, 232, 236, 255), size=11)
        c.text(90, 8, w - 104 - chip_w, 30, f.text, 24, title_col, "l", 800, spacing=0.6)
        c.text(90, 37, w - 104 - chip_w, 22, f.sub, 14, T.DIM, "l", 600)
