"""Wind & Weather (extra): vento relativo ao carro, temperaturas e chuva."""

from __future__ import annotations

import math

from .. import theme as T
from ..i18n import tr
from .base import Overlay


def wind_relative(wind_world, ori) -> tuple[float, float]:
    """Devolve (para_a_frente, para_a_esquerda) do movimento do ar no referencial do carro, em m/s.

    ori são as linhas da matriz que converte local->mundo, logo local = Mᵀ·mundo.
    Eixos locais do rF2/LMU: +x esquerda, +y cima, +z trás.
    """
    wx, wy, wz = wind_world
    lx = ori[0][0] * wx + ori[1][0] * wy + ori[2][0] * wz
    lz = ori[0][2] * wx + ori[1][2] * wy + ori[2][2] * wz
    return -lz, lx


class WindOverlay(Overlay):
    key = "wind"
    defaults = {"flip_lateral": False, "flip_longitudinal": False}
    default_pos = (1340, 560)
    default_enabled = False
    R = 62

    smart_capable = True
    default_mode = "auto"

    def auto_visible(self, snap, ctx):
        """No início, ao sair das boxes e quando chove."""
        s = snap.session
        return ctx.since("start") < 20 or ctx.since("pit_exit") < 20 or s.rain > 0.05 or s.wetness > 0.05

    def size(self, snap, ctx):
        return (220, T.HEADER_H + 5 + 2 * self.R + 16 + 94)

    def render(self, c, snap, ctx, w, h):
        s = snap.session
        y = T.panel(c, w, h, self.title)
        c.mark_static()
        cx, cy, R = w / 2, y + 8 + self.R, self.R
        c.ellipse(cx, cy, R, R, (255, 255, 255, 8), stroke=T.TRACK, stroke_w=1.5)
        for k in range(12):
            a = k * math.pi / 6
            r0 = R - (8 if k % 3 == 0 else 4)
            c.line(cx + r0 * math.sin(a), cy - r0 * math.cos(a), cx + R * math.sin(a), cy - R * math.cos(a),
                   T.FAINT, 1.5 if k % 3 == 0 else 1)
        body = (205, 212, 224, 230)
        c.rect(cx - 9, cy - 19, 18, 38, body, radius=7)
        c.rect(cx - 6, cy - 9, 12, 9, (40, 46, 56, 255), radius=2)
        c.polygon([(cx, cy - 27), (cx - 5, cy - 20), (cx + 5, cy - 20)], body)

        mph = ctx.cfg.get("speed_unit") == "mph"
        mul, unit = (2.23694, "mph") if mph else (3.6, "km/h")
        ty = cy + R + 10
        if not s.wind_valid:
            c.text(0, ty, w, 28, "--", 24, T.FAINT, "c", 800)
            c.text(6, ty + 28, w - 12, 18, tr("wind.no_data"), 12, T.FAINT, "c", 500)
        else:
            fwd, left = wind_relative(s.wind, snap.player.ori)
            if self.cfg["flip_lateral"]:
                left = -left
            if self.cfg["flip_longitudinal"]:
                fwd = -fwd
            spd = math.hypot(fwd, left)
            if spd > 0.05:
                sx, sy = -left / spd, -fwd / spd
                fx, fy = -sx, -sy
                x0, y0 = cx + fx * (R - 4), cy + fy * (R - 4)
                x1, y1 = cx + fx * 30, cy + fy * 30
                c.line(x0, y0, x1, y1, T.ACCENT, 4)
                px, py = -sy, sx
                c.polygon([(x1 + sx * 12, y1 + sy * 12), (x1 + px * 8, y1 + py * 8), (x1 - px * 8, y1 - py * 8)],
                          T.ACCENT)
            c.text(0, ty, w, 28, f"{spd * mul:.0f} {unit}", 24, T.TEXT, "c", 800)
            head, cross = -fwd * mul, left * mul
            parts = []
            if abs(head) >= 1:
                parts.append(tr("wind.ahead" if head > 0 else "wind.behind", x=f"{abs(head):.0f}"))
            if abs(cross) >= 1:
                parts.append(tr("wind.from_right" if cross > 0 else "wind.from_left", x=f"{abs(cross):.0f}"))
            c.text(6, ty + 28, w - 12, 18, " · ".join(parts) or tr("wind.calm"), 12, T.DIM, "c", 600)
        my = ty + 52
        c.line(10, my, w - 10, my, T.TRACK, 1)
        c.text(12, my + 4, w / 2 - 12, 18, tr("wind.air", x=f"{s.air_temp:.0f}"), 13, T.DIM, "l", 600)
        c.text(w / 2, my + 4, w / 2 - 12, 18, tr("wind.track", x=f"{s.track_temp:.0f}"), 13, T.DIM, "r", 600)
        c.text(12, my + 22, w / 2 - 12, 18, tr("wind.rain", x=f"{s.rain * 100:.0f}"), 13,
               T.INFO if s.rain > 0.02 else T.DIM, "l", 600)
        c.text(w / 2, my + 22, w / 2 - 12, 18, tr("wind.wet", x=f"{s.wetness * 100:.0f}"), 13,
               T.INFO if s.wetness > 0.02 else T.DIM, "r", 600)
