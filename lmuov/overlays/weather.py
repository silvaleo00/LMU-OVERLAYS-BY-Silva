"""Weather: água na pista (%), chuva, céu e quando vai chover ou secar (em voltas).

A previsão vem do jogo quando existe (LMU); senão é estimada pela tendência dos últimos minutos.
"""

from __future__ import annotations

from .. import theme as T
from ..canvas import alpha
from ..i18n import tr
from ..weathercalc import outlook
from .base import Overlay

STATE_COL = {"dry": (40, 214, 118, 255), "damp": (255, 196, 36, 255), "wet": (48, 148, 255, 255),
             "soaked": (130, 90, 255, 255)}
RAIN_COL = (48, 148, 255, 255)


def sky_name(sky: int) -> str:
    if sky < 0:
        return ""
    if sky <= 1:
        return tr("wx.sky_clear")
    if sky <= 3:
        return tr("wx.sky_cloudy")
    if sky == 4:
        return tr("wx.sky_overcast")
    if sky <= 7:
        return tr("wx.sky_light")
    if sky == 8:
        return tr("wx.sky_rain")
    return tr("wx.sky_heavy")


class WeatherOverlay(Overlay):
    key = "weather"
    defaults = {"warn_laps": 10}
    default_pos = (1225, 320)
    smart_capable = True
    default_mode = "auto"

    def auto_visible(self, snap, ctx):
        s = snap.session
        o = outlook(snap, ctx)
        soon = o.eta_laps is not None and o.eta_laps <= float(self.cfg["warn_laps"])
        return (s.rain > 0.02 or s.wetness > 0.02 or soon or ctx.since("start") < 20 or ctx.since("lap") < 8)

    def size(self, snap, ctx):
        return (330, 214)

    def render(self, c, snap, ctx, w, h):
        s = snap.session
        o = outlook(snap, ctx)
        y = T.panel(c, w, h, self.title, sky_name(o.sky), part="bg")
        c.text(14, y, 200, 14, tr("wx.water"), 10, T.FAINT, "l", 700, spacing=1)
        c.text(w - 160, y, 146, 14, tr("wx.rain"), 10, T.FAINT, "r", 700, spacing=1)
        c.rect(14, y + 50, w - 28, 10, (255, 255, 255, 18), radius=5)
        c.mark_static()
        T.panel(c, w, h, self.title, sky_name(o.sky), part="right")

        scol = STATE_COL[o.state]
        c.text(14, y + 10, 130, 40, f"{o.water * 100:.0f}%", 36, scol, "l", 800)
        c.text(118, y + 18, 120, 30, tr(f"wx.{o.state}").upper(), 15, scol, "l", 800, spacing=1)
        c.text(w - 160, y + 10, 146, 40, f"{o.rain * 100:.0f}%", 30, RAIN_COL if o.rain > 0.02 else T.DIM, "r", 800)
        # barra da água: valor médio + intervalo mín–máx
        bx, bw, by = 14, w - 28, y + 50
        if o.water_max > o.water_min:
            c.rect(bx + bw * o.water_min, by, bw * (o.water_max - o.water_min), 10, alpha(scol, 70), radius=5)
        if o.water > 0.002:
            T.neon_glow(c, bx, by, max(6.0, bw * o.water), 10, scol, 0.7)
            c.rect(bx, by, max(6.0, bw * min(1.0, o.water)), 10, scol, radius=5)
        for k in (0.05, 0.15, 0.45):                    # limites seco / húmido / molhado / encharcado
            c.rect(bx + bw * k - 0.5, by - 2, 1, 14, (255, 255, 255, 70))
        if abs(o.trend_water) > 0.003:                 # tendência da água: seta + %/min
            up = o.trend_water > 0
            txt = f"{abs(o.trend_water) * 100:.1f}%/min"
            tw = c.measure(txt, 10, 700)
            ax, ay = bx + bw - tw - 12, by + 18
            c.polygon([(ax, ay + (3 if up else -3)), (ax + 8, ay + (3 if up else -3)), (ax + 4, ay + (-4 if up else 4))],
                      RAIN_COL if up else T.GOOD)
            c.text(bx, by + 11, bw, 14, txt, 10, T.DIM, "r", 700)

        # o que aí vem
        yy = y + 80
        if o.event == "rain":
            txt, col = tr("wx.rain_in", n=f"{max(0.1, o.eta_laps):.0f}" if o.eta_laps >= 1 else "<1"), RAIN_COL
        elif o.event == "dry":
            txt, col = tr("wx.dry_in", n=f"{max(0.1, o.eta_laps):.0f}" if o.eta_laps >= 1 else "<1"), T.GOOD
        elif o.rain >= 0.05:
            txt, col = tr("wx.rain_now"), RAIN_COL
        else:
            txt, col = tr("wx.stable"), T.TEXT
        c.rect(8, yy, w - 16, 34, alpha(col, 34), radius=4)
        c.rect(8, yy + 4, 3, 26, col, radius=1.5)
        c.text(18, yy, w - 36, 34, txt, 18, col if col is not T.TEXT else T.TEXT, "l", 800)
        if o.source:
            c.text(18, yy, w - 36, 34, tr(f"wx.src_{o.source}"), 10, T.FAINT, "r", 600)

        # previsão por pontos da sessão
        yy += 42
        nodes = [n for n in o.nodes if n[0] >= 0][:4]
        air = tr("wx.air", a=f"{s.air_temp:.0f}", t=f"{s.track_temp:.0f}")
        if nodes:
            c.text(14, yy, 120, 14, tr("wx.next"), 10, T.FAINT, "l", 700, spacing=1)
            c.text(130, yy, w - 144, 14, air, 10, T.FAINT, "r", 600)
            cw = (w - 28 - 6 * (len(nodes) - 1)) / len(nodes)
            for i, (laps, ch, sky) in enumerate(nodes):
                x = 14 + i * (cw + 6)
                ccol = RAIN_COL if ch >= 0.5 or sky >= 5 else (T.WARN if ch >= 0.3 else T.GOOD)
                c.rect(x, yy + 15, cw, 30, (255, 255, 255, 12), radius=3)
                c.rect(x, yy + 15 + 27, cw * ch, 3, ccol, radius=1.5)
                c.text(x, yy + 14, cw, 16, tr("wx.laps_short", n=f"{laps:.0f}"), 10, T.DIM, "c", 700)
                c.text(x, yy + 26, cw, 16, f"{ch * 100:.0f}%", 13, ccol, "c", 800)
        else:
            c.text(14, yy + 4, w - 28, 18, air, 12, T.DIM, "l", 600)
