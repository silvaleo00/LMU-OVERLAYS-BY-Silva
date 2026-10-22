"""Delta Bar: delta para a melhor volta, estilo TV.

Modo automático: em treino e qualificação está sempre visível; em corrida aparece uns
segundos depois de cada setor e de cada volta.
"""

from __future__ import annotations

from .. import theme as T
from ..canvas import alpha
from ..i18n import tr
from .base import Overlay


class DeltaOverlay(Overlay):
    key = "delta"
    # style: "bar" = só a barra (verde = mais rápido, vermelho = mais lento); "full" = com tempos e número
    defaults = {"bar_range": 1.0, "race_show_s": 8.0, "style": "bar"}
    default_pos = (740, 16)
    smart_capable = True
    default_mode = "auto"

    def size(self, snap, ctx):
        return (440, 22) if self.cfg.get("style", "bar") == "bar" else (440, 84)

    def auto_visible(self, snap, ctx):
        if snap.session.kind != "race":
            return True
        t = float(self.cfg["race_show_s"])
        return ctx.since("sector") < t or ctx.since("lap") < t

    def _bar_only(self, c, d, w, h):
        """Só a barra: cresce do centro para a esquerda (verde) ou para a direita (vermelho)."""
        T.body(c, 0, 0, w, h)
        c.rect(3, 3, w - 6, h - 6, (255, 255, 255, 14), radius=3)
        c.mark_static()
        mid = w / 2
        if d.invalid:
            c.rect(3, 3, w - 6, h - 6, alpha(T.BAD, 70), radius=3)
        elif d.has_ref:
            rng = max(0.1, float(self.cfg["bar_range"]))
            frac = max(-1.0, min(1.0, d.delta / rng))
            col = T.GOOD if frac < 0 else T.BAD
            x0, x1 = sorted((mid, mid + frac * (w / 2 - 3)))
            if x1 - x0 > 0.5:
                T.neon_glow(c, x0, 3, x1 - x0, h - 6, col)
                c.rect(x0, 3, x1 - x0, h - 6, col, radius=2)
        c.rect(mid - 1.5, 0, 3, h, T.TEXT)

    def render(self, c, snap, ctx, w, h):
        d = ctx.delta
        if self.cfg.get("style", "bar") == "bar":
            self._bar_only(c, d, w, h)
            return
        right = (f"{tr('delta.pred')}  {T.laptime(d.predicted)}" if d.has_ref
                 else tr("delta.no_ref"))
        T.neon_frame(c, 0, 0, w, h, T.ACCENT, 0.8)
        T.tv_header(c, w, self.title, right, part="bg")
        top = T.HEADER_H
        if T.SKIN.get("header") in ("tv", "carbon"):
            T.body(c, 0, top, w, h - top)
        else:
            T.body(c, 0, 0, w, h)
            T.tv_header(c, w, self.title, right, part="bg")

        side = 112
        c.text(12, top + 4, side, 14, tr("delta.best"), 10, T.FAINT, "l", 800, spacing=1)
        c.text(12, top + 17, side, 22, T.laptime(d.ref_time if d.has_ref else d.best_session), 17, T.TEXT, "l", 800)
        c.text(w - 12 - side, top + 4, side, 14, tr("delta.last"), 10, T.FAINT, "r", 800, spacing=1)
        c.text(w - 12 - side, top + 17, side, 22, T.laptime(d.last), 17, T.DIM, "r", 800)
        bx, bw, by, bh = 0, w, h - 9, 9
        c.rect(bx, by, bw, bh, (255, 255, 255, 16))
        c.mark_static()                      # o que vem a seguir muda a cada frame
        T.tv_header(c, w, self.title, right, part="right")

        cx0, cw = side + 24, w - 2 * side - 48
        if d.invalid:
            T.chip(c, cx0, top + 6, cw, 32, tr("delta.invalid"), T.BAD, size=14, weight=800)
        elif d.has_ref:
            v = d.delta
            col = T.GOOD if v < -0.005 else T.BAD if v > 0.005 else T.TEXT
            T.skew_rect(c, cx0, top + 5, cw, 34, alpha(col, 40), skew=8)
            c.text(cx0, top + 3, cw, 38, f"{v:+.3f}" if abs(v) < 10 else f"{v:+.1f}", 34, col, "c", 800)
        else:
            c.text(cx0, top + 3, cw, 38, "±-.---", 34, T.FAINT, "c", 800)

        # barra: centro = igual à referência; verde à esquerda (mais rápido), vermelho à direita
        mid = bx + bw / 2
        if d.has_ref and not d.invalid:
            rng = max(0.1, float(self.cfg["bar_range"]))
            frac = max(-1.0, min(1.0, d.delta / rng))
            col = T.GOOD if frac < 0 else T.BAD
            x0, x1 = sorted((mid, mid + frac * bw / 2))
            if x1 - x0 > 0.5:
                T.neon_glow(c, x0, by, x1 - x0, bh, col)
                c.rect(x0, by, x1 - x0, bh, col)
                c.rect(x0, by + bh / 2 - 1, x1 - x0, 2, T.lighten(col, 0.6))
            if abs(d.trend) > 0.02:   # seta: a ganhar (verde) ou a perder (vermelho) agora
                tx = mid + frac * bw / 2
                tcol = T.GOOD if d.trend < 0 else T.BAD
                s = -1 if d.trend < 0 else 1
                c.polygon([(tx + 10 * s, by + bh / 2), (tx + 3 * s, by - 4), (tx + 3 * s, by + bh)], tcol)
        c.rect(mid - 1.5, by - 3, 3, bh + 3, T.TEXT)
