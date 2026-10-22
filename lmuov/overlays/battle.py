"""Battle: tu e os carros imediatamente à frente e atrás na tua classe, estilo TV.

Entre os cartões aparece o intervalo: faixa vermelha a ≤0.3 s, âmbar a ≤0.5 s.
Por baixo, quanto se está a ganhar ou perder por volta (pela última volta de cada um).
"""

from __future__ import annotations

from .. import theme as T
from .. import tv
from ..canvas import alpha
from ..i18n import tr
from .base import Overlay

CARD_W, CARD_H, PILL_W = 168, 54, 76


class BattleOverlay(Overlay):
    key = "battle"
    defaults = {"ahead": 1, "behind": 1, "red_s": 0.3, "amber_s": 0.5, "battle_s": 1.5}
    smart_capable = True
    default_mode = "auto"
    default_pos = (632, 796)
    default_sessions = ("race",)   # em treino/quali liga-se no painel

    def _cars(self, snap):
        me = snap.me
        cars = sorted((v for v in snap.vehicles if v.cls == me.cls and not v.in_garage), key=lambda v: v.class_place)
        i = cars.index(me) if me in cars else 0
        a, b = int(self.cfg["ahead"]), int(self.cfg["behind"])
        return cars[max(0, i - a): i + b + 1]

    def auto_visible(self, snap, ctx):
        """Só quando há luta: alguém da classe a menos de `battle_s` à frente ou atrás."""
        if ctx.since("pos") < 10:
            return True
        cars = self._cars(snap)
        race = snap.session.kind == "race"
        lim = float(self.cfg["battle_s"])
        for front, back in zip(cars, cars[1:]):
            if snap.me in (front, back):
                g = tv.gap_value(back, front, race)
                if g is not None and g <= lim:
                    return True
        return False

    def size(self, snap, ctx):
        n = 1 + int(self.cfg["ahead"]) + int(self.cfg["behind"])
        return (n * CARD_W + (n - 1) * PILL_W, 22 + CARD_H + 22)

    def render(self, c, snap, ctx, w, h):
        cars = self._cars(snap)
        race = snap.session.kind == "race"
        short, ccol = T.class_info(snap.me.cls)
        # separador do título
        tab = f"{short}  ·  {tr('ov.battle').upper()}"
        tw = c.measure(tab, 11, 800, 1.2) + 30
        if T.SKIN.get("header") in ("tv", "carbon", "retro"):
            tv.slant(c, 0, 0, tw, 20, T.TV_HEAD if T.SKIN.get("header") == "retro" else tv.INK, k=0)
            c.polygon([(tw, 0), (tw + 10, 0), (tw, 20)], T.TV_HEAD if T.SKIN.get("header") == "retro" else tv.INK)
        c.rect(0, 0, 4, 20, ccol)
        hs = T.SKIN.get("header")
        tab_ink = (255, 255, 255, 255) if hs in ("tv", "carbon") else (
            T.SKIN.get("head_ink", T.TEXT) if hs == "retro" else T.TEXT)
        c.text(12, 0, tw, 20, tab, 11, tab_ink, "l", 800, spacing=1.2)

        n_slots = 1 + int(self.cfg["ahead"]) + int(self.cfg["behind"])
        me_i = cars.index(snap.me) if snap.me in cars else 0
        offset = int(self.cfg["ahead"]) - me_i       # alinha "tu" sempre no mesmo cartão
        y = 22
        for k, v in enumerate(cars):
            slot = k + offset
            if not 0 <= slot < n_slots:
                continue
            x = slot * (CARD_W + PILL_W)
            self._card(c, x, y, v, ccol)
            if k + 1 < len(cars) and slot + 1 < n_slots:
                self._pill(c, x + CARD_W, y, v, cars[k + 1], race, ctx)

    def _card(self, c, x, y, v, ccol):
        focus = v.is_player
        if focus:
            T.neon_frame(c, x, y, CARD_W, CARD_H, T.ME, 0.9)
        if not focus and tv.ROW[3] == 0:
            T.body(c, x, y, CARD_W, CARD_H)
        tv.row_bg(c, x, y, CARD_W, CARD_H, focus)
        c.rect(x, y + CARD_H - 3, CARD_W, 3, T.ME if focus else ccol)
        tv.pos_box(c, x + 6, y + 6, 34, 24, str(v.class_place), focus)
        tv.plate(c, x + 46, y + 8, 34, 20, tv.brand_code(v.vehicle_name), focus)
        c.text(x + 86, y + 4, CARD_W - 92, 28, f"#{v.number}" if v.number else "", 14,
               tv.FOCUS_INK if focus else ccol, "l", 800)
        ink = tv.FOCUS_INK if focus else T.TEXT
        c.text(x + 8, y + 30, CARD_W - 16, 20, tv.surname(v.driver), 16, ink, "l", 800, spacing=0.3)
        last = T.laptime(v.last)
        c.text(x + 8, y + 30, CARD_W - 16, 20, last, 12, alpha(tv.FOCUS_INK, 160) if focus else T.DIM, "r", 600)

    def _pill(self, c, x, y, front, back, race, ctx):
        """Intervalo entre 'front' (à frente) e 'back' (atrás)."""
        g = tv.gap_value(back, front, race)
        red, amber = float(self.cfg["red_s"]), float(self.cfg["amber_s"])
        # fundo neutro: a caixa de tempos do estilo, ou o corpo se as linhas forem transparentes
        neutral = T.SKIN.get("value_box") or (tv.ROW_ALT if tv.ROW_ALT[3] >= 120 else T.TV_BODY)
        if g is None:
            txt, bg, fg = tv.gap_text(back, front, race), neutral, T.TEXT
        else:
            txt = f"{g:.3f}" if g < 10 else f"{g:.1f}"
            if g <= red:
                bg, fg = alpha(tv.RED_WASH, 255 if ctx.blink else 200), T.TEXT
            elif g <= amber:
                bg, fg = tv.AMBER, tv.INK
            else:
                bg, fg = neutral, T.TEXT
        py = y + 10
        if g is not None and g <= amber:
            T.neon_glow(c, x + 4, py, PILL_W - 8, 32, bg, 1.3)
        tv.slant(c, x + 4, py, PILL_W - 8, 32, bg, k=6)
        c.text(x + 4, py, PILL_W - 8, 32, txt, 15, fg, "c", 800)
        # ritmo: quanto o intervalo muda por volta (pelas últimas voltas de cada um)
        if front.last > 0 and back.last > 0:
            d = front.last - back.last          # >0: quem vem atrás é mais rápido, o gap fecha
            if abs(d) >= 0.05:
                if back.is_player:
                    col = T.GOOD if d > 0 else T.BAD
                elif front.is_player:
                    col = T.BAD if d > 0 else T.GOOD
                else:
                    col = T.DIM
                sign = "-" if d > 0 else "+"
                c.text(x, y + CARD_H + 2, PILL_W, 18, f"{sign}{abs(d):.2f}/{tr('tw.lap_short')}", 12, col, "c", 700)
