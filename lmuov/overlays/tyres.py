"""Tyres (extra): temperaturas esq/centro/dir, pressão, desgaste, carcaça e travões."""

from __future__ import annotations

from .. import theme as T
from ..i18n import tr
from .base import Overlay

PRESSURE = {"kPa": (1.0, "{:.1f}"), "psi": (0.145038, "{:.2f}"), "bar": (0.01, "{:.3f}")}


class TyresOverlay(Overlay):
    key = "tyres"
    # cores das temperaturas: "fixed" = escala por graus (limites abaixo), "optimal" = à volta da temperatura ótima
    # temp_source: que temperatura mostrar. O LMU dá três: "surface" (superfície, arrefece logo no ar),
    # "inner" (camada interior da borracha, a que o HUD do jogo mostra) e "carcass" (carcaça).
    defaults = {"show_brakes": True, "fallback_optimal": 88.0, "temp_scale": "fixed", "temp_source": "inner",
                "t_blue": 50, "t_light_green": 60, "t_green": 75, "t_yellow": 85}
    default_pos = (1240, 310)
    default_enabled = False

    CARD_W, CARD_H, GAP = 160, 96, 8

    smart_capable = True
    default_mode = "auto"

    def auto_visible(self, snap, ctx):
        """Depois de cada volta, nas boxes, com furo ou com algum pneu fora da janela."""
        if ctx.since("lap") < 12 or snap.me.in_pits:
            return True
        fb = float(self.cfg["fallback_optimal"])
        fixed = self.cfg.get("temp_scale", "fixed") == "fixed"
        lo, hi = float(self.cfg.get("t_blue", 50)), float(self.cfg.get("t_yellow", 85))
        for t in snap.player.tyres:
            opt = t.optimal if t.optimal > 20 else fb
            if t.flat or t.detached:
                return True
            temps = self._temps(t)
            if fixed and any(x <= lo or x > hi for x in temps if x > 0):
                return True
            if not fixed and any(abs(x - opt) > 18 for x in temps):
                return True
        return False

    def _temps(self, t) -> tuple:
        """As 3 temperaturas (esq./centro/dir.) da fonte escolhida; cai para a superfície se faltar."""
        src = self.cfg.get("temp_source", "inner")
        if src == "inner" and any(x > 0 for x in t.inner_lcr):
            return t.inner_lcr
        if src == "carcass" and t.carcass > 0:
            return (t.carcass, t.carcass, t.carcass)
        return t.temp_lcr

    def _tcol(self, temp: float, opt: float) -> tuple:
        if self.cfg.get("temp_scale", "fixed") != "fixed":
            return T.temp_color(temp, opt)
        g = self.cfg
        bands = ((float(g.get("t_blue", 50)), T.TYRE_BANDS[0][1]), (float(g.get("t_light_green", 60)), T.TYRE_BANDS[1][1]),
                 (float(g.get("t_green", 75)), T.TYRE_BANDS[2][1]), (float(g.get("t_yellow", 85)), T.TYRE_BANDS[3][1]))
        return T.tyre_band_color(temp, bands)

    def size(self, snap, ctx):
        return (self.CARD_W * 2 + self.GAP * 3, T.HEADER_H + 5 + self.CARD_H * 2 + self.GAP * 2)

    def render(self, c, snap, ctx, w, h):
        p = snap.player
        cf, cr = p.compound_front, p.compound_rear
        comp = cf if cf == cr or not cr else f"{cf} / {cr}"
        y0 = T.panel(c, w, h, self.title, comp)
        c.mark_static()
        for i, tyre in enumerate(p.tyres[:4]):
            col, row = i % 2, i // 2
            x = self.GAP + col * (self.CARD_W + self.GAP)
            y = y0 + row * (self.CARD_H + self.GAP)
            self._card(c, x, y, tyre, ctx.wear_per_lap[i] if i < len(ctx.wear_per_lap) else 0.0, ctx)

    def _card(self, c, x, y, t, wear_lap, ctx):
        W, H = self.CARD_W, self.CARD_H
        bad = t.flat or t.detached
        c.rect(x, y, W, H, (255, 255, 255, 10), radius=6, stroke=T.BAD if bad else (255, 255, 255, 18),
               stroke_w=2 if bad else 1)
        opt = t.optimal if t.optimal > 20 else self.cfg["fallback_optimal"]
        bw = (W - 12 - 4) / 3
        for k, temp in enumerate(self._temps(t)):
            bx = x + 6 + k * (bw + 2)
            col = self._tcol(temp, opt)
            c.rect(bx, y + 6, bw, 26, col, radius=4)
            c.text(bx, y + 6, bw, 26, f"{temp:.0f}°", 16, T.on_color(col), "c", 800)
        unit = ctx.cfg.get("pressure_unit", "kPa")
        unit = unit if unit in PRESSURE else "kPa"
        mul, fmt = PRESSURE[unit]
        if bad:
            c.text(x + 8, y + 36, W - 16, 26, tr("ty.flat") if t.flat else tr("ty.loose"), 20, T.BAD, "l", 800)
        else:
            ptxt = fmt.format(t.pressure * mul)
            c.text(x + 8, y + 36, W - 16, 26, ptxt, 21, T.TEXT, "l", 700)
            pw = c.measure(ptxt, 21, 700)
            c.text(x + 11 + pw, y + 41, 40, 20, unit, 11, T.DIM, "l", 600)
        wear = max(0.0, min(1.0, t.wear)) * 100
        wcol = T.GOOD if wear >= 70 else T.WARN if wear >= 40 else T.BAD
        c.text(x + 8, y + 36, W - 16, 26, f"{wear:.0f}%", 21, wcol, "r", 800)
        bar_w = W - 16 - (54 if wear_lap > 0 else 0)
        c.rect(x + 8, y + 66, bar_w, 4, (255, 255, 255, 24), radius=2)
        c.rect(x + 8, y + 66, bar_w * wear / 100, 4, wcol, radius=2)
        if wear_lap > 0:
            c.text(x + W - 60, y + 60, 52, 16, tr("ty.per_lap", x=f"{wear_lap:.1f}"), 11, T.DIM, "r", 600)
        dy = y + 73
        ccol = self._tcol(t.carcass, opt) if t.carcass > 0 else T.DIM
        c.text(x + 8, dy, 76, 18, tr("ty.carcass", x=f"{t.carcass:.0f}"), 12, ccol, "l", 600)
        if self.cfg["show_brakes"] and t.brake_temp > 0:
            c.text(x + 8, dy, W - 16, 18, tr("ty.brake", x=f"{t.brake_temp:.0f}"), 12,
                   self._brake_col(t.brake_temp), "r", 600)

    @staticmethod
    def _brake_col(b):
        if b < 250:
            return (110, 160, 255, 255)
        if b < 750:
            return T.DIM
        if b < 900:
            return T.WARN
        return T.BAD
