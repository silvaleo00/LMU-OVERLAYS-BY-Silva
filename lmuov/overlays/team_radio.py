"""Team Radio: o cartão "BOX, BOX." das transmissões quando há um pedido de boxes.

Aparece quando pedes boxes no jogo e (opcional) quando um rival da tua classe perto de ti pede
boxes ou entra no pit lane. Cor da equipa (pela marca do carro), número, nome da equipa e uma
onda de áudio animada. Fica uns segundos e desaparece.
"""

from __future__ import annotations

import math

from .. import theme as T
from .. import tv
from ..canvas import alpha
from ..i18n import tr
from .base import Overlay

NAVY = (8, 10, 44, 255)
NAVY2 = (16, 58, 122, 255)


def _lum(c) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


class TeamRadioOverlay(Overlay):
    key = "team_radio"
    defaults = {"show_s": 6.0, "show_player": True,
                "rivals": "near",          # off, near (perto de ti na classe), class (toda a classe), all
                "rival_range": 2}          # "near": até N posições à frente/atrás na classe
    default_pos = (1590, 330)
    contextual = True
    W, H = 300, 166

    # ------------------------------------------------------------------ #
    def _rival_ok(self, snap, v) -> bool:
        mode = str(self.cfg.get("rivals", "near"))
        if mode == "all":
            return True
        if mode == "off" or v.cls != snap.me.cls:
            return False
        if mode == "class":
            return True
        return abs(v.class_place - snap.me.class_place) <= int(self.cfg.get("rival_range", 2))

    def event(self, snap, ctx):
        """(carro, tipo, instante) a mostrar agora, ou None. O teu pedido tem prioridade."""
        show = float(self.cfg["show_s"])
        byid = {v.id: v for v in snap.vehicles}
        rival = None
        for t, vid, kind in reversed(getattr(ctx, "radio", ()) or ()):
            if not 0 <= ctx.now - t < show:
                continue
            v = byid.get(vid)
            if v is None:
                continue
            if v.is_player:
                if kind == "req" and self.cfg.get("show_player", True):
                    return v, kind, t
                continue
            if rival is None and self._rival_ok(snap, v):
                rival = (v, kind, t)
        return rival

    def has_content(self, snap, ctx):
        return self.event(snap, ctx) is not None

    def size(self, snap, ctx):
        return (self.W, self.H)

    def render(self, c, snap, ctx, w, h):
        ev = self.event(snap, ctx)
        if ev is None:
            if not ctx.edit_mode:
                return
            ev = (snap.me, "req", ctx.now)        # para posicionar no modo de edição
        v, kind, t0 = ev
        self.card(c, w, h, v, kind, ctx.now - t0, ctx.now)

    # ------------------------------------------------------------------ #
    def card(self, c, w, h, v, kind, age, now):
        bg, brand_ink = tv.brand_colors(v.vehicle_name)
        ink = T.on_color(bg)
        # cor viva para o texto e a onda sobre o azul-escuro
        if _lum(bg) > 200:                     # equipas de cor clara (branco/prata): usa a cor do logótipo
            acol = brand_ink if 40 < _lum(brand_ink) < 200 else (206, 212, 226, 255)
        elif _lum(bg) < 40:
            acol = T.lighten(bg, 0.45)
        elif _lum(bg) < 80:                    # verdes/azuis escuros: um pouco mais claros para se lerem
            acol = T.lighten(bg, 0.22)
        else:
            acol = bg
        white = (255, 255, 255, 255)
        band = 27

        T.neon_frame(c, 0, 0, w, h, acol, 0.9)
        c.rect(0, 0, w, h, bg, radius=3, fill2=T.scale_rgb(bg, 0.82))

        # faixa de cima: número grande + nome da equipa
        num = v.number or "--"
        lx = 10
        logo = tv.logo_path(tv.brand_code(v.vehicle_name))
        if logo:                                # logótipo da marca antes do número
            c.image(logo, lx + 14, band / 2, band - 6, box=(28, band - 7))
            lx += 34
        c.text(lx, 0, 80, band, num, 23, ink, "l", 800, italic=True)
        nw = lx - 10 + c.measure(num, 23, 800) + 16
        team = tv.vehicle_team(v)
        tw = w - nw - 22
        c.text(nw + 8, 0, tw, band, tv.team_short(c, team, tw, 11.5), 11.5, ink, "r", 800, spacing=0.4,
               italic=True)

        # painel azul-escuro com reflexos diagonais
        ix, iy, iw, ih = 4.0, float(band), w - 8.0, h - band - 4.0
        c.rect(ix, iy, iw, ih, NAVY, radius=2, fill2=NAVY2)
        for k, a in ((0.50, 34), (0.66, 26), (0.80, 40)):
            x0 = ix + iw * k
            c.polygon([(x0 + 40, iy + ih * 0.30), (x0 + 58, iy + ih * 0.30), (x0 + 18, iy + ih), (x0, iy + ih)],
                      (70, 150, 255, a))
        c.rect(ix, iy, iw, 1.5, (0, 0, 0, 90))

        # "TEAM RADIO"
        c.text(ix, iy + 5, iw - 12, 19, "TEAM", 18, acol, "r", 800, spacing=0.6, italic=True)
        c.text(ix, iy + 22, iw - 12, 19, "RADIO", 18, white, "r", 800, spacing=0.6, italic=True)

        # aspas + "BOX, BOX."
        qx, qy = ix + 10, iy + 47
        for d in (0, 9):
            c.polygon([(qx + d + 5, qy), (qx + d + 10, qy), (qx + d + 5, qy + 14), (qx + d, qy + 14)], acol)
        c.text(ix + 30, iy + 50, iw - 36, 48, "BOX, BOX.", 42, white, "l", 800, spacing=0.4, italic=True)
        ex, ey = ix + iw - 32, iy + ih - 22
        for d in (0, 9):
            c.polygon([(ex + d + 5, ey), (ex + d + 10, ey), (ex + d + 5, ey + 14), (ex + d, ey + 14)],
                      alpha(acol, 150))

        # legenda em baixo
        if kind == "req" and v.is_player:
            sub = tr("radio.req")
        else:
            short = T.class_info(v.cls)[0]
            sub = f"P{v.class_place} {short} · " + (tr("radio.req") if kind == "req" else tr("radio.in"))
        c.text(ix + 10, iy + ih - 20, iw * 0.7, 16, sub.upper(), 10, (120, 170, 255, 255), "l", 800, spacing=0.8,
               italic=True)

        c.mark_static()                      # só a onda muda a cada frame
        # onda de áudio animada (mais forte no início)
        cy, amp = iy + 22, 10.5
        n = 34
        boost = 1.0 if age > 0.4 else 0.5 + age * 1.25
        for i in range(n):
            u = i / (n - 1)
            env = math.sin(math.pi * u) ** 0.7
            a = 0.18 + 0.82 * abs(math.sin(i * 0.93 + now * 9.0) * math.sin(i * 0.41 - now * 5.3 + 1.1))
            hh = max(1.2, amp * env * a * boost)
            x = ix + 10 + i * 3.4
            c.rect(x, cy - hh, 2.0, hh * 2, alpha(acol, 150 + int(105 * env)))
