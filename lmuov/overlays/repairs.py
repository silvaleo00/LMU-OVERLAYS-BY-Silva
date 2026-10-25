"""Vehicle Health & Repairs: quão estragado está o carro (%) e quanto tempo demora a arranjar.

LMU: saúde pela média ponderada das peças (aero, suspensão, carroçaria, rodas, motor) e o tempo de
reparação que o PRÓPRIO jogo estima (o mesmo do menu das boxes), mais o tempo total da paragem.
iRacing: não dá dano por peça; usa o tempo de reparação obrigatória e opcional do jogo.
"""

from __future__ import annotations

from .. import theme as T
from ..canvas import alpha
from ..i18n import tr
from .base import Overlay
from .damage import HEALTH_PARTS, health_color, health_parts, repair_time, vehicle_health


def fmt_time(s: float) -> str:
    if s < 0:
        return "—"
    s = int(round(s))
    return f"{s // 60}:{s % 60:02d}" if s >= 60 else f"{s} s"


class RepairsOverlay(Overlay):
    key = "repairs"
    defaults = {"impact_s": 10.0}
    default_pos = (1225, 860)
    smart_capable = True
    default_mode = "auto"
    W, H = 330, 176

    def auto_visible(self, snap, ctx):
        p = snap.player
        h = vehicle_health(p)
        return ((h is not None and h < 99.5) or repair_time(p) > 0 or snap.me.in_pits
                or ctx.since("impact") < float(self.cfg["impact_s"]))

    def size(self, snap, ctx):
        return (self.W, self.H)

    def render(self, c, snap, ctx, w, h):
        p = snap.player
        hp = vehicle_health(p)
        rt = repair_time(p)
        right = tr("rep.none") if rt == 0 else (tr("rep.needed") if rt > 0 else "")
        y = T.panel(c, w, h, self.title, right, part="bg")
        c.mark_static()
        T.panel(c, w, h, self.title, right, part="right")
        col = health_color(hp) if hp is not None else T.FAINT
        # saúde do carro
        c.text(14, y + 2, 120, 14, tr("rep.health").upper(), 9, T.FAINT, "l", 800, spacing=1)
        c.text(12, y + 14, 140, 40, "—" if hp is None else f"{hp:.0f}%", 36, col, "l", 800)
        # tempo de reparação (estimativa do jogo)
        c.text(w - 160, y + 2, 146, 14, tr("rep.repair").upper(), 9, T.FAINT, "r", 800, spacing=1)
        c.text(w - 170, y + 14, 156, 40, fmt_time(rt), 32, T.TEXT if rt <= 0 else T.WARN, "r", 800)
        by = y + 58
        c.rect(12, by, w - 24, 6, (255, 255, 255, 22), radius=3)
        if hp is not None and hp > 0:
            c.rect(12, by, (w - 24) * hp / 100, 6, col, radius=3)
        # sistemas
        parts = health_parts(p)
        names = [(k, wgt) for k, wgt in HEALTH_PARTS if k in parts]
        if names and (p.dents or p.aero_damage >= 0):
            cw = (w - 24) / len(names)
            for i, (k, _w) in enumerate(names):
                x = 12 + i * cw
                ok = 1.0 - parts[k]
                kc = health_color(ok * 100)
                c.text(x, by + 12, cw - 4, 14, tr(f"rep.p.{k}"), 10, T.DIM, "c", 700)
                c.rect(x + 6, by + 28, cw - 16, 4, (255, 255, 255, 22), radius=2)
                c.rect(x + 6, by + 28, (cw - 16) * ok, 4, kc, radius=2)
                c.text(x, by + 33, cw - 4, 16, f"{ok * 100:.0f}%", 11, kc if ok < 0.995 else T.TEXT, "c", 800)
        # linha de baixo: paragem total (LMU) ou obrigatória/opcional (iRacing)
        fy = h - 22
        if p.pit_est >= 0:
            txt = tr("rep.pit_total", t=fmt_time(p.pit_est))
        elif p.repair_req >= 0 or p.repair_opt >= 0:
            txt = tr("rep.req_opt", a=fmt_time(max(0.0, p.repair_req)), b=fmt_time(max(0.0, p.repair_opt)))
        else:
            txt = tr("rep.no_data") if hp is None else ""
        c.rect(0, fy - 2, w, 1, (255, 255, 255, 20))
        c.text(12, fy, w - 24, 18, txt, 11, T.DIM, "c", 600)
