"""Advanced Panel: velocidade, mudança, RPM com luzes de mudança, e ajudas (TC, ABS, BB, mapa, bateria)."""

from __future__ import annotations

import math

from .. import theme as T
from .. import tv
from ..canvas import alpha
from ..i18n import tr
from .base import Overlay

LED_COLS = [(38, 214, 118, 255)] * 5 + [(255, 196, 36, 255)] * 5 + [(255, 66, 78, 255)] * 5
LED_OFF = (255, 255, 255, 22)
SHIFT = (70, 140, 255, 255)
ABS_ON = (255, 140, 40, 255)


class AdvancedOverlay(Overlay):
    key = "advanced"
    defaults = {"shift_start": 0.80, "shift_full": 0.965}
    default_pos = (745, 900)

    def size(self, snap, ctx):
        return (430, 162)

    def render(self, c, snap, ctx, w, h):
        p = snap.player
        T.panel(c, w, h)

        # fundo fixo: LEDs apagados, legendas e calha da barra de RPM (fica em cache)
        n = len(LED_COLS)
        lw = (w - 28 - (n - 1) * 4) / n
        for i in range(n):
            c.rect(14 + i * (lw + 4), 10, lw, 12, LED_OFF)
        gw, gh = 92, 82
        gx, gy = w / 2 - gw / 2, 32
        mph = ctx.cfg.get("speed_unit") == "mph"
        c.text(14, gy + 2, gx - 26, 14, "MPH" if mph else "KM/H", 10, T.FAINT, "r", 700, spacing=1)
        rx = gx + gw + 12
        c.text(rx, gy + 2, w - rx - 14, 14, tr("adv.rpm"), 10, T.FAINT, "l", 700, spacing=1)
        bw = w - rx - 16
        c.rect(rx, gy + 62, bw, 6, (255, 255, 255, 20))
        c.mark_static()

        # luzes de mudança
        r = p.rpm / p.max_rpm if p.max_rpm > 0 else 0.0
        st, full = float(self.cfg["shift_start"]), float(self.cfg["shift_full"])
        lit = n if r >= full else max(0, min(n, math.ceil((r - st) / max(0.01, full - st) * n)))
        for i in range(n):
            x = 14 + i * (lw + 4)
            if r >= full:
                col = SHIFT if ctx.blink else LED_OFF
            else:
                col = LED_COLS[i] if i < lit else LED_OFF
            if col is LED_OFF:
                continue
            if T.NEON:
                T.neon_glow(c, x, 10, lw, 12, col, 1.3)
            else:
                c.rect(x - 1.5, 8.5, lw + 3, 15, alpha(col, 60))
            c.rect(x, 10, lw, 12, col)
            if T.NEON:
                c.rect(x + 2, 12, lw - 4, 3, T.lighten(col, 0.7))

        # mudança no centro
        T.neon_glow(c, gx, gy, gw, gh, T.ME if r >= full else T.ACCENT, 1.0 if r >= full else 0.5)
        focus = T.SKIN.get("focus")
        if r < full and focus == "gradient":          # caixa em gradiente (Horizon, Aurora, Inferno)
            tv.grad_slant(c, gx, gy, gw - 10, gh, T.ACCENT, T.SKIN.get("accent2") or T.ACCENT, k=10)
        elif r < full and focus == "outline":         # caixa só com contorno (Hologram)
            T.skew_rect(c, gx, gy, gw, gh, alpha(T.ACCENT, 46), skew=10, stroke=T.ACCENT)
        else:
            T.skew_rect(c, gx, gy, gw, gh, T.ME if r >= full else tv.FOCUS_BG, skew=10)
        gear = "R" if p.gear < 0 else "N" if p.gear == 0 else str(p.gear)
        c.text(gx, gy - 2, gw, gh, gear, 72, tv.FOCUS_INK if r < full else T.TV_INK, "c", 800)

        # velocidade (esquerda) e RPM (direita)
        spd = p.speed * (2.23694 if mph else 3.6)
        c.text(14, gy + 14, gx - 26, 58, f"{spd:.0f}", 54, T.TEXT, "r", 800)
        c.text(rx, gy + 16, w - rx - 14, 40, f"{p.rpm:,.0f}", 34, T.TEXT, "l", 800)
        if r > 0:
            col = T.BAD if r >= full else (T.WARN if r >= st else T.ACCENT)
            c.rect(rx, gy + 62, bw * min(1.0, r), 6, col)

        # linha de ajudas
        y = h - 42
        if p.limiter_on:
            col = T.INFO if ctx.blink else alpha(T.INFO, 150)
            T.chip(c, 14, y, w - 28, 28, tr("adv.limiter"), col, size=15, weight=800)
            return
        chips = []
        if p.tc_max > 0 or p.tc > 0:
            chips.append((tr("adv.tc"), str(p.tc), T.WARN if p.tc_active else None))
            if p.tc_cut:
                chips.append((tr("adv.tc_cut"), str(p.tc_cut), None))
            if p.tc_slip:
                chips.append((tr("adv.slip"), str(p.tc_slip), None))
        if p.abs_max > 0 or p.abs > 0:
            chips.append((tr("adv.abs"), str(p.abs), ABS_ON if p.abs_active else None))
        if p.brake_bias > 0:
            chips.append((tr("adv.bb"), f"{p.brake_bias:.1f}", None))
        chips.append((tr("adv.map"), str(p.motor_map), None))
        if p.battery >= 0:
            chips.append((tr("adv.bat"), f"{p.battery * 100:.0f}%", None))
        cw = (w - 28 - (len(chips) - 1) * 6) / max(1, len(chips))
        for i, (label, val, active) in enumerate(chips):
            x = 14 + i * (cw + 6)
            bg = active if active else (255, 255, 255, 12)
            fg = T.DARK_TEXT if active else T.TEXT
            c.rect(x, y, cw, 32, bg, stroke=None if active else (255, 255, 255, 22))
            c.text(x + 2, y + 2, cw - 4, 11, label, 9, T.DARK_TEXT if active else T.FAINT, "c", 700, spacing=0.6)
            c.text(x + 2, y + 12, cw - 4, 20, val, 17, fg, "c", 800)
