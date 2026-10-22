"""Damage: o carro visto de cima, peça a peça.

LMU (o que o jogo dá):
  - carroçaria em 8 painéis (para-choques da frente, cantos da frente, lados, cantos de trás,
    para-choques de trás) com 3 níveis (intacto / amolgado / muito danificado);
  - aerodinâmica (asa da frente / splitter e asa de trás) em %, suspensão de cada roda em % e
    desgaste dos travões — pela API local do jogo (o mesmo ecrã de reparações das boxes);
  - rodas furadas ou soltas, peças soltas, motor sobreaquecido, último toque e a sua força.
iRacing (não dá danos por peça): tempo de reparação obrigatória/opcional, avisos do motor e rodas.
"""

from __future__ import annotations

from .. import theme as T
from ..canvas import alpha, mix
from ..i18n import tr
from .base import Overlay

# painéis de mDentSeverity, à volta do carro (sentido dos ponteiros a partir da frente-esquerda)
ZONES = ("fl", "f", "fr", "r", "rr", "b", "rl", "l")
WHEELS = ("FL", "FR", "RL", "RR")
OK_COL = (40, 214, 118, 255)
WARN_COL = (255, 170, 0, 255)
BAD_COL = (255, 56, 64, 255)
LEVEL = {0: None, 1: WARN_COL, 2: BAD_COL}
PANEL_IDLE = (226, 230, 238, 46)


def frac_col(f: float) -> tuple:
    """0 = verde, 0.5 = amarelo, 1 = vermelho."""
    if f < 0:
        return (120, 126, 140, 255)
    if f < 0.5:
        return mix(OK_COL, WARN_COL, f / 0.5)
    return mix(WARN_COL, BAD_COL, (f - 0.5) / 0.5)


def damage_level(p) -> int:
    """0 nada, 1 ligeiro, 2 grave."""
    lvl = max(p.dents) if p.dents else 0
    if p.aero_detached or any(t.flat or t.detached for t in p.tyres):
        lvl = 2
    if p.warnings & (4 | 8 | 16):
        lvl = 2
    elif p.warnings and lvl < 1:
        lvl = 1
    for f in (p.aero_damage, *p.susp_damage):
        if f >= 0.25:
            lvl = 2
        elif f > 0.02:
            lvl = max(lvl, 1)
    if p.repair_req > 0:
        lvl = max(lvl, 2 if p.repair_req > 20 else 1)
    elif p.repair_opt > 0:
        lvl = max(lvl, 1)
    return lvl


class DamageOverlay(Overlay):
    key = "damage"
    defaults = {"impact_s": 10.0, "design": "blueprint"}   # blueprint, engineer, exploded, corners, heatmap, mini
    default_pos = (1225, 545)
    smart_capable = True
    default_mode = "auto"
    W, H = 430, 300

    def auto_visible(self, snap, ctx):
        return damage_level(snap.player) > 0 or ctx.since("impact") < float(self.cfg["impact_s"])

    def _design(self):
        from .damage_designs import DESIGNS
        return DESIGNS.get(str(self.cfg.get("design", "blueprint")))

    def size(self, snap, ctx):
        d = self._design()
        return d[1] if d else (self.W, self.H)

    # ------------------------------------------------------------------ #
    def render(self, c, snap, ctx, w, h):
        p = snap.player
        d = self._design()
        if d:
            d[0](self, c, p, ctx, w, h)
            return
        lvl = damage_level(p)
        head = (tr("dmg.ok"), T.GOOD) if lvl == 0 else ((tr("dmg.light"), T.WARN) if lvl == 1 else (tr("dmg.heavy"), T.BAD))
        y = T.panel(c, w, h, self.title, head[0], part="bg")
        c.mark_static()
        T.panel(c, w, h, self.title, head[0], part="right")
        self._car(c, p, ctx, 16, y + 4, 168, h - y - 12)
        self._list(c, p, ctx, 196, y + 2, w - 206, h - y - 10)

    # ---- carro visto de cima ------------------------------------------- #
    def _car(self, c, p, ctx, x, y, w, h):
        cx = x + w / 2
        bw, bl = 74.0, h - 40                         # largura e comprimento da carroçaria
        x0, y0 = cx - bw / 2, y + 22
        x1, y1 = x0 + bw, y0 + bl
        dents = p.dents if p.dents else ()
        sev = {z: (dents[i] if i < len(dents) else 0) for i, z in enumerate(ZONES)}
        known = bool(dents)

        def panel_col(zone):
            if not known:
                return (255, 255, 255, 22)
            col = LEVEL.get(min(2, sev[zone]))
            return col or PANEL_IDLE

        def part(pts, zone=None, col=None, glow=False):
            fill = col if col is not None else panel_col(zone)
            if glow and fill[3] > 200:
                xs, ys = [q[0] for q in pts], [q[1] for q in pts]
                T.neon_glow(c, min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys), fill, 0.6)
            c.polygon(pts, fill, stroke=(255, 255, 255, 70), stroke_w=1)

        # aerodinâmica: asa da frente / splitter e asa de trás (mesma % de dano aero)
        aero_col = frac_col(p.aero_damage) if p.aero_damage >= 0 else (255, 255, 255, 22)
        if p.aero_detached:
            aero_col = BAD_COL
        part([(x0 - 8, y0 - 14), (x1 + 8, y0 - 14), (x1 + 4, y0 - 6), (x0 - 4, y0 - 6)], col=aero_col, glow=True)
        part([(x0 - 10, y1 + 8), (x1 + 10, y1 + 8), (x1 + 10, y1 + 16), (x0 - 10, y1 + 16)], col=aero_col, glow=True)
        for sx in (x0 + 10, x1 - 14):                  # suportes da asa de trás
            c.rect(sx, y1, 4, 9, (255, 255, 255, 40))
        # painéis da carroçaria
        fz, rz = bl * 0.30, bl * 0.70                   # fim da frente / início da traseira
        part([(x0 + 18, y0), (x1 - 18, y0), (x1 - 14, y0 + 20), (x0 + 14, y0 + 20)], "f", glow=True)
        part([(x0 + 4, y0 + 6), (x0 + 18, y0), (x0 + 14, y0 + 20), (x0 + 26, y0 + fz), (x0, y0 + fz)], "fl", glow=True)
        part([(x1 - 4, y0 + 6), (x1 - 18, y0), (x1 - 14, y0 + 20), (x1 - 26, y0 + fz), (x1, y0 + fz)], "fr", glow=True)
        part([(x0, y0 + fz), (x0 + 16, y0 + fz), (x0 + 16, y0 + rz), (x0, y0 + rz)], "l", glow=True)
        part([(x1, y0 + fz), (x1 - 16, y0 + fz), (x1 - 16, y0 + rz), (x1, y0 + rz)], "r", glow=True)
        part([(x0, y0 + rz), (x0 + 26, y0 + rz), (x0 + 14, y1 - 18), (x0 + 18, y1), (x0 + 4, y1 - 4)], "rl", glow=True)
        part([(x1, y0 + rz), (x1 - 26, y0 + rz), (x1 - 14, y1 - 18), (x1 - 18, y1), (x1 - 4, y1 - 4)], "rr", glow=True)
        part([(x0 + 14, y1 - 18), (x1 - 14, y1 - 18), (x1 - 18, y1), (x0 + 18, y1)], "b", glow=True)
        # capô, cockpit e motor (sem dados próprios: neutros)
        c.polygon([(x0 + 14, y0 + 20), (x1 - 14, y0 + 20), (x1 - 16, y0 + fz), (x0 + 16, y0 + fz)], (255, 255, 255, 14))
        c.rect(x0 + 18, y0 + fz + 6, bw - 36, bl * 0.2, (8, 10, 14, 200), radius=8, stroke=(255, 255, 255, 50), stroke_w=1)
        c.rect(x0 + 18, y0 + fz + bl * 0.24, bw - 36, rz - fz - bl * 0.26, alpha(T.BAD, 120) if p.overheating
               else (255, 255, 255, 14), radius=4)
        if p.overheating:
            c.text(x0, y0 + fz + bl * 0.24, bw, rz - fz - bl * 0.26, "°C", 11, (255, 255, 255, 255), "c", 800)

        # rodas + suspensão de cada canto
        wl, ww = 32.0, 13.0
        spots = ((x0 - ww - 9, y0 + 14), (x1 + 9, y0 + 14), (x0 - ww - 9, y1 - wl - 12), (x1 + 9, y1 - wl - 12))
        for i, (wx, wy) in enumerate(spots):
            t = p.tyres[i] if i < len(p.tyres) else None
            sd = p.susp_damage[i] if i < len(p.susp_damage) else -1.0
            scol = frac_col(sd) if sd >= 0 else (255, 255, 255, 60)
            ax = x0 if i % 2 == 0 else x1
            ex = wx + ww if i % 2 == 0 else wx
            for dy in (6, wl - 6):                      # braços da suspensão
                c.line(ex, wy + dy, ax, wy + wl / 2 + (dy - wl / 2) * 0.4, scol, 3 if sd > 0.02 else 2)
            if t is not None and t.detached:
                c.rect(wx, wy, ww, wl, None, radius=3, stroke=BAD_COL, stroke_w=1.5)
                c.line(wx + 2, wy + 2, wx + ww - 2, wy + wl - 2, BAD_COL, 2)
                c.line(wx + ww - 2, wy + 2, wx + 2, wy + wl - 2, BAD_COL, 2)
            else:
                tc = BAD_COL if t is not None and t.flat else (34, 36, 42, 255)
                c.rect(wx, wy, ww, wl, tc, radius=3, stroke=(255, 255, 255, 90), stroke_w=1)
            if sd >= 0:                                 # % da suspensão por baixo/cima da roda
                ly = wy - 15 if i < 2 else wy + wl + 2
                c.text(wx - 14, ly, ww + 28, 13, f"{sd * 100:.0f}%", 10, scol if sd > 0.02 else T.DIM, "c", 800)

        # último toque: pisca no centro
        since = ctx.since("impact")
        if p.impact_mag > 0 and since < float(self.cfg["impact_s"]):
            a = int(255 * max(0.0, 1 - since / float(self.cfg["impact_s"])))
            c.ellipse(cx, y0 + bl / 2, 18, 18, None, stroke=alpha(BAD_COL, a), stroke_w=2.5)
            c.ellipse(cx, y0 + bl / 2, 6, 6, alpha(BAD_COL, a))
        if not known:
            c.text(x, y + h - 12, w, 12, tr("dmg.no_body"), 9, T.FAINT, "c", 600)

    # ---- lista detalhada ------------------------------------------------ #
    def _list(self, c, p, ctx, x, y, w, h):
        rows: list = []          # (rótulo, valor, cor) ou ("grid", título, [4 x (valor, cor)])
        if p.dents:
            names = [tr(f"dmg.z.{z}") for z in ZONES]
            hit = [(n, d) for n, d in zip(names, p.dents) if d]
            if hit:
                for n, d in sorted(hit, key=lambda e: -e[1])[:4]:
                    rows.append((n, tr("dmg.sev2") if d >= 2 else tr("dmg.sev1"), BAD_COL if d >= 2 else WARN_COL))
            else:
                rows.append((tr("dmg.body"), tr("dmg.ok_short"), T.GOOD))
        if p.aero_damage >= 0 or p.aero_detached:
            val = f"{max(0.0, p.aero_damage) * 100:.0f}%" + (f" · {tr('dmg.loose')}" if p.aero_detached else "")
            rows.append((tr("dmg.aero"), val, BAD_COL if p.aero_detached else frac_col(p.aero_damage)))
        elif p.aero_detached:
            rows.append((tr("dmg.aero"), tr("dmg.loose"), BAD_COL))
        if any(s >= 0 for s in p.susp_damage):
            rows.append(("grid", tr("dmg.susp"), [(f"{max(0.0, s) * 100:.0f}%", frac_col(s)) for s in p.susp_damage]))
        if any(b >= 0 for b in p.brake_wear):
            rows.append(("grid", tr("dmg.brakes"), [(f"{max(0.0, b) * 100:.0f}%", frac_col(b)) for b in p.brake_wear]))
        tyre_bad = [(WHEELS[i], t) for i, t in enumerate(p.tyres[:4]) if t.flat or t.detached]
        rows.append((tr("dmg.tyres"), ", ".join(f"{n} {tr('dmg.lost_s') if t.detached else tr('dmg.flat_s')}"
                                                 for n, t in tyre_bad) or tr("dmg.ok_short"),
                     BAD_COL if tyre_bad else T.GOOD))
        eng = [txt for bit, txt in ((1, tr("dmg.hot")), (2, tr("dmg.hot")), (4, tr("dmg.oil_p")),
                                    (8, tr("dmg.fuel_p")), (16, tr("dmg.stalled"))) if p.warnings & bit]
        eng = list(dict.fromkeys(eng))
        rows.append((tr("dmg.engine"), ", ".join(eng) if eng else tr("dmg.ok_short"),
                     (BAD_COL if p.warnings & 28 else WARN_COL) if eng else T.GOOD))
        for k, v in list(p.extra_damage.items())[:2]:
            rows.append((k.capitalize(), f"{v * 100:.0f}%", frac_col(v)))
        if p.repair_req >= 0 or p.repair_opt >= 0:
            req, opt = max(0.0, p.repair_req), max(0.0, p.repair_opt)
            rows.append((tr("dmg.repair"), tr("dmg.repair_t", a=f"{req:.0f}", b=f"{opt:.0f}") if req or opt
                         else tr("dmg.ok_short"), BAD_COL if req > 0 else (WARN_COL if opt > 0 else T.GOOD)))
        since = ctx.since("impact")
        if p.impact_mag > 0 and since < 600:
            rows.append((tr("dmg.impact"), tr("dmg.ago", s=f"{since:.0f}"),
                         WARN_COL if since < float(self.cfg["impact_s"]) else T.DIM))

        units = sum(2 if r[0] == "grid" else 1 for r in rows)
        rh = min(23.0, h / max(1, units))
        yy = y
        for r in rows:
            if r[0] == "grid":
                _g, title, vals = r
                c.text(x + 4, yy, w * 0.4, rh * 2, title, 12, T.DIM, "l", 600)
                cw = (w - w * 0.43) / 2
                for i, (val, col) in enumerate(vals):
                    gx = x + w * 0.43 + (i % 2) * cw
                    gy = yy + (i // 2) * rh
                    c.rect(gx + 1, gy + 2, cw - 3, rh - 4, alpha(col, 30), radius=3)
                    c.text(gx + 4, gy, 24, rh, WHEELS[i], 9, T.FAINT, "l", 700)
                    c.text(gx + 4, gy, cw - 10, rh, val, 12, col, "r", 800)
                yy += 2 * rh
                continue
            lab, val, col = r
            c.rect(x, yy + 2, w, rh - 4, alpha(col, 22), radius=3)
            c.rect(x, yy + 4, 3, rh - 8, col, radius=1.5)
            c.text(x + 10, yy, w * 0.5, rh, lab, 12, T.DIM, "l", 600)
            c.text(x + w * 0.42, yy, w * 0.58 - 8, rh, val, 12, col if col is not T.GOOD else T.TEXT, "r", 800)
            yy += rh
