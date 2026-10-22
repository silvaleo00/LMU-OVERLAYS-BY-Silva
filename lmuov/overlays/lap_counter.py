"""Lap Counter: volta atual, total (ou estimativa das voltas que faltam numa corrida por tempo)."""

from __future__ import annotations

from .. import theme as T
from ..i18n import tr
from .base import Overlay


class LapCounterOverlay(Overlay):
    key = "lap_counter"
    defaults = {}
    default_pos = (1360, 168)

    def size(self, snap, ctx):
        return (230, 78)

    def render(self, c, snap, ctx, w, h):
        s, me = snap.session, snap.me
        lap = me.total_laps + 1
        y = T.panel(c, w, h, tr("lc.lap"), "", part="bg")
        c.mark_static()
        if s.max_laps:
            lap = min(lap, s.max_laps)
            right = tr("lc.of", m=s.max_laps)
            left_laps = max(0, s.max_laps - me.total_laps)
        else:
            right = tr("left", t=T.clock(s.time_left)) if s.time_left is not None else ""
            left_laps = ctx.fuel.race_laps_left if s.kind == "race" and ctx.fuel.race_laps_left > 0 else None
        T.panel(c, w, h, tr("lc.lap"), right, part="right")
        c.text(14, y - 2, 110, 46, str(lap), 42, T.TEXT, "l", 800)
        if s.max_laps:
            c.text(14 + c.measure(str(lap), 42, 800) + 6, y + 14, 80, 26, f"/ {s.max_laps}", 20, T.DIM, "l", 800)
        if left_laps is not None:
            c.text(w - 120, y + 2, 106, 20, tr("lc.left_label"), 10, T.FAINT, "r", 700, spacing=1)
            val = f"{left_laps:.0f}" if s.max_laps else f"~{left_laps:.1f}"
            c.text(w - 120, y + 16, 106, 28, val, 24, T.ACCENT, "r", 800)
