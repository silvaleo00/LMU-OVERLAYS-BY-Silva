"""Fuel Calculator: combustível ou energia virtual (Hypercar e GT3 usam VE no LMU)."""

from __future__ import annotations

from .. import theme as T
from ..canvas import alpha
from ..i18n import tr
from .base import Overlay


class FuelOverlay(Overlay):
    key = "fuel"
    defaults = {"margin_laps": 0.5, "avg_laps": 5}
    default_pos = (1560, 560)

    smart_capable = True
    default_mode = "auto"

    def auto_visible(self, snap, ctx):
        """Depois de cada volta, nas boxes, em FCY, ou quando o depósito não chega."""
        f, me = ctx.fuel, snap.me
        low = f.per_lap > 0 and f.race_laps_left > f.laps_in_tank and f.laps_in_tank < 2.5
        return (ctx.since("lap") < 12 or me.in_pits or me.pit_state in (1, 2, 3, 4) or low
                or snap.session.phase == 6)

    def size(self, snap, ctx):
        return (320, 226)

    def render(self, c, snap, ctx, w, h):
        f = ctx.fuel
        u = f.unit
        unit = " %" if u == "%" else " L"
        title = tr("fuel.ve_title") if f.uses_ve else tr("fuel.title")
        right = tr("fuel.fuel", x=f"{f.fuel_l:.1f}") if f.uses_ve else \
            (tr("fuel.tank", x=f"{f.capacity:.0f}") if f.capacity else "")
        y = T.panel(c, w, h, title, right, part="bg")
        c.mark_static()
        T.panel(c, w, h, title, right, part="right")

        # dois números grandes
        short = f.per_lap > 0 and f.race_laps_left > 0 and f.laps_in_tank < f.race_laps_left
        laps_col = T.TEXT if not short else (T.WARN if f.laps_in_tank > 2 else T.BAD)
        c.text(14, y, 140, 14, tr("fuel.remaining"), 10, T.FAINT, "l", 700, spacing=1)
        c.text(14, y + 13, 150, 36, f"{f.remaining:.1f}{unit}", 32, T.TEXT, "l", 800)
        c.text(w - 154, y, 140, 14, tr("fuel.laps"), 10, T.FAINT, "r", 700, spacing=1)
        c.text(w - 164, y + 13, 150, 36, f"{f.laps_in_tank:.1f}" if f.per_lap > 0 else "—", 32, laps_col, "r", 800)
        y += 54

        # barra do depósito com a marca do necessário até ao fim
        bx, bw = 14, w - 28
        frac = f.remaining / f.capacity if f.capacity > 0 else 0
        bcol = T.GOOD if frac > 0.3 else T.WARN if frac > 0.12 else T.BAD
        c.rect(bx, y, bw, 8, (255, 255, 255, 20), radius=4)
        if frac > 0:
            T.neon_glow(c, bx, y, bw * max(0.0, min(1.0, frac)), 8, bcol, 0.9)
            c.rect(bx, y, bw * max(0.0, min(1.0, frac)), 8, alpha(bcol, 150), radius=4, fill2=bcol, horizontal=True)
        if f.needed > 0 and f.capacity > 0 and f.needed < f.capacity:
            nx = bx + bw * f.needed / f.capacity
            c.rect(nx - 1, y - 4, 2, 16, T.TEXT, radius=1)
            c.text(nx - 40, y + 9, 80, 12, tr("fuel.need_line"), 9, T.DIM, "c", 700, spacing=0.6)
        y += 22

        if f.per_lap <= 0:
            c.text(14, y + 6, w - 28, 22, tr("fuel.measuring"), 14, T.DIM, "l", 600)
            c.text(14, y + 28, w - 28, 20, tr("fuel.measuring_hint"), 12, T.FAINT, "l", 500)
            return

        note = tr("fuel.estimate") if f.estimating else (tr("fuel.last", x=f"{f.last_lap:.2f}") if f.last_lap > 0 else "")
        rows = [
            (tr("fuel.per_lap"), f"{f.per_lap:.2f}{unit}", note, T.TEXT),
            (tr("fuel.laps_to_end"), f"{f.race_laps_left:.1f}" if f.race_laps_left > 0 else "—", "", T.TEXT),
            (tr("fuel.required"), f"{f.needed:.1f}{unit}" if f.needed > 0 else "—",
             tr("fuel.margin", x=f"{self.cfg['margin_laps']:g}") if f.needed > 0 else "", T.TEXT),
        ]
        if f.race_laps_left > 0:
            if f.to_add > 0:
                stops = tr("fuel.stops" if f.stops == 1 else "fuel.stops_pl", n=f.stops)
                rows.append((tr("fuel.add"), f"+{f.to_add:.1f}{unit}", stops, T.WARN))
                rows.append((tr("fuel.target"), f"{f.target_per_lap:.2f}{unit}",
                             tr("fuel.save", x=f"{f.per_lap - f.target_per_lap:.2f}") if f.target_per_lap > 0 else "",
                             T.DIM))
            else:
                rows.append((tr("fuel.finishes"), tr("fuel.yes"), tr("fuel.spare", x=f"{f.remaining - f.needed:.1f}"),
                             T.GOOD))
        for i, (label, val, extra, col) in enumerate(rows):
            if i % 2 == 0:
                c.rect(6, y, w - 12, 21, T.ROW_ALT, radius=3)
            c.text(14, y, 120, 21, label, 13, T.DIM, "l", 500)
            c.text(w - 14 - 86, y, 86, 21, val, 14, col, "r", 700)
            if extra:
                c.text(w - 14 - 86 - 100, y, 96, 21, extra, 11, T.FAINT, "r", 500)
            y += 21
