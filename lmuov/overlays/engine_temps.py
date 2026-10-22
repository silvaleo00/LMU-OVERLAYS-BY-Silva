"""Engine Temps: temperatura da água e do óleo (e do motor elétrico do híbrido), com cores de aviso."""

from __future__ import annotations

from .. import theme as T
from ..canvas import alpha
from ..i18n import tr
from .base import Overlay


class EngineTempsOverlay(Overlay):
    key = "engine_temps"
    defaults = {"water_warn": 100, "water_hot": 108, "oil_warn": 120, "oil_hot": 130,
                "hybrid_warn": 80, "hybrid_hot": 90, "fahrenheit": False}
    default_pos = (1182, 880)
    smart_capable = True
    default_mode = "auto"

    def rows(self, p):
        out = [("et.water", p.water_temp, float(self.cfg["water_warn"]), float(self.cfg["water_hot"]), 40, 125),
               ("et.oil", p.oil_temp, float(self.cfg["oil_warn"]), float(self.cfg["oil_hot"]), 40, 145)]
        if p.boost_temp >= 0:
            out.append(("et.hybrid", p.boost_temp, float(self.cfg["hybrid_warn"]), float(self.cfg["hybrid_hot"]), 20, 110))
        return out

    def auto_visible(self, snap, ctx):
        """Quando alguma temperatura chega perto do aviso, no início, ao sair das boxes e depois de cada volta."""
        warm = any(v >= warn - 3 for _k, v, warn, _hot, _lo, _hi in self.rows(snap.player) if v > 0)
        return warm or ctx.since("start") < 20 or ctx.since("pit_exit") < 15 or ctx.since("lap") < 6

    def size(self, snap, ctx):
        n = 3 if snap is not None and snap.player.boost_temp >= 0 else 2
        return (270, T.HEADER_H + 10 + n * 30)

    def render(self, c, snap, ctx, w, h):
        p = snap.player
        rows = self.rows(p)
        y = T.panel(c, w, h, self.title)
        for i, (key, *_r) in enumerate(rows):
            yy = y + i * 30
            c.text(14, yy, 70, 26, tr(key), 11, T.DIM, "l", 700, spacing=1)
            c.rect(84, yy + 10, w - 170, 8, (255, 255, 255, 18), radius=4)
        c.mark_static()
        f = bool(self.cfg.get("fahrenheit"))
        for i, (key, v, warn, hot, lo, hi) in enumerate(rows):
            yy = y + i * 30
            col = T.BAD if v >= hot else (T.WARN if v >= warn else T.GOOD)
            frac = max(0.0, min(1.0, (v - lo) / (hi - lo))) if v > 0 else 0.0
            bw = w - 170
            if frac > 0:
                if v >= warn:
                    T.neon_glow(c, 84, yy + 10, bw * frac, 8, col, 0.9 if (v < hot or ctx.blink) else 0.4)
                c.rect(84, yy + 10, bw * frac, 8, col, radius=4)
            c.rect(84 + bw * (warn - lo) / (hi - lo) - 0.5, yy + 6, 1.5, 16, alpha(T.WARN, 160))
            shown = v * 9 / 5 + 32 if f else v
            txt = f"{shown:.0f}°{'F' if f else 'C'}" if v > 0 else "—"
            c.text(w - 82, yy, 68, 26, txt, 18, col if v >= warn else T.TEXT, "r", 800)
