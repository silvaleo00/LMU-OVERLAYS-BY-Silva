"""Track Map: o traçado (gravado na tua primeira volta completa) com todos os carros."""

from __future__ import annotations

import bisect
import math

from .. import theme as T
from ..canvas import alpha
from ..i18n import tr
from .base import Overlay


class TrackMapOverlay(Overlay):
    key = "track_map"
    defaults = {"size": 290, "mirror": False, "show_pit_cars": True}
    default_pos = (1610, 16)

    smart_capable = True
    default_mode = "auto"

    def auto_visible(self, snap, ctx):
        """Com amarelas / FCY, nas boxes, no início e logo depois de cada volta."""
        s = snap.session
        if s.phase in (6, 7) or any(f == 1 for f in s.sector_flags) or snap.me.in_pits:
            return True
        return ctx.since("start") < 20 or ctx.since("lap") < 8 or ctx.track_map is None

    def size(self, snap, ctx):
        s = int(self.cfg["size"])
        return (s, s)

    _geo_key = None
    _geo = None

    def _geometry(self, tm, ax, ay, aw, ah):
        """Escala do mapa e pontos do traçado no ecrã. Calculado uma vez (não a cada frame) e com
        os pontos reduzidos a ~1.5 px de distância (uma volta a Le Mans tem milhares de pontos)."""
        flip = -1 if self.cfg["mirror"] else 1
        key = (id(tm), len(tm.pts), ax, ay, aw, ah, flip)
        if key == self._geo_key:
            return self._geo
        xs = [p[1] * flip for p in tm.pts]
        ys = [-p[2] for p in tm.pts]
        minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
        pad = 12
        k = min((aw - 2 * pad) / max(1.0, maxx - minx), (ah - 2 * pad) / max(1.0, maxy - miny))
        ox = ax + aw / 2 - (minx + maxx) / 2 * k
        oy = ay + ah / 2 - (miny + maxy) / 2 * k
        pts, dists = [], []
        for raw in tm.pts:
            x, y = ox + raw[1] * flip * k, oy - raw[2] * k
            if pts and (x - pts[-1][0]) ** 2 + (y - pts[-1][1]) ** 2 < 2.25 and raw is not tm.pts[-1]:
                continue
            pts.append((x, y))
            dists.append(raw[0])
        self._geo_key = key
        self._geo = (flip, k, ox, oy, tuple(pts), tuple(dists))
        return self._geo

    @staticmethod
    def _on_track(pts, dists, d):
        """Ponto do traçado (no ecrã) à distância d da meta."""
        i = bisect.bisect_right(dists, d)
        if i <= 0:
            return pts[0]
        if i >= len(dists):
            return pts[-1]
        d0, d1 = dists[i - 1], dists[i]
        t = (d - d0) / (d1 - d0) if d1 > d0 else 0.0
        (x0, y0), (x1, y1) = pts[i - 1], pts[i]
        return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t

    def render(self, c, snap, ctx, w, h):
        y0 = T.panel(c, w, h, self.title, snap.session.track[:28])
        ax, ay, aw, ah = 10, y0 + 2, w - 20, h - y0 - 12
        tm = ctx.track_map
        if tm is None or len(tm.pts) < 10:
            self._placeholder(c, snap, ctx, ax, ay, aw, ah)
            return
        flip, k, ox, oy, pts, dists = self._geometry(tm, ax, ay, aw, ah)

        def scr(x, z):
            return ox + x * flip * k, oy + (-z) * k

        if T.NEON:
            c.polyline(pts, alpha(T.ACCENT, 28), 16, closed=True)
            c.polyline(pts, alpha(T.ACCENT, 60), 11, closed=True)
        c.polyline(pts, (0, 0, 0, 120), 10, closed=True)
        c.polyline(pts, (255, 255, 255, 40), 8, closed=True)
        c.polyline(pts, (226, 231, 239, 235), 3.2, closed=True)

        # setores com amarela
        s = snap.session
        if len(tm.sectors) >= 2 and any(f == 1 for f in s.sector_flags):
            bounds = [0.0, tm.sectors[0], tm.sectors[1], tm.length]
            for sec in range(3):
                if s.sector_flags[sec] == 1:
                    seg = [pp for pp, dd in zip(pts, dists) if bounds[sec] <= dd < bounds[sec + 1]]
                    if len(seg) > 1:
                        c.polyline(seg, T.WARN, 5)
        # meta
        (x0, y0_), (x1, y1_) = pts[0], pts[1]
        dx, dy = x1 - x0, y1_ - y0_
        n = math.hypot(dx, dy) or 1
        px, py = -dy / n * 8, dx / n * 8
        c.line(x0 - px, y0_ - py, x0 + px, y0_ + py, T.ACCENT, 3)
        c.mark_static()                      # o traçado fica em cache; só os carros se mexem

        # carros (o teu por cima). Sem posições no mundo (iRacing): pela distância na volta.
        if snap.world_pos:
            def where(v):
                return scr(v.pos[0], v.pos[2])
        else:
            def where(v):
                return self._on_track(pts, dists, v.lap_dist)
        others = [v for v in snap.vehicles if not v.is_player and not v.in_garage
                  and (self.cfg["show_pit_cars"] or not v.in_pits)]
        for v in sorted(others, key=lambda v: -v.place):
            x, yy = where(v)
            _, ccol = T.class_info(v.cls)
            a = 110 if v.in_pits else 255
            c.ellipse(x, yy, 5.5, 5.5, alpha(ccol, a), stroke=(0, 0, 0, int(a * 0.7)), stroke_w=1.5)
        me = snap.me
        x, yy = scr(snap.player.pos[0], snap.player.pos[2]) if snap.world_pos else self._on_track(pts, dists, snap.my_lap_dist())
        c.ellipse(x, yy, 17, 17, alpha(T.ME, 28 if T.NEON else 0))
        c.ellipse(x, yy, 12, 12, alpha(T.ME, 55))
        c.ellipse(x, yy, 7, 7, T.ME, stroke=(255, 255, 255, 255), stroke_w=2)
        c.text(x - 20, yy - 24, 40, 12, f"P{me.class_place}", 10, T.ME, "c", 800)

    def _placeholder(self, c, snap, ctx, ax, ay, aw, ah):
        """Sem mapa ainda: carros numa pista circular pela distância na volta."""
        cx, cy = ax + aw / 2, ay + ah / 2
        r = min(aw, ah) / 2 - 18
        c.ellipse(cx, cy, r, r, None, stroke=(255, 255, 255, 40), stroke_w=7)
        L = snap.session.track_length or 1
        for v in sorted(snap.vehicles, key=lambda v: v.is_player):
            if v.in_garage:
                continue
            a = 2 * math.pi * (v.lap_dist / L) - math.pi / 2
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            if v.is_player:
                c.ellipse(x, y, 7, 7, T.ME, stroke=(255, 255, 255, 255), stroke_w=2)
            else:
                _, ccol = T.class_info(v.cls)
                c.ellipse(x, y, 5, 5, alpha(ccol, 110 if v.in_pits else 255))
        c.text(ax, cy - 22, aw, 20, tr("map.recording"), 13, T.TEXT, "c", 700)
        c.text(ax, cy, aw, 18, tr("map.recording_hint", p=int(ctx.map_progress * 100)), 12, T.DIM, "c", 500)
