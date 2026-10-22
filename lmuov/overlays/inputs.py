"""Input Graphics: barra compacta com módulos que se ligam/desligam.

  [mudança + velocidade + TC/ABS] [volante] [gráfico dos comandos] [pedais com %]

O volante é opcional e pode ser um dos desenhos (simples, normal, GT, fórmula, F1, antigo, rali,
camião, barco) ou uma foto PNG do teu volante. O gráfico mostra acelerador (verde), travão
(vermelho, laranja com ABS), embraiagem (azul) e direção (amarelo); as marcas por baixo mostram
onde o ABS e o TC atuaram.
"""

from __future__ import annotations

import math

from .. import theme as T
from ..canvas import alpha
from ..i18n import tr
from ..paths import app_dir
from ..wheels import STYLES, draw_wheel
from .base import Overlay

THR = (38, 214, 118, 255)
BRK = (255, 66, 78, 255)
CLU = (48, 148, 255, 255)
STEER = (255, 196, 36, 255)
ABS_ON = (255, 140, 40, 255)
GEAR_COL = (255, 186, 0, 255)

H = 78
W_GEAR, W_WHEEL, W_PEDALS = 92, 74, 70


def wheel_image(name: str) -> str | None:
    """Caminho da foto do volante (guardada em data/wheels)."""
    if not name:
        return None
    p = app_dir() / "data" / "wheels" / name
    return str(p) if p.exists() else None


class InputsOverlay(Overlay):
    key = "inputs"
    defaults = {"window_s": 5.0, "trace_w": 230, "show_gear": True, "show_wheel": True, "show_trace": True,
                "show_pedals": True, "show_clutch": True, "show_steering_trace": True, "show_aids": True,
                "wheel": "simple",          # simple, normal, gt, formula, f1, old_school, rally, truck, boat, custom
                "wheel_image": ""}          # nome do PNG em data/wheels (para "custom")
    default_pos = (1430, 960)

    def modules(self) -> list[tuple[str, float]]:
        cfg = self.cfg
        out = []
        if cfg.get("show_gear", True) and not (cfg.get("show_wheel", True) and cfg.get("wheel") == "simple"):
            out.append(("gear", W_GEAR))
        if cfg.get("show_wheel", True):
            out.append(("wheel", W_WHEEL))
        if cfg.get("show_trace", True):
            out.append(("trace", max(100.0, float(cfg.get("trace_w", 230)))))
        if cfg.get("show_pedals", True):
            out.append(("pedals", W_PEDALS if cfg.get("show_clutch", True) else W_PEDALS - 22))
        return out or [("gear", W_GEAR)]

    def size(self, snap, ctx):
        return (int(sum(w for _k, w in self.modules()) + 12), H)

    # ------------------------------------------------------------------ #
    def render(self, c, snap, ctx, w, h):
        p = snap.player
        mods = self.modules()
        T.panel(c, w, h)
        # fundo fixo de cada módulo (fica em cache)
        x = 6.0
        geo = {}
        for i, (k, mw) in enumerate(mods):
            geo[k] = (x, mw)
            if i:
                c.rect(x - 0.5, 10, 1, h - 20, (255, 255, 255, 18))
            if k == "trace":
                gx, gy, gw, gh = x + 6, 9, mw - 12, h - 18
                c.rect(gx, gy, gw, gh, (255, 255, 255, 6), radius=2)
                for f in (0.25, 0.5, 0.75):
                    c.rect(gx, gy + gh * f, gw, 1, (255, 255, 255, 14 if f != 0.5 else 22))
                for f in (0.25, 0.5, 0.75):
                    c.rect(gx + gw * f, gy, 1, gh, (255, 255, 255, 8))
            elif k == "pedals":
                for j, _ in enumerate(self._pedals(p)):
                    bx = x + 8 + j * 22
                    c.rect(bx, 22, 14, h - 32, (255, 255, 255, 16), radius=2)
            elif k == "gear":
                mph = ctx.cfg.get("speed_unit") == "mph"
                c.text(x + 42, 42, mw - 46, 12, "MPH" if mph else "KPH", 9, T.FAINT, "l", 700, spacing=1)
            x += mw
        c.mark_static()

        for k, (x, mw) in geo.items():
            getattr(self, f"_m_{k}")(c, snap, ctx, x, mw, h)

    # ---- módulos -------------------------------------------------------- #
    def _speed(self, p, ctx) -> str:
        mph = ctx.cfg.get("speed_unit") == "mph"
        return f"{p.speed * (2.23694 if mph else 3.6):.0f}"

    @staticmethod
    def _gear(p) -> str:
        return "R" if p.gear < 0 else "N" if p.gear == 0 else str(p.gear)

    def _m_gear(self, c, snap, ctx, x, mw, h):
        p = snap.player
        full = p.max_rpm > 0 and p.rpm >= 0.97 * p.max_rpm
        col = (255, 66, 78, 255) if full and ctx.blink else GEAR_COL
        c.text(x + 4, 6, 40, 46, self._gear(p), 42, col, "c", 800)
        c.text(x + 42, 14, mw - 46, 28, self._speed(p, ctx), 22, T.TEXT, "l", 800)
        if self.cfg.get("show_aids", True):            # TC / ABS a atuar
            for i, (lab, on, oc) in enumerate((("TC", p.tc_active, T.WARN), ("ABS", p.abs_active, ABS_ON))):
                bx = x + 6 + i * 40
                col = oc if on else (255, 255, 255, 18)
                if on:
                    T.neon_glow(c, bx, h - 20, 34, 13, oc, 0.8)
                c.rect(bx, h - 20, 34, 13, col, radius=3)
                c.text(bx, h - 20, 34, 13, lab, 9, T.DARK_TEXT if on else T.FAINT, "c", 800, spacing=0.5)

    def _m_wheel(self, c, snap, ctx, x, mw, h):
        p = snap.player
        rng = p.steering_range if p.steering_range > 0 else 450.0
        ang = p.steering * rng / 2
        style = str(self.cfg.get("wheel", "simple"))
        if style not in STYLES:
            style = "normal"
        r = min(mw, h) / 2 - 8
        rpm = p.rpm / p.max_rpm if p.max_rpm > 0 else None
        draw_wheel(c, x + mw / 2, h / 2, r, math.radians(ang), style,
                   image=wheel_image(self.cfg.get("wheel_image", "")),
                   gear=self._gear(p), speed=self._speed(p, ctx), rpm=rpm)

    def _m_trace(self, c, snap, ctx, x, mw, h):
        gx, gy, gw, gh = x + 6, 9, mw - 12, h - 18
        hist = ctx.inputs
        if len(hist) < 2:
            return
        t1 = hist[-1][0]
        win = float(self.cfg["window_s"])
        step = max(1, len(hist) // min(100, int(gw / 2)))
        pts = hist[::step] + ([hist[-1]] if (len(hist) - 1) % step else [])
        pts = [e for e in pts if t1 - e[0] <= win]

        def X(e):
            return gx + gw * (1 - (t1 - e[0]) / win)

        def series(idx):
            return [(X(e), gy + gh - max(0.0, min(1.0, e[idx])) * gh) for e in pts]

        if self.cfg.get("show_steering_trace", True):
            c.polyline([(X(e), gy + gh / 2 - max(-1.0, min(1.0, e[4])) * gh / 2) for e in pts], alpha(STEER, 200), 1.3)
        if self.cfg.get("show_clutch", True) and any(e[3] > 0.01 for e in pts):
            c.polyline(series(3), CLU, 1.5)
        T.neon_polyline(c, series(1), THR, 2.0)
        T.neon_polyline(c, series(2), BRK, 2.0)
        # ABS / TC a atuar: marcas por baixo do gráfico
        if self.cfg.get("show_aids", True) and len(pts[0]) > 6:
            for e in pts:
                if e[5]:
                    c.rect(X(e) - 1, gy + gh - 3, 2, 3, ABS_ON)
                if e[6]:
                    c.rect(X(e) - 1, gy, 2, 3, T.WARN)

    def _pedals(self, p):
        out = []
        if self.cfg.get("show_clutch", True):
            out.append(("C", p.clutch, CLU))
        out.append(("B", p.brake, ABS_ON if p.abs_active else BRK))
        out.append(("T", p.throttle, T.WARN if p.tc_active else THR))
        return out

    def _m_pedals(self, c, snap, ctx, x, mw, h):
        for j, (_lab, val, col) in enumerate(self._pedals(snap.player)):
            bx = x + 8 + j * 22
            v = max(0.0, min(1.0, val))
            bh = h - 32
            c.text(bx - 5, 6, 24, 14, f"{v * 100:.0f}", 10, T.TEXT if v > 0.005 else T.FAINT, "c", 800)
            if v > 0.005:
                T.neon_glow(c, bx, 22 + bh * (1 - v), 14, bh * v, col, 0.8)
                c.rect(bx, 22 + bh * (1 - v), 14, bh * v, col, radius=2)
