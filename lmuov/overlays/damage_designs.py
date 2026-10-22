"""Designs alternativos do overlay de danos (escolhe-se em Overlays > Damage > Design).

Todos mostram os mesmos dados (ver damage.py); muda só a forma:
  engineer  folha de engenheiro: tabela por roda (suspensão, travão, pneu, pressão) + motor + toques
  exploded  vista explodida: cada peça separada do carro, com a % ao lado
  corners   o carro ao centro e um cartão para cada canto
  heatmap   o carro grande com "manchas" de calor onde está o dano
  mini      faixa pequena com o pior valor de cada sistema
"""

from __future__ import annotations

import math

from .. import theme as T
from ..canvas import alpha, mix
from ..i18n import tr
from .damage import BAD_COL, LEVEL, OK_COL, PANEL_IDLE, WARN_COL, WHEELS, ZONES, damage_level, frac_col

NONE_COL = (130, 136, 150, 255)
UNKNOWN = (255, 255, 255, 22)


# ---- dados ------------------------------------------------------------------ #
def corner(p, i: int) -> dict:
    t = p.tyres[i] if i < len(p.tyres) else None
    temps = [v for v in (t.temp_lcr if t else ()) if v > 0]
    return {
        "susp": p.susp_damage[i] if i < len(p.susp_damage) else -1.0,
        "brake": p.brake_wear[i] if i < len(p.brake_wear) else -1.0,
        "btemp": t.brake_temp if t else 0.0,
        "tyre": (1.0 - t.wear) if t and 0 <= t.wear <= 1 else -1.0,
        "press": t.pressure if t else 0.0,
        "temp": sum(temps) / len(temps) if temps else 0.0,
        "flat": bool(t and t.flat), "lost": bool(t and t.detached),
    }


def worst(vals) -> float:
    vals = [v for v in vals if v >= 0]
    return max(vals) if vals else -1.0


def pct(v: float) -> str:
    return "—" if v < 0 else f"{v * 100:.0f}%"


def col(v: float):
    return NONE_COL if v < 0 else frac_col(v)


def dents_of(p) -> dict:
    d = p.dents or ()
    return {z: (d[i] if i < len(d) else 0) for i, z in enumerate(ZONES)}


def zone_col(p, zone: str):
    if not p.dents:
        return UNKNOWN
    return LEVEL.get(min(2, dents_of(p)[zone])) or PANEL_IDLE


def aero_col(p):
    if p.aero_detached:
        return BAD_COL
    return frac_col(p.aero_damage) if p.aero_damage >= 0 else UNKNOWN


def engine_state(p) -> tuple[str, tuple]:
    eng = [txt for bit, txt in ((1, tr("dmg.hot")), (2, tr("dmg.hot")), (4, tr("dmg.oil_p")),
                                (8, tr("dmg.fuel_p")), (16, tr("dmg.stalled"))) if p.warnings & bit]
    if p.overheating and tr("dmg.hot") not in eng:
        eng.append(tr("dmg.hot"))
    eng = list(dict.fromkeys(eng))
    if not eng:
        return tr("dmg.ok_short"), T.GOOD
    return ", ".join(eng), (BAD_COL if p.warnings & 28 else WARN_COL)


def status(p) -> tuple[str, tuple]:
    lvl = damage_level(p)
    return ((tr("dmg.ok"), T.GOOD), (tr("dmg.light"), T.WARN), (tr("dmg.heavy"), T.BAD))[lvl]


def last_hit(p, ctx) -> str:
    since = ctx.since("impact")
    hits = getattr(ctx, "hits", []) or []
    where = ""
    if hits:
        t0 = hits[-1][0]
        zs = list(dict.fromkeys(tr(f"dmg.z.{ZONES[i]}") for t, i, _l in hits if abs(t - t0) < 1.0 and i < len(ZONES)))
        where = " · " + ", ".join(zs[:2])
    if p.impact_mag > 0 and since < 3600:
        return tr("dmg.ago", s=f"{since:.0f}") + where
    return tr("dmg.none_yet")


# ---- carro visto de cima (geometria comum) -------------------------------------- #
def body_polys(cx: float, y0: float, bw: float, bl: float) -> dict:
    """Polígonos de cada painel + asas, para um carro de largura bw e comprimento bl."""
    x0, x1, y1 = cx - bw / 2, cx + bw / 2, y0 + bl
    k = bw / 74.0
    fz, rz = bl * 0.30, bl * 0.70
    a, b, e = 18 * k, 14 * k, 26 * k
    s = 16 * k
    return {
        "wf": [(x0 - 8 * k, y0 - 14 * k), (x1 + 8 * k, y0 - 14 * k), (x1 + 4 * k, y0 - 6 * k), (x0 - 4 * k, y0 - 6 * k)],
        "wr": [(x0 - 10 * k, y1 + 8 * k), (x1 + 10 * k, y1 + 8 * k), (x1 + 10 * k, y1 + 16 * k), (x0 - 10 * k, y1 + 16 * k)],
        "f": [(x0 + a, y0), (x1 - a, y0), (x1 - b, y0 + 20 * k), (x0 + b, y0 + 20 * k)],
        "fl": [(x0 + 4 * k, y0 + 6 * k), (x0 + a, y0), (x0 + b, y0 + 20 * k), (x0 + e, y0 + fz), (x0, y0 + fz)],
        "fr": [(x1 - 4 * k, y0 + 6 * k), (x1 - a, y0), (x1 - b, y0 + 20 * k), (x1 - e, y0 + fz), (x1, y0 + fz)],
        "l": [(x0, y0 + fz), (x0 + s, y0 + fz), (x0 + s, y0 + rz), (x0, y0 + rz)],
        "r": [(x1, y0 + fz), (x1 - s, y0 + fz), (x1 - s, y0 + rz), (x1, y0 + rz)],
        "rl": [(x0, y0 + rz), (x0 + e, y0 + rz), (x0 + b, y1 - a), (x0 + a, y1), (x0 + 4 * k, y1 - 4 * k)],
        "rr": [(x1, y0 + rz), (x1 - e, y0 + rz), (x1 - b, y1 - a), (x1 - a, y1), (x1 - 4 * k, y1 - 4 * k)],
        "b": [(x0 + b, y1 - a), (x1 - b, y1 - a), (x1 - a, y1), (x0 + a, y1)],
        "hood": [(x0 + b, y0 + 20 * k), (x1 - b, y0 + 20 * k), (x1 - s, y0 + fz), (x0 + s, y0 + fz)],
        "mid": [(x0 + s, y0 + fz), (x1 - s, y0 + fz), (x1 - s, y0 + rz), (x0 + s, y0 + rz)],
    }


def wheel_spots(cx, y0, bw, bl, wl, ww, gap) -> list:
    x0, x1, y1 = cx - bw / 2, cx + bw / 2, y0 + bl
    return [(x0 - ww - gap, y0 + bl * 0.06), (x1 + gap, y0 + bl * 0.06),
            (x0 - ww - gap, y1 - wl - bl * 0.07), (x1 + gap, y1 - wl - bl * 0.07)]


def centroid(pts):
    return sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts)


def draw_car(c, p, cx, y0, bw, bl, glow=True, wheels=True, offset=0.0, wheel_col=None):
    """Carro com cada painel na cor do dano. offset > 0 afasta as peças do centro (vista explodida)."""
    polys = body_polys(cx, y0, bw, bl)
    mx, my = cx, y0 + bl / 2

    def moved(pts, f=1.0):
        if not offset:
            return pts
        gx, gy = centroid(pts)
        dx, dy = (gx - mx) * offset * f, (gy - my) * offset * f
        return [(q[0] + dx, q[1] + dy) for q in pts]

    c.polygon(moved(polys["hood"]), (255, 255, 255, 14))
    c.polygon(moved(polys["mid"]), alpha(T.BAD, 110) if p.overheating else (255, 255, 255, 12))
    k = bw / 74.0
    c.rect(cx - bw / 2 + 18 * k, y0 + bl * 0.33, bw - 36 * k, bl * 0.2, (8, 10, 14, 200), radius=6 * k,
           stroke=(255, 255, 255, 50), stroke_w=1)
    for z in ZONES:
        pts = moved(polys[z])
        fill = zone_col(p, z)
        if glow and fill[3] > 200:
            xs, ys = [q[0] for q in pts], [q[1] for q in pts]
            T.neon_glow(c, min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys), fill, 0.6)
        c.polygon(pts, fill, stroke=(255, 255, 255, 70), stroke_w=1)
    for key in ("wf", "wr"):
        pts = moved(polys[key], 0.7)
        c.polygon(pts, aero_col(p), stroke=(255, 255, 255, 70), stroke_w=1)
    out = []
    if wheels:
        wl, ww = bl * 0.24, bw * 0.18
        gap = 9 * k + offset * bw * 0.5
        for i, (wx, wy) in enumerate(wheel_spots(cx, y0, bw, bl, wl, ww, gap)):
            cd = corner(p, i)
            ax = cx - bw / 2 if i % 2 == 0 else cx + bw / 2
            ex = wx + ww if i % 2 == 0 else wx
            sc = col(cd["susp"]) if cd["susp"] >= 0 else (255, 255, 255, 60)
            for dy in (wl * 0.2, wl * 0.8):
                c.line(ex, wy + dy, ax, wy + wl / 2 + (dy - wl / 2) * 0.4, sc, 3 if cd["susp"] > 0.02 else 2)
            if cd["lost"]:
                c.rect(wx, wy, ww, wl, None, radius=3, stroke=BAD_COL, stroke_w=1.5)
                c.line(wx + 2, wy + 2, wx + ww - 2, wy + wl - 2, BAD_COL, 2)
                c.line(wx + ww - 2, wy + 2, wx + 2, wy + wl - 2, BAD_COL, 2)
            else:
                fill = BAD_COL if cd["flat"] else (wheel_col(cd) if wheel_col else (34, 36, 42, 255))
                c.rect(wx, wy, ww, wl, fill, radius=3, stroke=(255, 255, 255, 90), stroke_w=1)
            out.append((wx, wy, ww, wl))
    return polys, out


def bar(c, x, y, w, h, v, colr=None):
    c.rect(x, y, w, h, (255, 255, 255, 18), radius=h / 2)
    if v > 0:
        c.rect(x, y, max(h, w * min(1.0, v)), h, colr or frac_col(v), radius=h / 2)


# ---- 2. folha de engenheiro --------------------------------------------------- #
def engineer(ov, c, p, ctx, w, h):
    st, sc = status(p)
    y = T.panel(c, w, h, ov.title, st, sc)
    car_w = 132
    draw_car(c, p, 12 + car_w / 2, y + 30, 62, min(178.0, h - y - 96), glow=False,
             wheel_col=lambda cd: col(worst([cd["susp"], cd["brake"]])) if worst([cd["susp"], cd["brake"]]) > 0.02
             else (34, 36, 42, 255))
    # aero por baixo do carro
    ay = h - 40
    c.text(12, ay, car_w, 14, tr("dmg.aero").upper(), 9, T.FAINT, "l", 800, spacing=1)
    c.text(12, ay, car_w, 14, pct(p.aero_damage) + (" !" if p.aero_detached else ""), 11, col(p.aero_damage), "r", 800)
    bar(c, 12, ay + 17, car_w, 5, max(0.0, p.aero_damage), aero_col(p) if p.aero_damage >= 0 else None)

    x = 12 + car_w + 14
    tw = w - x - 12
    cols = (("", 0.12), (tr("dmg.c.susp"), 0.19), (tr("dmg.c.brake"), 0.19), ("°C", 0.14),
            (tr("dmg.c.tyre"), 0.19), ("kPa", 0.17))
    xs, cx_ = [], x
    for _n, f in cols:
        xs.append((cx_, tw * f))
        cx_ += tw * f
    ty = y + 8
    for (cx0, cw), (name, _f) in zip(xs, cols):
        c.text(cx0, ty, cw - 4, 14, name.upper(), 9, T.FAINT, "r" if name else "l", 800, spacing=0.5)
    rh = 25
    for i in range(4):
        cd = corner(p, i)
        ry = ty + 18 + i * rh
        if i % 2 == 0:
            c.rect(x - 4, ry, tw + 8, rh - 2, (255, 255, 255, 7), radius=3)
        c.text(xs[0][0], ry, xs[0][1], rh - 2, WHEELS[i], 11, T.DIM, "l", 800)
        for j, key in ((1, "susp"), (2, "brake"), (4, "tyre")):
            v = cd[key]
            cx0, cw = xs[j]
            if v > 0:
                c.rect(cx0 + cw - 4 - (cw - 10) * min(1.0, v), ry + rh - 6, (cw - 10) * min(1.0, v), 2, col(v))
            c.text(cx0, ry, cw - 4, rh - 4, pct(v), 12, col(v) if v > 0.02 else T.TEXT if v >= 0 else T.FAINT, "r", 800)
        bt = cd["btemp"]
        c.text(xs[3][0], ry, xs[3][1] - 4, rh - 4, f"{bt:.0f}" if bt > 0 else "—", 12,
               T.BAD if bt > 900 else T.WARN if bt > 750 else T.DIM, "r", 700)
        if cd["lost"] or cd["flat"]:
            c.text(xs[5][0], ry, xs[5][1] - 4, rh - 4, tr("dmg.lost_s" if cd["lost"] else "dmg.flat_s").upper(), 10,
                   BAD_COL, "r", 800)
        else:
            c.text(xs[5][0], ry, xs[5][1] - 4, rh - 4, f"{cd['press']:.0f}" if cd["press"] > 0 else "—", 12, T.DIM, "r", 700)
    # carroçaria: os 8 painéis em pastilhas
    by = ty + 18 + 4 * rh + 8
    c.text(x, by, tw, 14, tr("dmg.body").upper(), 9, T.FAINT, "l", 800, spacing=1)
    pw = (tw - 3 * 4) / 4
    d = dents_of(p)
    for i, z in enumerate(ZONES):
        px, py = x + (i % 4) * (pw + 4), by + 16 + (i // 4) * 20
        lv = d[z] if p.dents else -1
        cc = LEVEL.get(min(2, lv)) if lv > 0 else None
        c.rect(px, py, pw, 17, alpha(cc, 60) if cc else (255, 255, 255, 10), radius=3,
               stroke=cc if cc else None, stroke_w=1)
        c.text(px + 4, py, pw - 8, 17, tr(f"dmg.zs.{z}"), 9, T.TEXT if cc else T.FAINT, "c", 700)
    # motor e último toque
    my = by + 16 + 2 * 20 + 6
    es, ecol = engine_state(p)
    temps = []
    if p.water_temp > 0:
        temps.append(tr("dmg.water", x=f"{p.water_temp:.0f}"))
    if p.oil_temp > 0:
        temps.append(tr("dmg.oil", x=f"{p.oil_temp:.0f}"))
    c.text(x, my, tw * 0.3, 16, tr("dmg.engine").upper(), 9, T.FAINT, "l", 800, spacing=1)
    c.text(x + tw * 0.25, my, tw * 0.75, 16, " · ".join(temps + [es]), 11, ecol if ecol is not T.GOOD else T.TEXT, "r", 700)
    c.text(x, my + 18, tw * 0.3, 16, tr("dmg.impact").upper(), 9, T.FAINT, "l", 800, spacing=1)
    recent = ctx.since("impact") < float(ov.cfg.get("impact_s", 10))
    c.text(x + tw * 0.25, my + 18, tw * 0.75, 16, last_hit(p, ctx), 11, WARN_COL if recent else T.DIM, "r", 700)


# ---- 3. vista explodida ------------------------------------------------------- #
def exploded(ov, c, p, ctx, w, h):
    st, sc = status(p)
    y = T.panel(c, w, h, ov.title, st, sc)
    cx, bw = w / 2, 86.0
    bl = h - y - 96
    y0 = y + 62
    bl = h - y - 168
    polys, wheels = draw_car(c, p, cx, y0, bw, bl, offset=0.32)
    ry = max(q[1] for q in polys["wr"]) + (max(q[1] for q in polys["wr"]) - (y0 + bl / 2)) * 0.22 + 6
    # etiquetas das asas
    fy = min(q[1] for q in polys["wf"])
    c.text(0, y + 4, w, 14, f"{tr('dmg.wing_f').upper()}  {pct(p.aero_damage)}", 10, col(p.aero_damage)
           if p.aero_damage > 0.02 else T.DIM, "c", 800, spacing=0.5)
    c.text(0, ry, w, 14, f"{tr('dmg.wing_r').upper()}  {pct(p.aero_damage)}", 10, col(p.aero_damage)
           if p.aero_damage > 0.02 else T.DIM, "c", 800, spacing=0.5)
    # rodas: suspensão e travão ao lado de fora
    for i, (wx, wy, ww, wl) in enumerate(wheels):
        cd = corner(p, i)
        left = i % 2 == 0
        tx = 8 if left else wx + ww + 6
        tw_ = wx - 14 if left else w - tx - 8
        al = "l" if left else "r"
        c.text(tx, wy - 2, tw_, 13, WHEELS[i], 9, T.FAINT, al, 800)
        c.text(tx, wy + 11, tw_, 14, f"{tr('dmg.c.susp')} {pct(cd['susp'])}", 10, col(cd["susp"])
               if cd["susp"] > 0.02 else T.DIM, al, 800)
        c.text(tx, wy + 25, tw_, 14, f"{tr('dmg.c.brake')} {pct(cd['brake'])}", 10, col(cd["brake"])
               if cd["brake"] > 0.02 else T.DIM, al, 700)
        if cd["flat"] or cd["lost"]:
            c.text(tx, wy + 39, tw_, 14, tr("dmg.lost_s" if cd["lost"] else "dmg.flat_s").upper(), 10, BAD_COL, al, 800)
    # painéis danificados: número do nível em cima da peça
    d = dents_of(p)
    for z in ZONES:
        if p.dents and d[z] > 0:
            gx, gy = centroid(polys[z])
            gx += (gx - cx) * 0.32
            gy += (gy - (y0 + bl / 2)) * 0.32
            c.ellipse(gx, gy, 8, 8, (10, 12, 16, 230), stroke=LEVEL[min(2, d[z])], stroke_w=1.5)
            c.text(gx - 8, gy - 8, 16, 16, "!" if d[z] >= 2 else "·", 11, LEVEL[min(2, d[z])], "c", 900)
    es, ecol = engine_state(p)
    c.text(0, h - 24, w, 14, f"{tr('dmg.engine').upper()}  {es}", 10, ecol if ecol is not T.GOOD else T.DIM, "c", 800)


# ---- 4. cantos ------------------------------------------------------------------ #
def corners(ov, c, p, ctx, w, h):
    st, sc = status(p)
    y = T.panel(c, w, h, ov.title, st, sc)
    cx, bw = w / 2, 58.0
    bl = h - y - 66
    draw_car(c, p, cx, y + 34, bw, bl, wheels=False)
    cw, chh = (w - bw - 70) / 2 - 8, (h - y - 60) / 2 - 4
    for i in range(4):
        cd = corner(p, i)
        left, top = i % 2 == 0, i < 2
        x0 = 8 if left else w - 8 - cw
        y0 = y + 6 + (0 if top else chh + 8)
        wv = worst([cd["susp"], cd["brake"]])
        edge = BAD_COL if cd["flat"] or cd["lost"] else (col(wv) if wv > 0.02 else (255, 255, 255, 40))
        c.rect(x0, y0, cw, chh, (255, 255, 255, 8), radius=5, stroke=alpha(edge, 160), stroke_w=1)
        c.rect(x0 if left else x0 + cw - 3, y0 + 6, 3, chh - 12, edge, radius=1.5)
        c.text(x0 + 10, y0 + 4, cw - 20, 15, tr(f"dmg.w.{WHEELS[i]}").upper(), 9, T.FAINT, "l", 800, spacing=0.8)
        if cd["flat"] or cd["lost"]:
            c.text(x0 + 10, y0 + 4, cw - 20, 15, tr("dmg.lost_s" if cd["lost"] else "dmg.flat_s").upper(), 9, BAD_COL, "r", 800)
        rows = ((tr("dmg.c.susp"), cd["susp"]), (tr("dmg.c.brake"), cd["brake"]), (tr("dmg.c.tyre"), cd["tyre"]))
        rh = (chh - 40) / 3
        for j, (lab, v) in enumerate(rows):
            ry = y0 + 21 + j * rh
            c.text(x0 + 10, ry, cw * 0.45, rh, lab, 10, T.DIM, "l", 600)
            bar(c, x0 + cw * 0.42, ry + rh / 2 - 2, cw * 0.32, 4, max(0.0, v), col(v) if v > 0.02 else T.GOOD)
            c.text(x0 + cw * 0.74, ry, cw * 0.26 - 10, rh, pct(v), 11, col(v) if v > 0.02 else T.TEXT, "r", 800)
        foot = []
        if cd["btemp"] > 0:
            foot.append(f"{cd['btemp']:.0f}°C")
        if cd["press"] > 0:
            foot.append(f"{cd['press']:.0f} kPa")
        c.text(x0 + 10, y0 + chh - 18, cw - 20, 14, " · ".join(foot), 9, T.FAINT, "l", 600)
        # linha do cartão até ao canto do carro
        ax = cx - bw / 2 - 4 if left else cx + bw / 2 + 4
        ay = y + 34 + (bl * 0.18 if top else bl * 0.82)
        c.line(x0 + cw if left else x0, y0 + chh / 2, ax, ay, alpha(edge, 120), 1)
    c.text(cx - 60, y + 4, 120, 14, f"{tr('dmg.aero').upper()} {pct(p.aero_damage)}", 10,
           col(p.aero_damage) if p.aero_damage > 0.02 else T.DIM, "c", 800)
    es, ecol = engine_state(p)
    c.text(0, h - 22, w, 14, f"{tr('dmg.engine').upper()} {es}   ·   {tr('dmg.impact')} {last_hit(p, ctx)}", 10,
           ecol if ecol is not T.GOOD else T.DIM, "c", 700)


# ---- 5. mapa de calor ------------------------------------------------------------- #
def heatmap(ov, c, p, ctx, w, h):
    st, sc = status(p)
    y = T.panel(c, w, h, ov.title, st, sc)
    cx, bw = w / 2, 104.0
    bl = h - y - 108
    y0 = y + 30
    polys = body_polys(cx, y0, bw, bl)
    # silhueta neutra
    for key in ("hood", "mid", *ZONES):
        c.polygon(polys[key], (255, 255, 255, 16), stroke=(255, 255, 255, 60), stroke_w=1)
    for key in ("wf", "wr"):
        c.polygon(polys[key], alpha(aero_col(p), 200) if p.aero_damage > 0.02 or p.aero_detached else (255, 255, 255, 16),
                  stroke=(255, 255, 255, 60), stroke_w=1)
    # manchas de calor
    d = dents_of(p)
    for z in ZONES:
        if p.dents and d[z] > 0:
            gx, gy = centroid(polys[z])
            colr = LEVEL[min(2, d[z])]
            r = 22 if d[z] >= 2 else 15
            for f, a in ((1.0, 40), (0.7, 70), (0.45, 120), (0.25, 200)):
                c.ellipse(gx, gy, r * f * 1.25, r * f * 1.25, alpha(colr, a))
    # rodas com a cor do pior valor do canto
    wl, ww = bl * 0.22, bw * 0.16
    for i, (wx, wy) in enumerate(wheel_spots(cx, y0, bw, bl, wl, ww, 8)):
        cd = corner(p, i)
        v = worst([cd["susp"], cd["brake"]])
        fill = BAD_COL if cd["flat"] or cd["lost"] else (alpha(col(v), 220) if v > 0.02 else (40, 44, 52, 255))
        c.rect(wx, wy, ww, wl, fill, radius=3, stroke=(255, 255, 255, 90), stroke_w=1)
        left = i % 2 == 0
        c.text(wx - 40 if left else wx + ww + 2, wy + wl / 2 - 7, 38, 14, pct(v), 10,
               col(v) if v > 0.02 else T.FAINT, "r" if left else "l", 800)
    # impacto recente: anel a pulsar
    since = ctx.since("impact")
    hits = getattr(ctx, "hits", []) or []
    if since < float(ov.cfg.get("impact_s", 10)) and hits:
        gx, gy = centroid(polys[ZONES[hits[-1][1]]])
        a = int(255 * max(0.0, 1 - since / float(ov.cfg.get("impact_s", 10))))
        c.ellipse(gx, gy, 26, 26, None, stroke=alpha((255, 255, 255, 255), a), stroke_w=2)
    # legenda
    ly = h - 46
    for k in range(40):
        f = k / 39
        c.rect(16 + k * (w - 32) / 40, ly, (w - 32) / 40 + 0.5, 6, frac_col(f))
    c.text(16, ly + 8, 80, 12, tr("dmg.ok_short"), 9, T.FAINT, "l", 700)
    c.text(w - 96, ly + 8, 80, 12, tr("dmg.sev2"), 9, T.FAINT, "r", 700)
    es, ecol = engine_state(p)
    c.text(0, h - 22, w, 14, f"{tr('dmg.aero')} {pct(p.aero_damage)}  ·  {tr('dmg.engine')} {es}", 10,
           ecol if ecol is not T.GOOD else T.DIM, "c", 700)


# ---- 6. faixa mini ------------------------------------------------------------------ #
def mini(ov, c, p, ctx, w, h):
    T.panel(c, w, h)
    st, sc = status(p)
    c.rect(0, 0, 4, h, sc, radius=2)
    draw_car(c, p, 30, 14, 18, h - 28, glow=False, wheels=False)
    items = [
        ("Aero", p.aero_damage if not p.aero_detached else 1.0),
        (tr("dmg.c.susp"), worst(p.susp_damage)),
        (tr("dmg.c.brake"), worst(p.brake_wear)),
    ]
    body = max(p.dents) / 2 if p.dents else -1.0
    items.insert(0, ("body", body))
    x = 56
    cw = (w - x - 76) / len(items)
    for lab, v in items:
        c.text(x, 8, cw - 4, 13, tr("dmg.zs.body" if lab == "body" else lab).upper(), 8, T.FAINT, "c", 800, spacing=0.5)
        txt = pct(v)
        if lab == "body":
            n = sum(1 for d in p.dents if d > 0) if p.dents else 0
            txt = "—" if v < 0 else tr("dmg.ok_short") if n == 0 else f"{n}/8"
        c.text(x, 22, cw - 4, h - 30, txt, 17, col(v) if v > 0.02 else T.TEXT if v >= 0 else T.FAINT, "c", 800)
        x += cw
    es, ecol = engine_state(p)
    c.text(x, 8, 70, 13, tr("dmg.engine").upper(), 8, T.FAINT, "c", 800, spacing=0.5)
    c.text(x, 22, 70, h - 30, "OK" if ecol is T.GOOD else "!", 17, T.TEXT if ecol is T.GOOD else ecol, "c", 800)


DESIGNS = {
    "engineer": (engineer, (500, 300)),
    "exploded": (exploded, (330, 400)),
    "corners": (corners, (520, 300)),
    "heatmap": (heatmap, (260, 400)),
    "mini": (mini, (330, 64)),
}
