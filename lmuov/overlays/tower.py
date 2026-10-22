"""Timing Tower: classificação estilo transmissão de TV.

Ecrãs que alternam sozinhos, como na WEC: intervalo, gap ao líder, nome do piloto, nome da
equipa e top 8 de cada classe (em treino/quali: melhores voltas da tua classe). Placas na cor
da marca, tempo de volta acabado de fazer em dourado (roxo = melhor da classe, verde = melhor
pessoal) e linha amarela a pulsar para carros parados.

O estilo "WEC 2025" tem um desenho próprio (_render_wec25); os outros estilos usam o desenho base.
"""

from __future__ import annotations

from .. import theme as T
from .. import tv
from ..canvas import alpha
from ..i18n import tr
from .base import Overlay

ROW_H, GAP, BAND_H = 26, 2, 20
FIELDS = ("interval", "gap", "last", "best", "avg5", "rating", "pits", "name", "team", "top")
CLASS_ONLY = ("gap", "name", "team")        # ecrãs só com a tua classe
NO_VALUE = ("name", "team")                 # ecrãs sem coluna de tempos (nome largo)
CLASS_LONG = {"HYP": "HYPERCAR", "GT3": "LMGT3", "GTE": "LMGTE"}

# medidas do estilo WEC 2025
W25, ROW25, HEAD25, CBAR25, FOOT25, SEP25 = 252, 22, 84, 20, 22, 9


def class_long(raw: str) -> str:
    short = T.class_info(raw)[0]
    return CLASS_LONG.get(short, short)


class TowerOverlay(Overlay):
    key = "tower"
    defaults = {"fields": ["interval", "gap", "avg5", "rating", "name", "team", "top"], "fields_v": 2, "quali_fields": ["best", "gap", "name"],
                "cycle_s": 8.0, "player_class_rows": 10, "other_class_rows": 3, "show_other_classes": True,
                "top_n": 8, "lap_flash_s": 10.0, "slow_kmh": 60, "show_s": 12.0, "title": "", "footer": ""}
    default_pos = (20, 20)
    smart_capable = True
    default_mode = "auto"
    W = 330

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self._laps: dict[int, int] = {}
        self._flash: dict[int, float] = {}     # id -> instante em que acabou a volta
        if int(self.cfg.get("fields_v", 1)) < 2:   # versões antigas: junta média de 5 voltas e SR/DR à rotação
            f = list(self.cfg.get("fields") or [])
            for k in ("avg5", "rating"):
                if k not in f:
                    f.insert(min(2, len(f)), k)
            self.cfg["fields"] = f
            self.cfg["fields_v"] = 2

    # ------------------------------------------------------------------ #
    def observe(self, snap, now: float) -> None:
        """Deteta voltas acabadas (para o tempo a dourado). Chamado a cada atualização."""
        if snap is None:
            return
        for v in snap.vehicles:
            prev = self._laps.get(v.id)
            if prev is not None and v.total_laps == prev + 1 and v.last > 0:
                self._flash[v.id] = now
            self._laps[v.id] = v.total_laps

    def field(self, ctx, snap=None) -> str:
        race = snap is None or snap.session.kind == "race"
        if ctx.focus_field:                       # escolhido por botão
            return FIELDS[(ctx.focus_field - 1) % len(FIELDS)]
        lst = self.cfg["fields"] if race else self.cfg.get("quali_fields", ["best"])
        fields = [f for f in lst if f in FIELDS] or ["interval" if race else "best"]
        if snap is not None and not any(v.sr or v.dr for v in snap.vehicles):
            fields = [f for f in fields if f != "rating"] or fields     # o jogo não dá ratings: salta o ecrã
        period = max(2.0, float(self.cfg["cycle_s"]))
        return fields[int(ctx.now / period) % len(fields)]

    @staticmethod
    def wec25() -> bool:
        return T.SKIN.get("tower") == "wec25"

    def expanded(self, snap, ctx) -> bool:
        """Modo auto: torre completa só em momentos que interessam; no resto, mini-torre."""
        if self.mode() != "auto" or ctx.peek or ctx.edit_mode:
            return True
        show = float(self.cfg["show_s"])
        return (ctx.since("lap") < show or ctx.since("pos") < 8 or ctx.since("start") < 20
                or ctx.since("tower_req") < show
                or snap.session.phase in (6, 7, 8) or snap.me.in_pits)

    def _blocks(self, snap, ctx=None, fld=None):
        """[(classe, carros da classe, linhas a mostrar)] para o ecrã atual."""
        if ctx is not None and not self.expanded(snap, ctx):
            cars = sorted((v for v in snap.vehicles if v.cls == snap.me.cls), key=lambda v: v.class_place)
            i = cars.index(snap.me) if snap.me in cars else 0
            return [(snap.me.cls, cars, cars[max(0, i - 1): i + 2])]
        if fld is None:
            fld = self.field(ctx, snap) if ctx is not None else "interval"
        race = snap.session.kind == "race"
        class_only = fld in CLASS_ONLY or (self.wec25() and not race)
        top_n = max(1, int(self.cfg.get("top_n", 8)))
        by_class: dict[str, list] = {}
        for v in snap.vehicles:
            if v.in_garage and not race:
                continue
            by_class.setdefault(v.cls, []).append(v)
        out = []
        for cls in sorted(by_class, key=lambda k: (T.class_order(k), k)):
            cars = sorted(by_class[cls], key=lambda v: v.class_place)
            if cls == snap.me.cls:
                rows = self._window(cars, snap.me, top_n if fld == "top" else int(self.cfg["player_class_rows"]))
            elif class_only:
                continue
            elif fld == "top":
                rows = cars[:top_n]
            elif self.cfg["show_other_classes"]:
                rows = cars[: int(self.cfg["other_class_rows"])]
            else:
                continue
            if rows:
                out.append((cls, cars, rows))
        return out

    @staticmethod
    def _window(cars, me, n):
        if len(cars) <= n:
            return cars
        top = 3 if n >= 6 else 1
        idx = cars.index(me) if me in cars else 0
        if idx < n - 1:
            return cars[:n]
        rest = n - top
        start = max(top, min(idx - rest // 2, len(cars) - rest))
        return cars[:top] + ["sep"] + cars[start:start + rest]

    def size(self, snap, ctx):
        if self.wec25():
            return self._size_wec25(snap, ctx)
        if snap is None:
            return (self.W, 80)
        h = 35 + 20
        for _cls, _cars, rows in self._blocks(snap, ctx, self.field(ctx, snap)):
            h += BAND_H + GAP + sum(10 if r == "sep" else ROW_H + GAP for r in rows) + 4
        return (self.W, h)

    # ------------------------------------------------------------------ #
    def render(self, c, snap, ctx, w, h):
        if self.wec25():
            self._render_wec25(c, snap, ctx, w, h)
            return
        T.neon_frame(c, 0, 0, w, h, T.ACCENT, 0.8)
        if T.SKIN.get("header") not in ("tv", "carbon"):
            T.body(c, 0, 0, w, h)
        c.mark_static()
        self.observe(snap, ctx.now)
        s, me = snap.session, snap.me
        race = s.kind == "race"
        lap_txt = (tr("lap_of", n=min(s.max_laps, me.total_laps + 1), m=s.max_laps) if s.max_laps
                   else f"{tr('tw.lap')} {max(v.total_laps for v in snap.vehicles) + 1}")
        y = tv.header(c, w, tr(f"session.{s.kind}").upper(), lap_txt.upper() if race else s.track.upper(),
                      T.clock(s.time_left))
        fld = self.field(ctx, snap)
        # faixa com o nome do campo que está a aparecer
        tv.row_bg(c, 0, y, w, 20)
        c.text(10, y, 60, 20, tr("tw.pos"), 10, T.FAINT, "l", 700, spacing=1)
        c.text(w - 150, y, 140, 20, tr(f"tw.f.{fld}"), 10, T.ACCENT, "r", 800, spacing=1.2)
        y += 20 + GAP

        for cls, cars, rows in self._blocks(snap, ctx, fld):
            short, ccol = T.class_info(cls)
            tv.class_band(c, 0, y, w, BAND_H, short, ccol, tr("cars", n=len(cars)))
            y += BAND_H + GAP
            class_best = min((v.best for v in cars if v.best > 0), default=0.0)
            prev = None
            for r in rows:
                if r == "sep":
                    c.text(0, y - 3, w, 13, "· · ·", 11, T.FAINT, "c", 700)
                    y += 10
                    prev = None
                    continue
                ahead = prev if prev is not None else (cars[cars.index(r) - 1] if cars.index(r) > 0 else None)
                self._row(c, w, y, r, cars[0], ahead, class_best, race, fld, ctx, ccol)
                prev = r
                y += ROW_H + GAP
            y += 4

    def _row(self, c, w, y, v, leader, ahead, class_best, race, fld, ctx, ccol):
        focus = v.is_player
        slow = (not v.in_pits and v.speed < float(self.cfg["slow_kmh"]) / 3.6 and v.total_laps > 0
                and v.finish_status == 0)
        if slow and not focus:
            c.rect(0, y, w, ROW_H, alpha(tv.SLOW, 150 if ctx.blink else 70), radius=T.SKIN.get("radius", 0))
        else:
            tv.row_bg(c, 0, y, w, ROW_H, focus, alt=v.class_place % 2 == 0)
        ink = tv.FOCUS_INK if focus else (T.FAINT if v.in_pits else T.TEXT)

        tv.pos_box(c, 6, y + 3, 30, ROW_H - 6, str(v.class_place), focus)
        c.rect(40, y + 3, 3, ROW_H - 6, ccol)
        tv.plate(c, 48, y + 4, 34, ROW_H - 8, tv.brand_code(v.vehicle_name), focus)
        c.text(86, y, 34, ROW_H, v.number, 13, tv.FOCUS_INK if focus else ccol, "l", 800)
        name_w = w - 120 - (10 if fld in NO_VALUE and not v.in_pits else 84)
        if fld == "team":
            label = tv.team_short(c, tv.vehicle_team(v), name_w, 14, 800, 0.3)
        elif fld == "name":
            label = T.driver_label(v.driver)
        else:
            label = tv.surname(v.driver)
        c.text(118, y, name_w, ROW_H, label, 15 if fld != "team" else 14, ink, "l", 800, spacing=0.3)
        if v.fuel_frac >= 0:
            fw = name_w - 6
            c.rect(118, y + ROW_H - 4, fw, 2, (255, 255, 255, 30) if not focus else (0, 0, 0, 40))
            c.rect(118, y + ROW_H - 4, fw * max(0.0, min(1.0, v.fuel_frac)), 2, tv.energy_color(v.fuel_frac))

        vx, vw = w - 80, 72
        if v.in_pits:
            tv.slant(c, vx + 18, y + 5, 54, ROW_H - 10, (236, 238, 242, 255) if not focus else tv.INK, k=4)
            c.text(vx + 18, y + 5, 54, ROW_H - 10, tr("pit"), 11, tv.INK if not focus else T.TEXT, "c", 800)
            return
        if fld in NO_VALUE:
            return
        if slow and not focus:
            c.text(vx, y, vw, ROW_H, tr("tw.slow"), 12, tv.INK, "r", 800, spacing=0.8)
            return

        # volta acabada há pouco: tempo a dourado / roxo / verde, a desvanecer
        t0 = self._flash.get(v.id)
        flash_s = float(self.cfg["lap_flash_s"])
        if t0 is not None and 0 <= ctx.now - t0 < flash_s and v.last > 0:
            if abs(v.last - class_best) < 1e-4:
                col = tv.PURPLE
            elif abs(v.last - v.best) < 1e-4:
                col = tv.GREEN
            else:
                col = tv.GOLD
            fade = min(1.0, (flash_s - (ctx.now - t0)) / 2.0)
            c.text(vx, y, vw, ROW_H, T.laptime(v.last), 14, alpha(col, int(255 * fade)), "r", 800)
            return

        txt, col = "", ink
        if fld in ("interval", "top"):
            txt = tr("leader") if ahead is None else tv.gap_text(v, ahead, race)
        elif fld == "gap":
            txt = tr("leader") if v is leader else tv.gap_text(v, leader, race)
        elif fld == "last":
            txt = T.laptime(v.last)
            if v.last > 0 and abs(v.last - class_best) < 1e-4:
                col = tv.PURPLE
            elif v.last > 0 and abs(v.last - v.best) < 1e-4 and not focus:
                col = tv.GREEN
        elif fld == "best":
            txt = T.laptime(v.best)
            if v.best > 0 and abs(v.best - class_best) < 1e-4:
                col = tv.PURPLE
        elif fld == "pits":
            txt = f"{v.pitstops}"
        elif fld == "avg5":
            a = (ctx.avg5 or {}).get(v.id, 0.0)
            txt = T.laptime(a) if a > 0 else "—"
        elif fld == "rating":
            tv.rating_chip(c, vx + 2, y + 5, 34, ROW_H - 10, v.sr)
            tv.rating_chip(c, vx + 38, y + 5, 34, ROW_H - 10, v.dr)
            return
        if txt == tr("leader"):
            col = T.FAINT if not focus else tv.FOCUS_INK
        c.text(vx, y, vw, ROW_H, txt, 14, col, "r", 800)

    # ================================================================== #
    # Estilo WEC 2025: torre azul-escura, emblema + relógio, faixa vermelha,
    # placas na cor da marca, código de 3 letras e tempos em caixas cinzentas.
    # ================================================================== #
    def _bars(self, blocks, fld, race, mini):
        """Texto e cor da faixa de cima + que blocos levam faixa de classe."""
        class_view = mini or fld in CLASS_ONLY or fld == "top" or not race
        if class_view and blocks:
            cls0 = blocks[0][0]
            top = (class_long(cls0), T.class_info(cls0)[1])
            per_block = [False] + [True] * (len(blocks) - 1)
        else:
            top = None
            per_block = [len(blocks) > 1] * len(blocks)
        return class_view, top, per_block

    def _size_wec25(self, snap, ctx):
        if snap is None:
            return (W25, HEAD25 + 3 * ROW25 + FOOT25)
        mini = not self.expanded(snap, ctx)
        fld = self.field(ctx, snap)
        blocks = self._blocks(snap, ctx, fld)
        _cv, _top, per_block = self._bars(blocks, fld, snap.session.kind == "race", mini)
        h = HEAD25
        for (_cls, _cars, rows), bar in zip(blocks, per_block):
            h += (CBAR25 + 2 if bar else 0) + sum(SEP25 if r == "sep" else ROW25 for r in rows)
        return (W25, h + 6 + FOOT25)

    def _flag_color(self, snap, ctx):
        s = snap.session
        if s.phase == 7:
            return (235, 40, 50, 255)
        if s.phase == 6 or any(s.sector_flags):
            return (255, 206, 0, 255)
        if ctx.now < ctx.green_until:
            return (40, 222, 110, 255)
        return None

    def _render_wec25(self, c, snap, ctx, w, h):
        acc, acc2 = T.ACCENT, T.SKIN.get("accent2") or T.ACCENT
        self.observe(snap, ctx.now)
        s, me = snap.session, snap.me
        race = s.kind == "race"
        mini = not self.expanded(snap, ctx)
        fld = self.field(ctx, snap)
        blocks = self._blocks(snap, ctx, fld)
        class_view, top, per_block = self._bars(blocks, fld, race, mini)

        # corpo: azul-escuro com contorno azul claro
        T.neon_frame(c, 0, 0, w, h, acc, 0.55)
        c.rect(0, 0, w, h, T.TV_BODY, radius=7, fill2=T.SKIN.get("body2"))
        c.rect(0, 0, w, h, None, radius=7, stroke=alpha(T.lighten(acc, 0.3), 150), stroke_w=1.4)
        c.rect(3, 3, w - 6, 40, (255, 255, 255, 7), radius=5)
        c.mark_static()

        # emblema (muda de cor com a bandeira) + relógio
        fcol = self._flag_color(snap, ctx)
        title = str(self.cfg.get("title") or "")
        if title in ("", "LMU"):            # automático: o do estilo, senão o do simulador
            title = T.SKIN.get("emblem") or ("iRACING" if snap.source == "iracing" else "LMU")
        title = title if title == "iRACING" else title.upper()
        c.text(0, 3, w, 30, title, 26, fcol or (255, 255, 255, 255), "c", 800, spacing=1.5, italic=True)
        tw = min(w - 40, c.measure(title, 26, 800, 1.5) + 18)
        sx = (w - tw) / 2
        swo = fcol or acc
        c.polygon([(sx + 6, 33), (sx + tw, 33), (sx + tw - 4, 36), (sx + 2, 36)], swo)
        T.neon_line(c, sx + 8, 34.5, sx + tw - 4, 34.5, swo, 1.0)
        if s.phase == 8:                                     # bandeira de xadrez por baixo do emblema
            for i in range(int(tw // 6)):
                c.rect(sx + 3 + i * 6, 33 + (i % 2) * 1.5, 3, 1.5, (255, 255, 255, 255))
        if s.max_laps:
            clk = tr("lap_of", n=min(s.max_laps, me.total_laps + 1), m=s.max_laps).upper()
        else:
            t = s.time_left
            clk = "--:--:--" if t is None else "{:02d}:{:02d}:{:02d}".format(int(t) // 3600, int(t) % 3600 // 60, int(t) % 60)
        c.text(0, 38, w, 18, clk, 14, (255, 255, 255, 255), "c", 700, spacing=1.0)

        # faixa de cima: sessão (vermelho) ou classe (cor da classe)
        x0, x1 = 7.0, w - 7.0
        if top is not None:
            T.wec_bar(c, x0, 58, x1 - x0, 21, top[0], top[1], 12.5)
        else:
            T.wec_bar(c, x0, 58, x1 - x0, 21, tr(f"session.{s.kind}").upper(), None, 12.5)
        y = HEAD25

        for (cls, cars, rows), bar in zip(blocks, per_block):
            short, ccol = T.class_info(cls)
            if bar:
                T.wec_bar(c, x0 + 14, y + 1, x1 - x0 - 28, CBAR25 - 2, class_long(cls), ccol, 11)
                y += CBAR25 + 2
            class_best = min((v.best for v in cars if v.best > 0), default=0.0)
            prev = None
            for r in rows:
                if r == "sep":
                    for k in range(3):
                        c.ellipse(w / 2 - 8 + k * 8, y + SEP25 / 2, 1.4, 1.4, T.FAINT)
                    y += SEP25
                    prev = None
                    continue
                i = cars.index(r)
                ahead = prev if prev is not None else (cars[i - 1] if i > 0 else None)
                self._row25(c, x0, x1, y, r, cars[0], ahead, class_best, race, fld, ctx)
                prev = r
                y += ROW25

        # rodapé: nome do circuito + risca em gradiente
        fy = h - FOOT25
        c.rect(0, fy, w, FOOT25, (0, 0, 0, 70), radius=6)
        c.rect(0, fy, w, 6, (0, 0, 0, 70))
        foot = str(self.cfg.get("footer") or s.track or "").upper()
        c.text(10, fy, w - 20, FOOT25 - 3, foot, 9.5, (226, 232, 255, 255), "c", 700, spacing=1.2, italic=True)
        c.rect(14, h - 3.5, w - 28, 2, acc, fill2=acc2, horizontal=True)

    def _row25(self, c, x0, x1, y, v, leader, ahead, class_best, race, fld, ctx):
        focus = v.is_player
        slow = (not v.in_pits and v.speed < float(self.cfg["slow_kmh"]) / 3.6 and v.total_laps > 0
                and v.finish_status == 0)
        rw = x1 - x0
        if focus:
            T.neon_glow(c, x0, y + 1, rw, ROW25 - 2, tv.FOCUS_BG, 0.8)
            c.rect(x0, y + 1, rw, ROW25 - 2, tv.FOCUS_BG, radius=3, fill2=T.scale_rgb(tv.FOCUS_BG, 0.8),
                   horizontal=True)
        elif slow:
            c.rect(x0, y + 1, rw, ROW25 - 2, alpha(tv.SLOW, 120 if ctx.blink else 50), radius=3)
        else:
            c.rect(x0 + 4, y + ROW25 - 0.5, rw - 8, 1, (255, 255, 255, 13))
        white = (255, 255, 255, 255)
        ink = white if (focus or not v.in_pits) else (190, 198, 232, 255)
        c.text(x0, y, 21, ROW25, str(v.class_place), 13, ink, "r", 800)
        tv.plate(c, x0 + 26, y + 4, 26, ROW25 - 8, tv.brand_code(v.vehicle_name), focus)
        c.text(x0 + 56, y, 30, ROW25, v.number, 12.5, ink, "l", 800)

        bx, bw = x1 - 70, 68                     # caixa dos tempos
        if fld in NO_VALUE:
            avail = x1 - (x0 + 88) - (40 if v.in_pits else 6)
            if fld == "team":
                label = tv.team_short(c, tv.vehicle_team(v), avail, 12.5, 800, 0.4)
            else:
                label = tv.surname(v.driver)
            c.text(x0 + 88, y, avail, ROW25, label, 12.5, ink, "l", 800, spacing=0.4)
            if v.in_pits:
                self._box(c, x1 - 36, y, 34, tr("pit"), (255, 255, 255, 255), (14, 20, 70, 255))
            return
        c.text(x0 + 88, y, bx - x0 - 92, ROW25, tv.driver_code(v.driver), 13, ink, "l", 800, spacing=0.6)

        box = T.SKIN.get("value_box", (76, 82, 130, 240))
        if focus:
            box = (255, 255, 255, 60)
        if v.in_pits:
            self._box(c, bx, y, bw, tr("pit"), (255, 255, 255, 255), (14, 20, 70, 255), "c")
            return
        if slow and not focus:
            self._box(c, bx, y, bw, tr("tw.slow"), tv.SLOW, (20, 16, 0, 255), "c")
            return
        t0 = self._flash.get(v.id)
        flash_s = float(self.cfg["lap_flash_s"])
        if t0 is not None and 0 <= ctx.now - t0 < flash_s and v.last > 0:
            if abs(v.last - class_best) < 1e-4:
                self._box(c, bx, y, bw, T.laptime(v.last), tv.PURPLE, white)
            elif abs(v.last - v.best) < 1e-4:
                self._box(c, bx, y, bw, T.laptime(v.last), tv.GREEN, (6, 30, 14, 255))
            else:
                self._box(c, bx, y, bw, T.laptime(v.last), box, white if focus else tv.GOLD)
            return

        size, txt, fill = 12.0, "", box
        if fld in ("interval", "top"):
            if ahead is None:
                txt, size = tr("tw.f.interval"), 9.5
            else:
                txt = tv.gap_text(v, ahead, race)
        elif fld == "gap":
            if v is leader:
                txt, size = (tr("leader").upper(), 9.5) if race else (T.laptime(v.best), 12.0)
            else:
                txt = tv.gap_text(v, leader, race)
        elif fld == "last":
            txt = T.laptime(v.last)
            if v.last > 0 and abs(v.last - class_best) < 1e-4:
                fill = tv.PURPLE
        elif fld == "best":
            txt = T.laptime(v.best)
            if v.best > 0 and abs(v.best - class_best) < 1e-4:
                fill = tv.PURPLE
        elif fld == "pits":
            txt = str(v.pitstops)
        elif fld == "avg5":
            a = (ctx.avg5 or {}).get(v.id, 0.0)
            txt = T.laptime(a) if a > 0 else "—"
        elif fld == "rating":
            tv.rating_chip(c, bx, y + 3, bw / 2 - 1, ROW25 - 6, v.sr)
            tv.rating_chip(c, bx + bw / 2 + 1, y + 3, bw / 2 - 1, ROW25 - 6, v.dr)
            return
        self._box(c, bx, y, bw, txt, fill, white, size=size)

    @staticmethod
    def _box(c, x, y, w, text, fill, ink, align="r", size=12.0):
        c.rect(x, y + 3, w, ROW25 - 6, fill, radius=3)
        if align == "c":
            c.text(x, y + 3, w, ROW25 - 6, text, size, ink, "c", 800, spacing=0.4)
        else:
            c.text(x + 4, y + 3, w - 9, ROW25 - 6, text, size, ink, "r", 700 if size >= 12 else 800,
                   spacing=0.2 if size >= 12 else 0.6)
