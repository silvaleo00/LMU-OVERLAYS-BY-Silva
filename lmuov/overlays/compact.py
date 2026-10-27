"""Estilo "compacto" do Relative e da Standings: linhas finas, colunas que cada um liga/desliga.

Colunas possíveis (a ordem é sempre esta; o utilizador escolhe quais quer):
  pos, number, country, name, sr, dr, logo, gap, interval, last, best, avg5, tyre, energy, pits
"""

from __future__ import annotations

import math

from .. import theme as T
from .. import tv
from ..canvas import alpha
from ..i18n import tr

ORDER = ("pos", "number", "country", "name", "sr", "dr", "logo", "gap", "interval", "last", "best", "avg5",
         "tyre", "energy", "pits")
WIDTH = {"pos": 24, "number": 30, "country": 30, "name": 138, "sr": 26, "dr": 96, "logo": 30, "gap": 54,
         "interval": 54, "last": 62, "best": 62, "avg5": 62, "tyre": 22, "energy": 42, "pits": 30}
HEAD = {"pos": "", "number": "#", "country": "", "name": "", "sr": "", "dr": "DR", "logo": "",
        "gap": "col.gap", "interval": "col.int", "last": "col.last", "best": "col.best", "avg5": "col.avg5",
        "tyre": "", "energy": "col.nrg", "pits": "col.pits"}
RELATIVE_COLS = ("pos", "number", "name", "sr", "dr", "logo", "last", "tyre", "energy", "pits", "gap")
STANDINGS_COLS = ("pos", "number", "country", "name", "sr", "dr", "logo", "gap", "interval", "last", "best",
                  "avg5", "tyre", "energy", "pits")
REL_DEFAULT = ["pos", "name", "sr", "dr", "logo", "gap"]
STD_DEFAULT = ["pos", "name", "sr", "dr", "logo", "gap", "best", "tyre", "energy"]

ROW = 21
ROW_BG = (22, 24, 30, 232)
ROW_BG2 = (28, 30, 38, 232)
ME_BG = (34, 72, 112, 240)
HEAD_BG = (10, 11, 15, 245)
TYRE_COLORS = {"S": (235, 52, 60, 255), "M": (255, 204, 0, 255), "H": (236, 238, 242, 255),
               "W": (40, 140, 255, 255), "D": (180, 186, 198, 255)}


def columns(cfg, allowed, default, snap) -> list:
    """Colunas ativas, pela ordem certa. SR/DR/país só aparecem se o jogo der esses dados."""
    want = cfg.get("columns") or default
    cols = [k for k in ORDER if k in want and k in allowed]
    if snap is not None:
        for k in ("sr", "dr", "country"):
            if k in cols and not any(getattr(v, k) for v in snap.vehicles):
                cols.remove(k)
    if "name" not in cols:
        cols.insert(min(1, len(cols)), "name")
    return cols


def width(cols) -> int:
    return int(sum(WIDTH[k] for k in cols) + 8)


def xs(cols, w) -> dict:
    """x de cada coluna; o nome fica com o espaço que sobrar."""
    fixed = sum(WIDTH[k] for k in cols if k != "name")
    out, x = {}, 4.0
    for k in cols:
        cw = (w - 8 - fixed) if k == "name" else WIDTH[k]
        out[k] = (x, cw)
        x += cw
    return out


def header_bar(c, w, left: str, right: str = "") -> float:
    c.rect(0, 0, w, 22, HEAD_BG, radius=4)
    c.rect(0, 20, w, 2, T.ACCENT)
    c.text(8, 0, w * 0.6, 20, left, 12, T.TEXT, "l", 800)
    if right:
        c.text(w * 0.4, 0, w * 0.6 - 8, 20, right, 11, T.DIM, "r", 700)
    return 24.0


def col_heads(c, cols, x, y, h, color=T.FAINT):
    for k, (cx, cw) in x.items():
        lab = HEAD.get(k, "")
        if lab:
            lab = tr(lab) if "." in lab else lab
            al = "r" if k in ("gap", "interval", "last", "best", "avg5", "energy") else "c"
            c.text(cx, y, cw - 4, h, lab, 9, color, al, 800, spacing=0.5)


def sof(vehicles) -> float:
    """Strength of field do iRacing (a partir do iRating de cada piloto)."""
    irs = [v.irating for v in vehicles if v.irating > 0]
    if not irs:
        return 0.0
    br = 1600 / math.log(2)
    return br * math.log(len(irs) / sum(math.exp(-ir / br) for ir in irs))


def dr_sof(vehicles) -> str:
    """SOF em Driver Rating (como o LMU): média dos níveis da classe, ex. "S2 69%"."""
    vals = []
    for v in vehicles:
        tier, lvl = tv.dr_parts(v.dr)
        if tier in "BSGP" and tier:
            t = "BSGP".index(tier)
            vals.append(t * 3 + (int(lvl) - 1 if lvl else 0) + max(0.0, v.dr_pct))
    if not vals:
        return ""
    m = sum(vals) / len(vals)
    t = min(3, int(m // 3))
    rest = m - t * 3
    lvl = min(2, int(rest))
    return f"{'BSGP'[t]}{lvl + 1} {(rest - lvl) * 100:.0f}%"


def row(c, x, y, w, v, info, ctx, i=0):
    """Uma linha. info: gap, interval (texto), class_best, name_col, dim."""
    me = v.is_player
    dim = info.get("dim", False)
    c.rect(0, y, w, ROW - 1, ME_BG if me else (ROW_BG2 if i % 2 else ROW_BG), radius=2)
    if me:
        c.rect(0, y, 3, ROW - 1, T.ACCENT)
    _short, ccol = T.class_info(v.cls)
    ink = T.FAINT if dim else T.TEXT
    for k, (cx, cw) in x.items():
        if k == "pos":
            c.rect(cx + 1, y + 2, cw - 3, ROW - 5, alpha(ccol, 120) if dim else ccol, radius=3)
            c.text(cx + 1, y + 2, cw - 3, ROW - 5, str(v.class_place), 11, T.on_color(ccol), "c", 800)
        elif k == "number":
            c.text(cx, y, cw - 3, ROW - 1, v.number, 11, ccol if not dim else T.FAINT, "c", 800)
        elif k == "country":
            if v.country:
                c.rect(cx + 2, y + 4, cw - 6, ROW - 9, (255, 255, 255, 30), radius=2)
                c.text(cx + 2, y + 4, cw - 6, ROW - 9, v.country, 8.5, ink, "c", 800)
        elif k == "name":
            c.text(cx + 4, y, cw - 6, ROW - 1, T.driver_label(v.driver), 12.5, info.get("name_col", ink), "l",
                   800 if me else 700)
        elif k == "sr":                                 # Safety Rating: losango colorido (ou texto)
            if not tv.sr_icon(c, cx + cw / 2, y + ROW / 2 - 0.5, (ROW - 7) / 2, v.sr, dim):
                tv.rating_chip(c, cx + 2, y + 3, cw - 5, ROW - 7, v.sr, dim)
        elif k == "dr":                                 # Driver Rating: [S3] 50% +18%
            tv.dr_box(c, cx + 2, y + 3, cw - 5, ROW - 7, v.dr, v.dr_pct, v.dr_delta, dim)
        elif k == "logo":
            code = tv.brand_code(v.vehicle_name or v.team)
            if not tv.logo_plate(c, cx + 2, y + 2, cw - 4, ROW - 5, code, dim):
                bg, fg = tv.brand_colors(v.vehicle_name or v.team)
                c.rect(cx + 2, y + 3, cw - 4, ROW - 7, alpha(bg, 120) if dim else bg, radius=2)
                c.text(cx + 2, y + 3, cw - 4, ROW - 7, code, 8, fg, "c", 800)
        elif k in ("gap", "interval"):
            c.text(cx, y, cw - 4, ROW - 1, info.get(k, ""), 12, info.get(k + "_col", ink), "r", 800)
        elif k == "last":
            c.text(cx, y, cw - 4, ROW - 1, T.laptime(v.last), 11.5, T.FAINT if dim else T.DIM, "r", 600)
        elif k == "best":
            best = info.get("class_best", 0)
            pb = v.best > 0 and best > 0 and abs(v.best - best) < 1e-4
            c.text(cx, y, cw - 4, ROW - 1, T.laptime(v.best), 11.5, tv.PURPLE if pb else (T.FAINT if dim else T.DIM),
                   "r", 800 if pb else 600)
        elif k == "avg5":
            a = (getattr(ctx, "avg5", None) or {}).get(v.id, 0.0)
            c.text(cx, y, cw - 4, ROW - 1, T.laptime(a) if a > 0 else "—", 11.5, ink, "r", 600)
        elif k == "tyre":
            col = TYRE_COLORS.get(v.tyre)
            if col:
                r = (ROW - 7) / 2
                c.ellipse(cx + cw / 2, y + ROW / 2 - 0.5, r, r, (16, 16, 20, 255), stroke=col, stroke_w=2)
                c.text(cx, y, cw, ROW - 1, v.tyre, 8.5, col, "c", 900)
        elif k == "energy":
            if v.fuel_frac >= 0:
                f = max(0.0, min(1.0, v.fuel_frac))
                ecol = tv.energy_color(f)
                c.text(cx, y, cw - 4, ROW - 4, f"{f * 100:.0f}%", 11, ink, "r", 700)
                c.rect(cx + 4, y + ROW - 5, cw - 8, 2, (255, 255, 255, 25))
                c.rect(cx + 4, y + ROW - 5, (cw - 8) * f, 2, ecol)
        elif k == "pits":
            if v.in_pits:
                T.chip(c, cx + 1, y + 3, cw - 3, ROW - 7, tr("pit"), T.PIT, size=9)
            elif v.pitstops:
                c.text(cx, y, cw - 3, ROW - 1, f"P{v.pitstops}", 10, T.FAINT, "c", 700)
