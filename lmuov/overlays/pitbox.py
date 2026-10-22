"""Pitbox Helper: ajuda na entrada das boxes, a parar na box e a sair.

Aparece quando pedes boxes ou estás no pit lane.
"""

from __future__ import annotations

from .. import theme as T
from ..canvas import alpha
from ..i18n import tr
from .base import Overlay


def speed_txt(ms: float, ctx) -> str:
    if ctx.cfg.get("speed_unit") == "mph":
        return f"{ms * 2.23694:.0f} mph"
    return f"{ms * 3.6:.0f} km/h"


class PitboxOverlay(Overlay):
    key = "pitbox"
    defaults = {"approach_m": 150, "decel": 9.0}
    default_pos = (760, 300)
    contextual = True

    def has_content(self, snap, ctx):
        return self.state(snap) is not None

    def size(self, snap, ctx):
        return (400, 168)

    @staticmethod
    def state(snap) -> str | None:
        if snap is None or not snap.session.in_realtime or snap.me.in_garage:
            return None
        me = snap.me
        if me.in_pits:
            return {3: "stopped", 4: "exit"}.get(me.pit_state, "lane")
        if me.pit_state == 1:
            return "request"
        return None

    @staticmethod
    def box_distance(snap) -> float | None:
        me, L = snap.me, snap.session.track_length
        if me.pit_lap_dist <= 0 or L <= 0:
            return None
        d = me.pit_lap_dist - snap.my_lap_dist()
        if d > L / 2:
            d -= L
        elif d <= -L / 2:
            d += L
        return d

    def draw(self, c, snap, ctx, w, h):
        st = self.state(snap)
        if st is None:
            if ctx.edit_mode:
                T.placeholder(c, w, h, tr("pit.placeholder"))
            return
        me, p, f = snap.me, snap.player, ctx.fuel
        chip_txt, chip_col = {"request": (tr("pit.request"), T.WARN), "lane": (tr("pit.lane"), T.INFO),
                              "stopped": (tr("pit.stopped"), T.GOOD), "exit": (tr("pit.exit"), T.ACCENT)}[st]
        y = T.panel(c, w, h, self.title)
        T.chip(c, w - 166, 5, 154, 18, chip_txt, chip_col, size=11, weight=800)
        c.mark_static()
        d = self.box_distance(snap)
        add = f"+{f.to_add:.1f}{' %' if f.unit == '%' else ' L'}" if f.to_add > 0 else "—"

        if st == "request":
            c.text(14, y, w - 28, 40, tr("pit.request"), 30, T.WARN, "l", 800, spacing=0.8)
            if d is not None:
                dd = d if d > 0 else d + snap.session.track_length
                dist = f"{dd / 1000:.2f} km" if dd >= 1000 else f"{dd:.0f} m"
                c.text(14, y + 38, w - 28, 22, tr("pit.box_ahead", d=dist), 14, T.DIM, "l", 600)
            self._row(c, w, y + 66, tr("pit.fuel_add"), add, T.WARN if f.to_add > 0 else T.TEXT)
            self._limiter(c, w, h, p, ctx, need_on=False)
            return

        if st == "stopped":
            secs = max(0.0, ctx.now - ctx.pit_stop_since) if ctx.pit_stop_since else 0.0
            c.text(14, y, 160, 14, tr("pit.stop_time"), 10, T.FAINT, "l", 700, spacing=1)
            c.text(14, y + 12, 200, 44, f"{secs:4.1f} s", 40, T.TEXT, "l", 800)
            self._row(c, w, y + 66, tr("pit.fuel_add"), add, T.WARN if f.to_add > 0 else T.TEXT)
            self._limiter(c, w, h, p, ctx, need_on=True)
            return

        # no pit lane (a entrar ou a sair)
        c.text(w - 164, y, 150, 14, tr("pit.speed").upper(), 10, T.FAINT, "r", 700, spacing=1)
        c.text(w - 214, y + 12, 200, 40, speed_txt(p.speed, ctx), 30, T.TEXT, "r", 800)
        if st == "exit":
            c.text(14, y + 4, 220, 40, tr("pit.exit"), 28, T.ACCENT, "l", 800, spacing=0.6)
            c.text(14, y + 58, w - 28, 20, tr("pit.release"), 13, T.DIM, "l", 600)
            self._limiter(c, w, h, p, ctx, need_on=True)
            return

        c.text(14, y, 160, 14, tr("pit.to_box"), 10, T.FAINT, "l", 700, spacing=1)
        if d is None:
            c.text(14, y + 12, 200, 40, "—", 34, T.FAINT, "l", 800)
        else:
            stop = abs(d) <= 3.0
            brake_d = p.speed ** 2 / (2 * float(self.cfg["decel"])) + 4
            col = T.GOOD if stop else (T.WARN if 0 < d <= brake_d else T.ACCENT)
            txt = tr("pit.stop") if stop else (f"{d:.0f} m" if d > 0 else tr("pit.passed"))
            c.text(14, y + 12, 220, 40, txt, 34, col, "l", 800)
            # barra de aproximação
            rng = float(self.cfg["approach_m"])
            bx, bw, by = 14, w - 28, y + 62
            c.rect(bx, by, bw, 12, (255, 255, 255, 18), radius=6)
            c.rect(bx + bw - 8, by - 5, 6, 22, T.GOOD, radius=2)                  # a box
            frac = 1 - max(0.0, min(rng, d)) / rng if d > 0 else 1.0
            T.neon_glow(c, bx, by, max(6.0, (bw - 8) * frac), 12, col)
            c.rect(bx, by, max(6.0, (bw - 8) * frac), 12, alpha(col, 120), radius=6, fill2=col, horizontal=True)
            if 0 < d <= brake_d and not stop and ctx.blink:
                T.chip(c, w / 2 - 50, by + 16, 100, 18, tr("pit.brake"), T.WARN, size=11)
        self._limiter(c, w, h, p, ctx, need_on=True)

    @staticmethod
    def _row(c, w, y, label, val, col):
        c.rect(6, y, w - 12, 24, T.ROW_ALT, radius=3)
        c.text(14, y, 200, 24, label, 13, T.DIM, "l", 500)
        c.text(w - 160, y, 146, 24, val, 15, col, "r", 700)

    @staticmethod
    def _limiter(c, w, h, p, ctx, need_on):
        y = h - 30
        if p.limiter_on:
            T.chip(c, 14, y, 130, 20, tr("pit.limiter_on"), T.GOOD, size=11)
        else:
            bg = T.BAD if (ctx.blink or not need_on) else alpha(T.BAD, 140)
            T.chip(c, 14, y, 130, 20, tr("pit.limiter_off"), bg, size=11)
            if need_on:
                c.text(152, y, w - 166, 20, tr("pit.turn_on"), 13, T.BAD, "l", 700)
