"""Track Limits: aviso vermelho quando apanhas um track limit (ou incidente no iRacing) e
verde quando fazes uma volta limpa. Pontos acumulados numa barra até à penalização."""

from __future__ import annotations

from .. import theme as T
from ..canvas import alpha
from ..i18n import tr
from .base import Overlay


def check_mark(c, x, y, s, col, w=3.0):
    c.polyline([(x, y + s * 0.55), (x + s * 0.38, y + s * 0.9), (x + s, y + s * 0.12)], col, w)


class TrackLimitsOverlay(Overlay):
    key = "track_limits"
    defaults = {"warn_s": 6.0, "clean_s": 4.0}
    default_pos = (745, 196)
    smart_capable = True
    default_mode = "auto"

    def state(self, snap, ctx) -> str | None:
        """'hit' (acabaste de apanhar), 'clean' (volta limpa), 'ok' (sem nada) ou None (sem dados)."""
        if snap.player.tl_points < 0:
            return None
        if ctx.since("tl") < float(self.cfg["warn_s"]):
            return "hit"
        if ctx.since("lap_clean") < float(self.cfg["clean_s"]):
            return "clean"
        return "ok"

    def auto_visible(self, snap, ctx):
        return self.state(snap, ctx) in ("hit", "clean")

    def size(self, snap, ctx):
        return (330, 74)

    def render(self, c, snap, ctx, w, h):
        st = self.state(snap, ctx)
        p = snap.player
        if st is None:
            y = T.panel(c, w, h, self.title)
            c.text(0, y, w, h - y - 4, tr("tl.no_data"), 12, T.FAINT, "c", 600)
            return
        inc = p.tl_kind == "inc"
        hit = st == "hit"
        col = T.BAD if hit else T.GOOD
        lit = not hit or ctx.blink
        T.neon_frame(c, 0, 0, w, h, col, 1.5 if lit else 0.7)
        T.panel(c, w, h, accent=col)
        c.rect(1, 1, w - 2, 3, col if lit else alpha(col, 140), radius=1.5)
        # quadrado com o símbolo
        tile = col if lit else alpha(col, 150)
        c.rect(10, 10, 54, h - 20, tile, radius=4, fill2=T.scale_rgb(tile, 0.8))
        if hit:
            c.text(10, 8, 54, h - 18, "!", 40, (255, 255, 255, 255), "c", 800)
        else:
            check_mark(c, 22, 22, 30, (255, 255, 255, 255), 5)
        c.mark_static()

        pts, lim = p.tl_points, p.tl_limit
        if hit:
            title = tr("tl.hit_inc", n=f"{ctx.tl_last_add:g}") if inc else tr("tl.hit")
        else:
            title = tr("tl.ok_inc") if inc else tr("tl.ok")
        c.text(76, 8, w - 86, 28, title, 22, col if hit else T.TEXT, "l", 800, spacing=0.6)
        if lim > 0:
            sub = tr("tl.count_inc" if inc else "tl.count", p=f"{pts:g}", m=f"{lim:g}")
        else:
            sub = tr("tl.count_free", p=f"{pts:g}")
        if st == "clean":
            sub = tr("tl.clean") + "  ·  " + sub
        c.text(76, 34, w - 86, 18, sub, 13, T.DIM, "l", 600)
        # barra de pontos até à penalização
        if lim > 0:
            n = int(min(lim, 12)) if float(lim).is_integer() else 0
            bx, by, bw = 76, h - 16, w - 88
            if n:
                gap = 3
                sw = (bw - gap * (n - 1)) / n
                for i in range(n):
                    filled = i < pts
                    sc = (T.BAD if pts >= lim - 1 else T.WARN) if filled else (255, 255, 255, 26)
                    c.rect(bx + i * (sw + gap), by, sw, 6, sc, radius=2)
            else:
                frac = max(0.0, min(1.0, pts / lim))
                c.rect(bx, by, bw, 6, (255, 255, 255, 26), radius=3)
                c.rect(bx, by, bw * frac, 6, T.WARN if frac < 0.8 else T.BAD, radius=3)
