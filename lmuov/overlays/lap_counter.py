"""Lap Counter: volta atual, total (ou estimativa das voltas que faltam numa corrida por tempo)."""

from __future__ import annotations

from .. import theme as T
from ..i18n import tr
from .base import Overlay


GAIN = (40, 214, 118, 255)
LOSS = (255, 168, 0, 255)
DELTA_RED = (226, 28, 48, 255)
DELTA_GREEN = (22, 178, 92, 255)

# design -> tamanho
SIZES = {"classic": (230, 78), "board": (220, 214), "strip": (520, 74), "tv": (300, 152), "minimal": (250, 96)}


def sector_bar(c, x, y, w, h, snap, ctx, labels=True):
    """S1 S2 S3: verde = ganhaste tempo nesse setor, laranja = perdeste, claro = onde estás agora."""
    cur = snap.me.sector if 0 <= snap.me.sector < 3 else 0
    sd = getattr(ctx, "sec_delta", [None] * 3)
    sw = (w - 4) / 3
    for k in range(3):
        sx = x + k * (sw + 2)
        v = sd[k] if k < cur else None
        if k < cur and v is not None:
            col = GAIN if v <= 0 else LOSS
        elif k == cur:
            col = (210, 214, 222, 255) if ctx.blink or True else (150, 154, 162, 255)
        else:
            col = (255, 255, 255, 30)
        c.rect(sx, y, sw, h, col, radius=2)
        if labels:
            ink = T.on_color(col) if col[3] > 200 else T.DIM
            txt = f"S{k + 1}"
            if k < cur and v is not None:
                txt += f"  {v:+.2f}"
            c.text(sx, y, sw, h, txt, max(8.0, h * 0.62), ink, "c", 800)


def delta_box(c, x, y, w, h, d, size):
    if d.invalid:
        c.rect(x, y, w, h, (60, 60, 66, 255), radius=3)
        c.text(x, y, w, h, tr("delta.invalid"), size * 0.6, T.TEXT, "c", 800)
        return
    if not d.has_ref:
        c.rect(x, y, w, h, (255, 255, 255, 18), radius=3)
        c.text(x, y, w, h, "±-.---", size, T.FAINT, "c", 800)
        return
    v = d.delta
    col = DELTA_GREEN if v < 0 else DELTA_RED
    c.rect(x, y, w, h, col, radius=3, fill2=T.scale_rgb(col, 0.8))
    for k in range(4):                                   # riscas diagonais, como no exemplo
        sx = x + w * 0.70 + k * 12
        if sx + 8 + h * 0.5 > x + w - 2:
            break
        c.polygon([(sx, y + h), (sx + 8, y + h), (sx + 8 + h * 0.5, y), (sx + h * 0.5, y)], (255, 255, 255, 22))
    c.text(x, y, w, h, f"{v:+.3f}" if abs(v) < 10 else f"{v:+.1f}", size, (255, 255, 255, 255), "c", 800)


class LapCounterOverlay(Overlay):
    key = "lap_counter"
    defaults = {"design": "board"}      # classic, board, strip, tv, minimal
    default_pos = (1360, 168)

    def size(self, snap, ctx):
        return SIZES.get(str(self.cfg.get("design", "board")), SIZES["board"])

    def _lap(self, snap) -> str:
        s, me = snap.session, snap.me
        lap = me.total_laps + 1
        if s.max_laps:
            return f"{min(lap, s.max_laps)}/{s.max_laps}"
        return str(lap)

    def render(self, c, snap, ctx, w, h):
        d = str(self.cfg.get("design", "board"))
        if d != "classic":
            return getattr(self, f"_d_{d}", self._d_board)(c, snap, ctx, w, h)
        return self._classic(c, snap, ctx, w, h)

    # ---- quadro (como o exemplo): Lap / Last / Best / Current + setores + delta ----------- #
    def _d_board(self, c, snap, ctx, w, h):
        d = ctx.delta
        c.rect(0, 0, w, h, (70, 78, 90, 215), radius=6)
        rows = ((tr("lc.lap"), self._lap(snap), T.TEXT), (tr("lc.last"), T.laptime(d.last), T.TEXT),
                (tr("lc.best"), T.laptime(d.best_session), (200, 120, 255, 255) if d.best_session > 0 and abs(d.last - d.best_session) < 1e-3 else T.TEXT),
                (tr("lc.current"), T.laptime(d.lap_time), T.TEXT))
        rh = 34
        for i, (lab, _v, _c) in enumerate(rows):
            y = 4 + i * rh
            if i:
                c.rect(8, y, w - 16, 1, (255, 255, 255, 40))
            c.text(12, y, w * 0.5, rh, lab, 17, T.TEXT, "l", 700)
        c.mark_static()
        for i, (_lab, val, col) in enumerate(rows):
            c.text(w * 0.4, 4 + i * rh, w * 0.6 - 12, rh, val, 19 if i else 22, col, "r", 800)
        sy = 4 + 4 * rh + 4
        sector_bar(c, 8, sy, w - 16, 14, snap, ctx)
        delta_box(c, 8, sy + 18, w - 16, h - sy - 24, d, 24)

    # ---- faixa horizontal ----------------------------------------------------------------- #
    def _d_strip(self, c, snap, ctx, w, h):
        d = ctx.delta
        T.panel(c, w, h)
        cols = ((tr("lc.lap"), self._lap(snap)), (tr("lc.last"), T.laptime(d.last)),
                (tr("lc.best"), T.laptime(d.best_session)), (tr("lc.current"), T.laptime(d.lap_time)))
        cw = (w - 150) / 4
        for i, (lab, _v) in enumerate(cols):
            c.text(10 + i * cw, 6, cw, 14, lab.upper(), 9, T.FAINT, "l", 800, spacing=1)
        c.mark_static()
        for i, (_lab, val) in enumerate(cols):
            c.text(10 + i * cw, 18, cw, 28, val, 20 if i else 24, T.TEXT, "l", 800)
        sector_bar(c, 10, h - 20, w - 170, 12, snap, ctx)
        delta_box(c, w - 142, 8, 132, h - 16, d, 24)

    # ---- estilo TV (cabeçalho do estilo escolhido) ------------------------------------------ #
    def _d_tv(self, c, snap, ctx, w, h):
        d = ctx.delta
        s = snap.session
        right = tr("left", t=T.clock(s.time_left)) if s.time_left is not None and not s.max_laps else ""
        y = T.panel(c, w, h, tr("lc.lap"), right, part="bg")
        for i, lab in enumerate((tr("lc.last"), tr("lc.best"), tr("lc.current"))):
            c.text(w * 0.42, y + 2 + i * 22, 80, 22, lab, 12, T.DIM, "l", 600)
        c.mark_static()
        T.panel(c, w, h, tr("lc.lap"), right, part="right")
        c.text(12, y, w * 0.4, 56, self._lap(snap), 40, T.TEXT, "l", 800)
        for i, val in enumerate((T.laptime(d.last), T.laptime(d.best_session), T.laptime(d.lap_time))):
            c.text(w * 0.42, y + 2 + i * 22, w * 0.58 - 12, 22, val, 16, T.TEXT, "r", 800)
        sector_bar(c, 10, h - 44, w - 20, 12, snap, ctx)
        delta_box(c, 10, h - 28, w - 20, 22, d, 16)

    # ---- mínimo: tempo atual grande + delta ------------------------------------------------ #
    def _d_minimal(self, c, snap, ctx, w, h):
        d = ctx.delta
        c.rect(0, 0, w, h, (10, 12, 16, 200), radius=8)
        c.mark_static()
        c.text(12, 4, w - 24, 18, f"{tr('lc.lap')} {self._lap(snap)}", 12, T.DIM, "l", 700)
        c.text(12, 4, w - 24, 18, f"{tr('lc.best')} {T.laptime(d.best_session)}", 12, T.DIM, "r", 700)
        c.text(12, 20, w * 0.58, 42, T.laptime(d.lap_time), 30, T.TEXT, "l", 800)
        delta_box(c, w * 0.6, 26, w * 0.4 - 12, 30, d, 18)
        sector_bar(c, 12, h - 24, w - 24, 14, snap, ctx)

    # ---- o original ----------------------------------------------------------------------- #
    def _classic(self, c, snap, ctx, w, h):
        s, me = snap.session, snap.me
        lap = me.total_laps + 1
        y = T.panel(c, w, h, tr("lc.lap"), "", part="bg")
        c.mark_static()
        if s.max_laps:
            lap = min(lap, s.max_laps)
            right = tr("lc.of", m=s.max_laps)
            left_laps = max(0, s.max_laps - me.total_laps)
        else:
            right = tr("left", t=T.clock(s.time_left)) if s.time_left is not None else ""
            left_laps = ctx.fuel.race_laps_left if s.kind == "race" and ctx.fuel.race_laps_left > 0 else None
        T.panel(c, w, h, tr("lc.lap"), right, part="right")
        c.text(14, y - 2, 110, 46, str(lap), 42, T.TEXT, "l", 800)
        if s.max_laps:
            c.text(14 + c.measure(str(lap), 42, 800) + 6, y + 14, 80, 26, f"/ {s.max_laps}", 20, T.DIM, "l", 800)
        if left_laps is not None:
            c.text(w - 120, y + 2, 106, 20, tr("lc.left_label"), 10, T.FAINT, "r", 700, spacing=1)
            val = f"{left_laps:.0f}" if s.max_laps else f"~{left_laps:.1f}"
            c.text(w - 120, y + 16, 106, 28, val, 24, T.ACCENT, "r", 800)
