"""Standings: classificação multiclasse, agrupada por classe.

Colunas: posição, número, marca, piloto, SR, DR (quando o jogo dá), boxes, diferença,
última volta, média das últimas 5 voltas e melhor volta.
"""

from __future__ import annotations

from .. import theme as T
from .. import tv
from ..canvas import alpha
from ..i18n import tr
from . import compact as K
from .base import Overlay

ROW_H = 23
CLASS_H = 25
SEP_H = 10
NAME_W = 170


class StandingsOverlay(Overlay):
    key = "standings"
    defaults = {"player_class_rows": 10, "other_class_rows": 3, "show_other_classes": True,
                "player_class_first": False, "show_brand": True, "show_ratings": True, "show_avg5": True,
                "style": "compact", "columns": list(K.STD_DEFAULT)}
    default_pos = (20, 20)
    default_enabled = False   # a Timing Tower substitui-a por defeito

    def _layout(self, snap):
        if snap is None:
            return []
        by_class: dict[str, list] = {}
        for v in snap.vehicles:
            if v.in_garage and snap.session.kind != "race":
                continue
            by_class.setdefault(v.cls, []).append(v)
        mine = snap.me.cls
        classes = sorted(by_class, key=lambda k: (0 if (self.cfg["player_class_first"] and k == mine) else 1,
                                                  T.class_order(k), k))
        blocks = []
        for cls in classes:
            cars = sorted(by_class[cls], key=lambda v: v.class_place)
            if cls == mine:
                rows = self._window(cars, snap.me, int(self.cfg["player_class_rows"]))
            elif self.cfg["show_other_classes"]:
                rows = cars[: int(self.cfg["other_class_rows"])]
            else:
                continue
            if rows:
                blocks.append((cls, rows, len(cars)))
        return blocks

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

    def _cols(self, snap) -> list:
        """Colunas da direita (chave, largura), da esquerda para a direita."""
        cols = []
        if self.cfg.get("show_ratings", True) and snap is not None:
            if any(v.sr for v in snap.vehicles):
                cols.append(("sr", 46))
            if any(v.dr for v in snap.vehicles):
                cols.append(("dr", 46))
        cols += [("pit", 36), ("gap", 62), ("last", 66)]
        if self.cfg.get("show_avg5", True):
            cols.append(("avg", 66))
        cols.append(("best", 66))
        return cols

    def _left(self) -> float:
        return 88 + (40 if self.cfg.get("show_brand", True) else 0)

    def _compact(self) -> bool:
        return self.cfg.get("style", "compact") == "compact"

    def size(self, snap, ctx):
        if self._compact():
            cols = K.columns(self.cfg, K.STANDINGS_COLS, K.STD_DEFAULT, snap)
            blocks = self._layout(snap)
            h = 24 + sum(20 + sum(8 if r == "sep" else K.ROW for r in rows) + 3 for _c, rows, _n in blocks)
            return (K.width(cols), max(60, h + 2))
        w = int(self._left() + NAME_W + sum(cw for _k, cw in self._cols(snap)) + 12)
        blocks = self._layout(snap)
        if not blocks:
            return (w, 80)
        h = T.HEADER_H + 5
        for _cls, rows, _n in blocks:
            h += CLASS_H + sum(SEP_H if r == "sep" else ROW_H for r in rows) + 4
        return (w, h + 4)

    def render(self, c, snap, ctx, w, h):
        if self._compact():
            return self._render_compact(c, snap, ctx, w, h)
        s = snap.session
        sess = tr(f"session.{s.kind}")
        if s.max_laps:
            right = f"{sess} · {tr('lap_of', n=min(s.max_laps, snap.me.total_laps + 1), m=s.max_laps)}"
        else:
            right = f"{sess} · {T.clock(s.time_left)}"
        y = T.panel(c, w, h, self.title, right, part="bg")
        cols = self._cols(snap)
        xs, x = {}, w - 10 - sum(cw for _k, cw in cols)
        for k, cw in cols:
            xs[k] = (x, cw)
            x += cw
        heads = {"sr": "SR", "dr": "DR", "gap": tr("col.gap"), "last": tr("col.last"), "avg": tr("col.avg5"),
                 "best": tr("col.best")}
        c.mark_static()
        T.panel(c, w, h, self.title, right, part="right")
        race = s.kind == "race"
        first = True
        for cls, rows, n in self._layout(snap):
            short, ccol = T.class_info(cls)
            T.chip(c, 10, y + 4, 56, CLASS_H - 8, short, ccol, size=12, weight=800)
            c.text(72, y, 100, CLASS_H, tr("cars", n=n), 11, T.FAINT, "l", 500)
            if first:
                for k, (cx, cw) in xs.items():
                    if k in heads:
                        c.text(cx, y, cw - 4, CLASS_H, heads[k], 10, T.FAINT, "c" if k in ("sr", "dr") else "r", 700,
                               spacing=0.8)
                first = False
            y += CLASS_H
            cars = [r for r in rows if r != "sep"]
            leader = cars[0]
            class_best = min((v.best for v in snap.vehicles if v.cls == cls and v.best > 0), default=0)
            for i, r in enumerate(rows):
                if r == "sep":
                    for k in range(3):
                        c.ellipse(w / 2 - 8 + k * 8, y + SEP_H / 2, 1.4, 1.4, T.FAINT)
                    y += SEP_H
                    continue
                self._row(c, w, y, r, leader, class_best, race, i, ccol, xs, ctx)
                y += ROW_H
            y += 4

    def _row(self, c, w, y, v, leader, class_best, race, i, ccol, xs, ctx):
        me = v.is_player
        if me:
            T.me_row(c, 6, y, w - 12, ROW_H)
        elif i % 2:
            c.rect(6, y, w - 12, ROW_H, T.ROW_ALT, radius=3)
        dim = v.in_pits and not me
        main = T.FAINT if dim else T.TEXT
        T.pos_badge(c, 12, y + 3, 32, ROW_H - 6, str(v.class_place), ccol if not dim else alpha(ccol, 120), me=me)
        c.text(50, y, 34, ROW_H, f"#{v.number}" if v.number else "", 12, T.FAINT if dim else T.DIM, "l", 600)
        if self.cfg.get("show_brand", True):          # marca do carro (cor + código, sem logótipos)
            code = tv.brand_code(v.vehicle_name or v.team)
            if not tv.logo_plate(c, 86, y + 3, 36, ROW_H - 6, code, dim):
                bg, ink = tv.brand_colors(v.vehicle_name or v.team)
                if dim:
                    bg = alpha(bg, 110)
                c.rect(86, y + 4, 36, ROW_H - 8, bg, radius=3)
                c.text(86, y + 4, 36, ROW_H - 8, code, 10, ink, "c", 800)
        x0 = self._left()
        first_col = min(x for x, _w in xs.values())
        c.text(x0, y, first_col - x0 - 6, ROW_H, T.driver_label(v.driver), 13, main, "l", 700 if me else 600)

        for k in ("sr", "dr"):
            if k in xs:
                cx, cw = xs[k]
                tv.rating_chip(c, cx + 3, y + 4, cw - 8, ROW_H - 8, getattr(v, k), dim)
        px, pw = xs["pit"]
        if v.in_pits:
            T.chip(c, px, y + 4, pw - 2, ROW_H - 8, tr("pit"), T.PIT, size=10)
        elif v.pitstops:
            c.text(px, y, pw - 2, ROW_H, f"P{v.pitstops}", 11, T.FAINT, "c", 600)

        if v is leader:
            gap, gcol = tr("leader"), T.DIM
        elif race:
            laps = v.laps_behind_leader - leader.laps_behind_leader
            gap = tr("laps_behind", n=laps) if laps >= 1 else f"+{max(0.0, v.t_behind_leader - leader.t_behind_leader):.1f}"
            gcol = main
        else:
            gap = f"+{v.best - class_best:.3f}" if v.best > 0 and class_best > 0 else "—"
            gcol = main
        gx, gw = xs["gap"]
        c.text(gx, y, gw - 4, ROW_H, gap, 13, gcol, "r", 600)
        lx, lw = xs["last"]
        c.text(lx, y, lw - 4, ROW_H, T.laptime(v.last), 13, T.FAINT if dim else T.DIM, "r", 500)
        if "avg" in xs:
            ax, aw = xs["avg"]
            avg = (ctx.avg5 or {}).get(v.id, 0.0) if ctx is not None else 0.0
            c.text(ax, y, aw - 4, ROW_H, T.laptime(avg) if avg > 0 else "—", 13, T.FAINT if dim else T.TEXT, "r", 600)
        bx, bw = xs["best"]
        is_best = v.best > 0 and abs(v.best - class_best) < 1e-4
        c.text(bx, y, bw - 4, ROW_H, T.laptime(v.best), 13, T.BEST if is_best else (T.FAINT if dim else T.DIM),
               "r", 700 if is_best else 500)

    # ---- estilo compacto ------------------------------------------------- #
    def _render_compact(self, c, snap, ctx, w, h):
        s = snap.session
        cols = K.columns(self.cfg, K.STANDINGS_COLS, K.STD_DEFAULT, snap)
        X = K.xs(cols, w)
        left = f"{tr(f'session.{s.kind}')} {T.clock(s.time_left)}"
        if s.max_laps:
            left = f"{tr(f'session.{s.kind}')} · {tr('lap_of', n=min(s.max_laps, snap.me.total_laps + 1), m=s.max_laps)}"
        else:
            left += f"  ·  {tr('tw.lap')} {snap.me.total_laps + 1}"
        state = tr("cmp.wet", x=f"{s.wetness * 100:.0f}") if s.wetness > 0.05 else tr("cmp.dry")
        right = f"{s.air_temp:.0f}° · {state}" if s.air_temp else state
        c.rect(0, 0, w, h, (8, 9, 12, 150), radius=4)
        y = K.header_bar(c, w, left, right)
        c.mark_static()
        race = s.kind == "race"
        for cls, rows, n in self._layout(snap):
            short, ccol = T.class_info(cls)
            cars_all = [v for v in snap.vehicles if v.cls == cls]
            c.rect(0, y, w, 19, (14, 15, 20, 240), radius=2)
            c.rect(0, y + 17, w, 2, ccol)
            T.chip(c, 4, y + 2, 50, 14, short, ccol, size=10, weight=800)
            on_track = sum(1 for v in cars_all if not v.in_garage)
            info = f"{on_track}/{len(cars_all)}"
            sf = K.sof(cars_all)
            if sf > 0:
                info += f"   {tr('cmp.sof')} {sf / 1000:.1f}k"
            c.text(58, y, 140, 17, info, 10, T.DIM, "l", 700)
            K.col_heads(c, cols, {k: v for k, v in X.items() if k not in ("pos", "name")}, y, 17)
            y += 20
            cars = [r for r in rows if r != "sep"]
            ordered = sorted(cars_all, key=lambda v: v.class_place)
            leader = ordered[0] if ordered else None
            class_best = min((v.best for v in cars_all if v.best > 0), default=0)
            for i, r in enumerate(rows):
                if r == "sep":
                    for k in range(3):
                        c.ellipse(w / 2 - 8 + k * 8, y + 4, 1.4, 1.4, T.FAINT)
                    y += 8
                    continue
                idx = ordered.index(r) if r in ordered else 0
                ahead = ordered[idx - 1] if idx > 0 else None
                inf = {"class_best": class_best, "dim": r.in_pits and not r.is_player}
                inf["gap"] = self._gap_txt(r, leader, race, class_best)
                inf["interval"] = self._gap_txt(r, ahead, race, ahead.best if ahead else 0) if ahead else ""
                if r is leader:
                    inf["gap_col"] = T.DIM
                K.row(c, X, y, w, r, inf, ctx, i)
                y += K.ROW
            y += 3

    @staticmethod
    def _gap_txt(v, ref, race, ref_best) -> str:
        if ref is None or v is ref:
            return tr("leader") if ref is v else ""
        if race:
            laps = v.laps_behind_leader - ref.laps_behind_leader
            if laps >= 1 and v.t_behind_leader - ref.t_behind_leader > 0:
                return tr("laps_behind", n=laps)
            return f"+{max(0.0, v.t_behind_leader - ref.t_behind_leader):.1f}"
        if v.best > 0 and ref_best > 0:
            return f"+{v.best - ref_best:.3f}"
        return "—"
