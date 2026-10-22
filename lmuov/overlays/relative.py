"""Relative: os carros mais próximos em pista, à frente e atrás, estilo TV.

Modo automático: só aparece quando há alguém a menos de `near_s` segundos, com bandeira
azul, ou logo a seguir a saíres das boxes.
"""

from __future__ import annotations

from .. import theme as T
from .. import tv
from ..canvas import alpha
from ..i18n import tr
from ..relcalc import relatives
from . import compact as K
from .base import Overlay

ROW_H, GAP = 26, 2
LAPPING_ME = (255, 120, 112, 255)    # está voltas à minha frente (deixa passar)
LAPPED_BY_ME = (110, 172, 255, 255)  # estou a dar-lhe volta


class RelativeOverlay(Overlay):
    key = "relative"
    defaults = {"rows_ahead": 3, "rows_behind": 3, "show_last_lap": True, "show_pit_cars": True, "near_s": 1.2,
                "show_ratings": True, "style": "compact", "columns": list(K.REL_DEFAULT)}
    default_pos = (20, 790)
    smart_capable = True
    default_mode = "auto"

    def _compact(self) -> bool:
        return self.cfg.get("style", "compact") == "compact"

    def size(self, snap, ctx):
        rows = int(self.cfg["rows_ahead"]) + int(self.cfg["rows_behind"]) + 1
        if self._compact():
            return (K.width(K.columns(self.cfg, K.RELATIVE_COLS, K.REL_DEFAULT, snap)), 24 + rows * K.ROW + 2)
        return (400 + 46 * len(self._ratings(snap)), T.HEADER_H + 4 + rows * (ROW_H + GAP))

    def _ratings(self, snap) -> list:
        """Que colunas de rating mostrar (só as que o jogo dá)."""
        if not self.cfg.get("show_ratings", True) or snap is None:
            return []
        return [k for k in ("sr", "dr") if any(getattr(v, k) for v in snap.vehicles)]

    def auto_visible(self, snap, ctx):
        if snap.me.flag == 6 or ctx.since("pit_exit") < 10:
            return True
        near = float(self.cfg["near_s"])
        return any(abs(r.gap) <= near for r in relatives(snap, include_pits=False))

    def render(self, c, snap, ctx, w, h):
        na, nb = int(self.cfg["rows_ahead"]), int(self.cfg["rows_behind"])
        rels = relatives(snap, include_pits=self.cfg["show_pit_cars"])
        ahead = sorted((r for r in rels if r.dist > 0), key=lambda r: r.dist)[:na]
        behind = sorted((r for r in rels if r.dist <= 0), key=lambda r: -r.dist)[:nb]
        rows = [None] * (na - len(ahead)) + list(reversed(ahead)) + ["me"] + behind + [None] * (nb - len(behind))
        s = snap.session
        if self._compact():
            return self._render_compact(c, snap, ctx, w, h, rows)
        right = tr("left", t=T.clock(s.time_left)) if s.time_left is not None else tr(f"session.{s.kind}")
        T.neon_frame(c, 0, 0, w, h, T.ACCENT, 0.8)
        if T.SKIN.get("header") not in ("tv", "carbon"):
            T.body(c, 0, 0, w, h)
        T.tv_header(c, w, self.title, right, part="bg")
        c.mark_static()
        T.tv_header(c, w, self.title, right, part="right")
        y = T.HEADER_H + 2
        self._rk = self._ratings(snap)
        for r in rows:
            if r is None:
                tv.row_bg(c, 0, y, w, ROW_H, alt=True)
            elif r == "me":
                self._row(c, w, y, snap.me, 0.0, 0)
            else:
                self._row(c, w, y, r.v, r.gap, r.lap_diff)
            y += ROW_H + GAP

    def _row(self, c, w, y, v, gap, lap_diff):
        focus = v.is_player
        dim = v.in_pits and not focus
        _short, ccol = T.class_info(v.cls)
        tv.row_bg(c, 0, y, w, ROW_H, focus)
        tv.pos_box(c, 6, y + 3, 30, ROW_H - 6, str(v.class_place), focus)
        c.rect(40, y + 3, 3, ROW_H - 6, ccol)
        tv.plate(c, 48, y + 4, 34, ROW_H - 8, tv.brand_code(v.vehicle_name), focus)
        c.text(86, y, 34, ROW_H, v.number, 13, tv.FOCUS_INK if focus else ccol, "l", 800)

        if focus:
            name_col = tv.FOCUS_INK
        elif dim:
            name_col = T.FAINT
        elif lap_diff > 0:
            name_col = LAPPING_ME
        elif lap_diff < 0:
            name_col = LAPPED_BY_ME
        else:
            name_col = T.TEXT
        right_w = 148 if self.cfg["show_last_lap"] else 70
        rk = getattr(self, "_rk", [])
        rx = w - right_w - 4 - 46 * len(rk)
        for j, k in enumerate(rk):                      # SR / DR
            tv.rating_chip(c, rx + j * 46 + 2, y + 5, 42, ROW_H - 10, getattr(v, k), dim)
        c.text(118, y, rx - 118 - 4, ROW_H, tv.surname(v.driver), 15, name_col, "l", 800, spacing=0.3)

        if self.cfg["show_last_lap"]:
            if v.in_pits:
                tv.slant(c, w - 136, y + 5, 46, ROW_H - 10, (236, 238, 242, 255), k=4)
                c.text(w - 136, y + 5, 46, ROW_H - 10, tr("pit"), 11, tv.INK, "c", 800)
            else:
                c.text(w - 150, y, 70, ROW_H, T.laptime(v.last), 12,
                       alpha(tv.FOCUS_INK, 160) if focus else (T.FAINT if dim else T.DIM), "r", 600)
        if focus:
            c.rect(w - 34, y + ROW_H / 2 - 1.5, 22, 3, tv.FOCUS_INK)
        else:
            g = abs(gap)
            txt = f"{g:.1f}" if g < 99.95 else f"{g:.0f}"
            box = T.SKIN.get("value_box")
            if box:                                     # estilo WEC 2025: tempo numa caixa
                c.rect(w - 62, y + 4, 54, ROW_H - 8, box, radius=3)
                c.text(w - 62, y, 47, ROW_H, txt, 14, T.FAINT if dim else T.TEXT, "r", 800)
            else:
                c.text(w - 74, y, 64, ROW_H, txt, 15, T.FAINT if dim else T.TEXT, "r", 800)

    # ---- estilo compacto ------------------------------------------------- #
    def _render_compact(self, c, snap, ctx, w, h, rows):
        s = snap.session
        cols = K.columns(self.cfg, K.RELATIVE_COLS, K.REL_DEFAULT, snap)
        X = K.xs(cols, w)
        me = snap.me
        left = f"{tr('tw.lap')} {me.total_laps + 1}"
        if me.sr or me.dr:
            left += "   " + " · ".join(x for x in (me.sr, me.dr) if x)
        right = T.clock(s.time_left) if s.time_left is not None else tr(f"session.{s.kind}")
        c.rect(0, 0, w, h, (8, 9, 12, 150), radius=4)
        y = K.header_bar(c, w, left, right)
        c.mark_static()
        for i, r in enumerate(rows):
            if r is None:
                c.rect(0, y, w, K.ROW - 1, (22, 24, 30, 120), radius=2)
                y += K.ROW
                continue
            if r == "me":
                v, gap, lap_diff, ahead = me, 0.0, 0, None
            else:
                v, gap, lap_diff, ahead = r.v, r.gap, r.lap_diff, r.dist > 0
            dim = v.in_pits and not v.is_player
            name_col = (T.FAINT if dim else LAPPING_ME if lap_diff > 0 else LAPPED_BY_ME if lap_diff < 0
                        else T.TEXT)
            g = abs(gap)
            txt = "" if ahead is None else (("+" if ahead else "-") + (f"{g:.1f}" if g < 99.95 else f"{g:.0f}"))
            K.row(c, X, y, w, v, {"gap": txt, "name_col": name_col, "dim": dim}, ctx, i)
            y += K.ROW
