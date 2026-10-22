"""Blind Spot: radar visto de cima com os carros à tua volta e aviso lateral.

Só aparece quando há um carro perto (configurável).
"""

from __future__ import annotations

import math

from .. import theme as T
from ..canvas import alpha
from ..i18n import tr
from ..model import to_local
from .base import Overlay

CAR_W, CAR_L = 2.0, 4.8


class BlindSpotOverlay(Overlay):
    key = "blind_spot"
    defaults = {"range_long_m": 14.0, "range_lat_m": 9.0, "always_show": False, "flip_sides": False}
    default_pos = (885, 560)
    contextual = True

    def has_content(self, snap, ctx):
        return bool(self.cfg["always_show"]) or (snap.session.in_realtime and bool(self.nearby(snap)))

    def size(self, snap, ctx):
        return (150, 230)

    def nearby(self, snap):
        p = snap.player
        rl, rt = float(self.cfg["range_long_m"]), float(self.cfg["range_lat_m"])
        out = []
        for v in snap.vehicles:
            if v.is_player or v.in_garage or v.in_pits:
                continue
            d = (v.pos[0] - p.pos[0], v.pos[1] - p.pos[1], v.pos[2] - p.pos[2])
            if abs(d[0]) > 60 or abs(d[2]) > 60:
                continue
            lx, _, lz = to_local(p.ori, d)
            if self.cfg["flip_sides"]:      # se no teu PC os lados aparecerem trocados
                lx = -lx
            if abs(lz) <= rl + CAR_L / 2 and abs(lx) <= rt:
                f = to_local(p.ori, v.fwd)
                if self.cfg["flip_sides"]:
                    f = (-f[0], f[1], f[2])
                out.append((v, lx, lz, f))
        return out

    def draw(self, c, snap, ctx, w, h):
        cars = self.nearby(snap) if snap is not None and snap.session.in_realtime else []
        if not cars and not (ctx.edit_mode or self.cfg["always_show"]):
            return
        rl, rt = float(self.cfg["range_long_m"]), float(self.cfg["range_lat_m"])
        T.panel(c, w, h)
        cx, cy = w / 2, h / 2
        k = min((w - 34) / (2 * rt), (h - 20) / (2 * rl))
        for m in (-10, -5, 5, 10):
            if abs(m) <= rl:
                c.rect(16, cy + m * k, w - 32, 1, (255, 255, 255, 14))
        c.rect(cx - 0.5, 10, 1, h - 20, (255, 255, 255, 12))
        for x in (5, w - 11):
            c.rect(x, 12, 6, h - 24, (255, 255, 255, 14), radius=3)
        c.mark_static()

        left = right = None
        for v, lx, lz, f in cars:
            sx, sy = cx - lx * k, cy + lz * k
            dx, dy = -f[0], f[2]
            n = math.hypot(dx, dy) or 1
            dx, dy = dx / n, dy / n
            alongside = abs(lz) < CAR_L + 0.4 and abs(lx) < 4.5
            close = alongside and abs(lx) < CAR_W + 0.7
            _, ccol = T.class_info(v.cls)
            col = T.BAD if close else (T.WARN if alongside else alpha(ccol, 220))
            self._car(c, sx, sy, dx, dy, k, col)
            if alongside:
                level = 2 if close else 1
                if lx > 0:
                    left = max(left or 0, level), sy
                else:
                    right = max(right or 0, level), sy
        self._car(c, cx, cy, 0, -1, k, (236, 239, 245, 255), stroke=T.ME)

        for side, info in (("l", left), ("r", right)):
            x = 5 if side == "l" else w - 11
            if info:
                col = T.BAD if info[0] == 2 else T.WARN
                c.rect(x - 2, 12, 10, h - 24, alpha(col, 60 if ctx.blink else 30), radius=4)
                y = max(12.0, min(h - 12 - CAR_L * k, info[1] - CAR_L * k / 2))
                T.neon_glow(c, x, y, 6, CAR_L * k, col, 1.4)
                c.rect(x, y, 6, CAR_L * k, col, radius=3)
        if left and right:
            T.chip(c, cx - 48, h - 26, 96, 16, tr("bs.both"), T.BAD, size=10)

    @staticmethod
    def _car(c, x, y, dx, dy, k, col, stroke=None):
        hl, hw = CAR_L * k / 2, CAR_W * k / 2
        px, py = -dy, dx
        pts = [(x + dx * hl + px * hw, y + dy * hl + py * hw), (x + dx * hl - px * hw, y + dy * hl - py * hw),
               (x - dx * hl - px * hw, y - dy * hl - py * hw), (x - dx * hl + px * hw, y - dy * hl + py * hw)]
        c.polygon(pts, col, stroke=stroke or (0, 0, 0, 140), stroke_w=2 if stroke else 1.5)
        # para-brisas (mostra para onde aponta)
        wx, wy = x + dx * hl * 0.35, y + dy * hl * 0.35
        c.line(wx + px * hw * 0.7, wy + py * hw * 0.7, wx - px * hw * 0.7, wy - py * hw * 0.7, (0, 0, 0, 150), 2)
