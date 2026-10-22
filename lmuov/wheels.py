"""Volantes desenhados para o Input Graphics: normal, GT, Fórmula 1, camião e barco.

Todos rodam com o ângulo do volante (positivo = para a direita, sentido dos ponteiros)."""

from __future__ import annotations

import math

from . import theme as T
from .canvas import alpha

STYLES = ("simple", "normal", "gt", "formula", "f1", "old_school", "rally", "truck", "boat", "custom")
RIM = (232, 235, 241, 225)
GRIP = (34, 36, 42, 255)
WOOD = (176, 116, 58, 255)
WOOD_DARK = (120, 74, 34, 255)


def _rot(cx, cy, a):
    ca, sa = math.cos(a), math.sin(a)

    def f(x, y):
        return cx + x * ca - y * sa, cy + x * sa + y * ca
    return f


def _poly(rot, pts):
    return [rot(x, y) for x, y in pts]


def _spoke(c, rot, x0, y0, x1, y1, col, w):
    (ax, ay), (bx, by) = rot(x0, y0), rot(x1, y1)
    c.line(ax, ay, bx, by, col, w)


def _arc(cx, cy, r, a0, a1, n=24):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def draw_wheel(c, cx, cy, r, a, style="normal", accent=None, image=None, gear=None, speed=None, rpm=None):
    """Volante em (cx, cy), raio r, rodado `a` radianos.

    style "simple": anel com as RPM, a mudança e a velocidade lá dentro (gear/speed/rpm 0..1).
    style "custom": a imagem PNG em `image` (a foto do teu volante), rodada."""
    acc = accent or T.ACCENT
    rot = _rot(cx, cy, a)
    if style == "custom":
        if image:
            c.image(image, cx, cy, 2 * r, math.degrees(a))
            return
        style = "normal"
    if style == "simple":
        c.ellipse(cx, cy, r, r, (12, 14, 18, 200), stroke=(255, 255, 255, 40), stroke_w=4)
        if rpm is not None and rpm > 0:
            f = max(0.0, min(1.0, rpm))
            col = (40, 222, 110, 255) if f < 0.85 else ((255, 196, 36, 255) if f < 0.95 else (255, 66, 78, 255))
            c.polyline(_arc(cx, cy, r, 135, 135 + 270 * f), col, 3.5)
        mx, my = rot(0, -r)
        c.ellipse(mx, my, 3.2, 3.2, (255, 255, 255, 255))
        if gear is not None:
            c.text(cx - r, cy - r * 0.62, 2 * r, r, gear, r * 0.78, (255, 255, 255, 255), "c", 800)
        if speed is not None:
            c.text(cx - r, cy + r * 0.12, 2 * r, r * 0.45, speed, r * 0.36, T.DIM, "c", 700)
        return
    if style == "formula":                              # volante de fórmula simples (silhueta)
        shape = [(-1.0, -0.42), (-0.55, -0.6), (0.55, -0.6), (1.0, -0.42), (1.0, 0.35), (0.72, 0.62),
                 (0.36, 0.48), (-0.36, 0.48), (-0.72, 0.62), (-1.0, 0.35)]
        c.polygon(_poly(rot, [(x * r, y * r) for x, y in shape]), (150, 156, 168, 255), stroke=(255, 255, 255, 110),
                  stroke_w=1.2)
        c.polygon(_poly(rot, [(-0.42 * r, -0.36 * r), (0.42 * r, -0.36 * r), (0.42 * r, 0.22 * r),
                              (-0.42 * r, 0.22 * r)]), (24, 26, 32, 255))
        for sx in (-1, 1):
            c.polygon(_poly(rot, [(sx * 0.66 * r, -0.3 * r), (sx * 0.9 * r, -0.3 * r), (sx * 0.9 * r, 0.25 * r),
                                  (sx * 0.66 * r, 0.25 * r)]), (40, 42, 50, 255))
        _spoke(c, rot, -0.12 * r, -0.6 * r, 0.12 * r, -0.6 * r, acc, 3)
        return
    if style == "old_school":                           # aro fino e três raios finos
        c.ellipse(cx, cy, r, r, None, stroke=(30, 32, 38, 255), stroke_w=4)
        c.ellipse(cx, cy, r, r, None, stroke=(200, 204, 214, 255), stroke_w=2.2)
        for t in (200, 340, 90):
            tt = math.radians(t)
            _spoke(c, rot, 0.2 * r * math.cos(tt), 0.2 * r * math.sin(tt), r * math.cos(tt), r * math.sin(tt),
                   (176, 182, 194, 255), 2)
        c.ellipse(cx, cy, 0.2 * r, 0.2 * r, (70, 74, 84, 255), stroke=(255, 255, 255, 90), stroke_w=1)
    elif style == "rally":                              # volante de rali: aro grosso, raios com furos
        c.ellipse(cx, cy, r, r, None, stroke=(26, 28, 34, 255), stroke_w=7)
        c.ellipse(cx, cy, r, r, None, stroke=(120, 126, 138, 255), stroke_w=4)
        c.ellipse(cx, cy, 0.72 * r, 0.72 * r, None, stroke=(70, 74, 84, 255), stroke_w=1.5)
        for t in (180, 0, 90):
            tt = math.radians(t)
            _spoke(c, rot, 0.25 * r * math.cos(tt), 0.25 * r * math.sin(tt), 0.95 * r * math.cos(tt),
                   0.95 * r * math.sin(tt), (150, 156, 168, 255), 6)
            for k in (0.45, 0.7):
                x, y = rot(k * r * math.cos(tt), k * r * math.sin(tt))
                c.ellipse(x, y, 1.6, 1.6, (20, 22, 26, 255))
        c.ellipse(cx, cy, 0.27 * r, 0.27 * r, (60, 64, 74, 255), stroke=(255, 255, 255, 80), stroke_w=1.2)
    elif style == "gt":                                   # aro em D (fundo plano), placa com botões
        pts = [(r * math.cos(math.radians(t)), r * math.sin(math.radians(t))) for t in range(160, 381, 12)]
        pts.append((r * math.cos(math.radians(20)), r * math.sin(math.radians(20))))
        c.polyline(_poly(rot, pts), RIM, 5, closed=True)
        for sx in (-1, 1):
            _spoke(c, rot, sx * 0.25 * r, 0.05 * r, sx * 0.9 * r, -0.05 * r, (190, 194, 204, 255), 5)
        c.polygon(_poly(rot, [(-0.3 * r, -0.2 * r), (0.3 * r, -0.2 * r), (0.38 * r, 0.3 * r), (-0.38 * r, 0.3 * r)]),
                  GRIP, stroke=(255, 255, 255, 60), stroke_w=1)
        for (bx, by), col in (((-0.18, 0.0), (255, 70, 80, 255)), ((0.18, 0.0), (60, 160, 255, 255)),
                              ((0.0, 0.15), (255, 196, 36, 255))):
            x, y = rot(bx * r, by * r)
            c.ellipse(x, y, 2.2, 2.2, col)
    elif style == "f1":                                 # volante retangular com pegas e ecrã
        body = [(-0.95, -0.35), (-0.6, -0.55), (0.6, -0.55), (0.95, -0.35), (0.95, 0.45), (0.6, 0.62), (-0.6, 0.62),
                (-0.95, 0.45)]
        for sx in (-1, 1):
            c.polygon(_poly(rot, [(sx * 0.82 * r, -0.42 * r), (sx * 1.18 * r, -0.38 * r), (sx * 1.18 * r, 0.5 * r),
                                  (sx * 0.82 * r, 0.56 * r)]), GRIP, stroke=(255, 255, 255, 70), stroke_w=1)
        c.polygon(_poly(rot, [(x * r, y * r) for x, y in body]), (52, 56, 66, 255), stroke=(255, 255, 255, 90),
                  stroke_w=1.2)
        c.polygon(_poly(rot, [(-0.36 * r, -0.32 * r), (0.36 * r, -0.32 * r), (0.36 * r, 0.12 * r),
                              (-0.36 * r, 0.12 * r)]), (8, 10, 14, 255), stroke=alpha(acc, 160), stroke_w=1)
        for i in range(5):                              # luzes de mudança
            x, y = rot((-0.32 + i * 0.16) * r, -0.45 * r)
            c.ellipse(x, y, 1.6, 1.6, ((40, 222, 110, 255), (40, 222, 110, 255), (255, 196, 36, 255),
                                       (255, 70, 80, 255), (60, 120, 255, 255))[i])
        for bx, by in ((-0.62, 0.0), (0.62, 0.0), (-0.62, 0.3), (0.62, 0.3), (-0.2, 0.38), (0.2, 0.38)):
            x, y = rot(bx * r, by * r)
            c.ellipse(x, y, 2.0, 2.0, (200, 205, 215, 255))
        _spoke(c, rot, -0.1 * r, -0.62 * r, 0.1 * r, -0.62 * r, acc, 3)
        return
    elif style == "truck":                              # aro grande e fino, 4 raios, centro largo
        c.ellipse(cx, cy, r, r, None, stroke=(30, 32, 38, 255), stroke_w=4.5)
        c.ellipse(cx, cy, r, r, None, stroke=RIM, stroke_w=2.2)
        for t in (35, 145, 215, 325):
            tt = math.radians(t)
            _spoke(c, rot, 0.34 * r * math.cos(tt), 0.34 * r * math.sin(tt), r * math.cos(tt), r * math.sin(tt),
                   (190, 194, 204, 255), 2.5)
        c.ellipse(cx, cy, 0.36 * r, 0.36 * r, (60, 64, 74, 255), stroke=(255, 255, 255, 80), stroke_w=1.2)
        c.ellipse(cx, cy, 0.18 * r, 0.18 * r, (90, 96, 108, 255))
    elif style == "boat":                               # roda de leme: 8 raios com punhos de madeira
        rr = r * 0.74
        for k in range(8):
            t = math.radians(-90 + k * 45)
            _spoke(c, rot, 0, 0, 1.3 * rr * math.cos(t), 1.3 * rr * math.sin(t), WOOD_DARK, 3)
            x, y = rot(1.3 * rr * math.cos(t), 1.3 * rr * math.sin(t))
            c.ellipse(x, y, 3.2, 3.2, acc if k == 0 else WOOD, stroke=(0, 0, 0, 120), stroke_w=1)
        c.ellipse(cx, cy, rr, rr, None, stroke=WOOD_DARK, stroke_w=5)
        c.ellipse(cx, cy, rr, rr, None, stroke=WOOD, stroke_w=3)
        c.ellipse(cx, cy, 0.26 * rr, 0.26 * rr, WOOD, stroke=WOOD_DARK, stroke_w=1.5)
        return
    else:                                               # normal: aro redondo, 3 raios
        c.ellipse(cx, cy, r, r, None, stroke=RIM, stroke_w=5)
        for x1, y1 in ((-r, 0.0), (r, 0.0), (0.0, r)):
            _spoke(c, rot, 0, 0, x1 * 0.92, y1 * 0.92, (190, 194, 204, 255), 4)
        c.ellipse(cx, cy, 0.3 * r, 0.3 * r, (60, 64, 74, 255), stroke=(255, 255, 255, 80), stroke_w=1.2)
    # marca do centro (no topo do aro)
    mx, my = rot(0, -r)
    c.ellipse(mx, my, 3.4, 3.4, acc)
