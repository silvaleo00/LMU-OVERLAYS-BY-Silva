"""Backend Pillow: desenha os overlays para imagens (testes e pré-visualizações).

Não é usado pela app em si; serve para verificar o aspeto sem abrir janelas.
Usa a mesma fonte embutida que a app, por isso o resultado é muito próximo.
    python run.py --preview  ->  previews/*.png com dados do modo demo
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features

from .canvas import rgba
from .paths import resource

WEIGHTS = {400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold", 800: "ExtraBold"}
_RAQM = features.check("raqm")


def _font_path(weight: int) -> str | None:
    name = WEIGHTS[min(WEIGHTS, key=lambda k: abs(k - weight))]
    p = resource(f"assets/fonts/BarlowSemiCondensed-{name}.ttf")
    if p.exists():
        return str(p)
    for cand in ("C:/Windows/Fonts/bahnschrift.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(cand).exists():
            return cand
    return None


class PILCanvas:
    def __init__(self, w: int, h: int, scale: float = 1.0, ss: int = 3) -> None:
        self.k = scale * ss
        self.ss = ss
        self.img = Image.new("RGBA", (max(1, int(w * self.k)), max(1, int(h * self.k))), (0, 0, 0, 0))
        self._fonts: dict = {}

    def _f(self, size, weight):
        key = (round(size * self.k), weight)
        if key not in self._fonts:
            path = _font_path(weight)
            self._fonts[key] = ImageFont.truetype(path, key[0]) if path else ImageFont.load_default()
        return self._fonts[key]

    def _layer(self, x0, y0, x1, y1):
        """Desenha numa camada do tamanho da forma e compõe por cima (alpha correto)."""
        pad = 4
        bx, by = int(max(0, x0 - pad)), int(max(0, y0 - pad))
        bw = max(1, int(min(self.img.size[0], x1 + pad)) - bx)
        bh = max(1, int(min(self.img.size[1], y1 + pad)) - by)
        layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        return layer, ImageDraw.Draw(layer), bx, by

    def _commit(self, layer, bx, by):
        self.img.alpha_composite(layer, (bx, by))

    def result(self) -> Image.Image:
        w, h = self.img.size
        return self.img.resize((max(1, round(w / self.ss)), max(1, round(h / self.ss))), Image.LANCZOS)

    # --- Canvas API ------------------------------------------------------- #
    def rect(self, x, y, w, h, fill=None, radius=0, stroke=None, stroke_w=1.0, fill2=None, horizontal=False):
        if w <= 0 or h <= 0:
            return
        k = self.k
        x0, y0, x1, y1 = x * k, y * k, (x + w) * k - 1, (y + h) * k - 1
        if x1 <= x0 or y1 <= y0:
            return
        layer, d, bx, by = self._layer(x0, y0, x1, y1)
        r = max(0, min(radius * k, (x1 - x0) / 2, (y1 - y0) / 2))
        box = [x0 - bx, y0 - by, x1 - bx, y1 - by]
        if fill2 is not None and fill is not None:
            gw, gh = max(1, int(x1 - x0 + 1)), max(1, int(y1 - y0 + 1))
            a, b = rgba(fill), rgba(fill2)
            n = 64
            strip = Image.new("RGBA", (n, 1) if horizontal else (1, n))
            strip.putdata([tuple(int(a[j] + (b[j] - a[j]) * i / (n - 1)) for j in range(4)) for i in range(n)])
            grad = strip.resize((gw, gh), Image.BILINEAR)
            mask = Image.new("L", layer.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle(box, radius=r, fill=255)
            full = Image.new("RGBA", layer.size, (0, 0, 0, 0))
            full.paste(grad, (int(box[0]), int(box[1])))
            layer.paste(full, (0, 0), mask)
            d = ImageDraw.Draw(layer)
            if stroke:
                d.rounded_rectangle(box, radius=r, outline=rgba(stroke), width=max(1, round(stroke_w * k)))
        else:
            d.rounded_rectangle(box, radius=r, fill=rgba(fill) if fill else None,
                                outline=rgba(stroke) if stroke else None,
                                width=max(1, round(stroke_w * k)) if stroke else 0)
        self._commit(layer, bx, by)

    def line(self, x1, y1, x2, y2, color, width=1.0):
        self.polyline([(x1, y1), (x2, y2)], color, width)

    def polyline(self, pts, color, width=1.0, closed=False):
        if len(pts) < 2:
            return
        k = self.k
        wd = max(1, round(width * k))
        P = [(px * k, py * k) for px, py in pts]
        if closed:
            P.append(P[0])
        xs, ys = [p[0] for p in P], [p[1] for p in P]
        layer, d, bx, by = self._layer(min(xs) - wd, min(ys) - wd, max(xs) + wd, max(ys) + wd)
        d.line([(px - bx, py - by) for px, py in P], fill=rgba(color), width=wd, joint="curve")
        r = wd / 2
        for px, py in (P[0], P[-1]):  # pontas redondas
            d.ellipse([px - bx - r, py - by - r, px - bx + r, py - by + r], fill=rgba(color))
        self._commit(layer, bx, by)

    def polygon(self, pts, fill=None, stroke=None, stroke_w=1.0):
        k = self.k
        xs, ys = [p[0] * k for p in pts], [p[1] * k for p in pts]
        layer, d, bx, by = self._layer(min(xs), min(ys), max(xs), max(ys))
        d.polygon([(px - bx, py - by) for px, py in zip(xs, ys)], fill=rgba(fill) if fill else None,
                  outline=rgba(stroke) if stroke else None)
        self._commit(layer, bx, by)

    def ellipse(self, cx, cy, rx, ry, fill=None, stroke=None, stroke_w=1.0):
        k = self.k
        x0, y0, x1, y1 = (cx - rx) * k, (cy - ry) * k, (cx + rx) * k, (cy + ry) * k
        layer, d, bx, by = self._layer(x0, y0, x1, y1)
        d.ellipse([x0 - bx, y0 - by, x1 - bx, y1 - by], fill=rgba(fill) if fill else None,
                  outline=rgba(stroke) if stroke else None, width=max(1, round(stroke_w * k)) if stroke else 0)
        self._commit(layer, bx, by)

    def mark_static(self) -> None:
        pass

    def image(self, path, cx, cy, size, angle=0.0, box=None):
        try:
            im = Image.open(path).convert("RGBA")
        except Exception:
            return
        bw, bh = box if box else (size, size)
        im.thumbnail((max(1, int(bw * self.k)), max(1, int(bh * self.k))), Image.LANCZOS)
        im = im.rotate(-angle, resample=Image.BICUBIC, expand=True)
        layer = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        layer.paste(im, (int(cx * self.k - im.size[0] / 2), int(cy * self.k - im.size[1] / 2)), im)
        self.img.alpha_composite(layer)

    def _len(self, f, s, spacing):
        kw = {"features": ["tnum"]} if _RAQM else {}
        return f.getlength(s, **kw) + spacing * self.k * max(0, len(s) - 1)

    def measure(self, s, size, weight=400, spacing=0.0):
        return self._len(self._f(size, weight), s, spacing) / self.k

    def text(self, x, y, w, h, s, size, color, align="l", weight=400, spacing=0.0, italic=False):
        if not s:
            return
        f = self._f(size, weight)
        k = self.k
        maxw = w * k
        if self._len(f, s, spacing) > maxw:
            while s and self._len(f, s + "…", spacing) > maxw:
                s = s[:-1]
            s = s + "…"
        tw = self._len(f, s, spacing)
        x0 = {"l": x * k, "c": (x + w / 2) * k - tw / 2, "r": (x + w) * k - tw}[align]
        cy = (y + h / 2) * k
        ext = 0.3 * size * k if italic else 0
        layer, d, bx, by = self._layer(x0 - 4 - ext, y * k - size * k, x0 + tw + 4 + ext, (y + h) * k + size * k)
        kw = {"features": ["tnum"]} if _RAQM else {}
        from . import theme
        passes = [(rgba(color), 0.0)]
        if theme.SKIN.get("text_shadow"):     # estilo HUD: sombra por baixo do texto
            passes.insert(0, ((0, 0, 0, int(rgba(color)[3] * 0.85)), 1.2 * k))
        for col, off in passes:
            if spacing:
                px = x0
                for ch in s:
                    d.text((px - bx + off, cy - by + off), ch, font=f, fill=col, anchor="lm", **kw)
                    px += f.getlength(ch, **kw) + spacing * k
            else:
                d.text((x0 - bx + off, cy - by + off), s, font=f, fill=col, anchor="lm", **kw)
        if italic:   # inclina a camada à volta do centro vertical (como o shear do Qt)
            sh = 0.2
            ly = cy - by
            layer = layer.transform(layer.size, Image.AFFINE, (1, sh, -sh * ly, 0, 1, 0), Image.BICUBIC)
        self._commit(layer, bx, by)


class _Offset:
    """Desloca todas as coordenadas (para deixar margem ao brilho néon)."""

    def __init__(self, c, d):
        self.c, self.d = c, d

    def rect(self, x, y, *a, **k):
        self.c.rect(x + self.d, y + self.d, *a, **k)

    def line(self, x1, y1, x2, y2, *a, **k):
        self.c.line(x1 + self.d, y1 + self.d, x2 + self.d, y2 + self.d, *a, **k)

    def polyline(self, pts, *a, **k):
        self.c.polyline([(x + self.d, y + self.d) for x, y in pts], *a, **k)

    def polygon(self, pts, *a, **k):
        self.c.polygon([(x + self.d, y + self.d) for x, y in pts], *a, **k)

    def ellipse(self, cx, cy, *a, **k):
        self.c.ellipse(cx + self.d, cy + self.d, *a, **k)

    def text(self, x, y, *a, **k):
        self.c.text(x + self.d, y + self.d, *a, **k)

    def measure(self, *a, **k):
        return self.c.measure(*a, **k)

    def mark_static(self) -> None:
        self.c.mark_static()

    def image(self, path, cx, cy, *a, **k):
        self.c.image(path, cx + self.d, cy + self.d, *a, **k)


def pad() -> int:
    from . import theme
    return theme.NEON_PAD if theme.NEON else 0


def render(overlay, snap, ctx, scale: float = 1.5) -> Image.Image:
    """Imagem do overlay com margem pad() à volta (o conteúdo começa em (pad, pad))."""
    w, h = overlay.size(snap, ctx)
    p = pad()
    c = PILCanvas(w + 2 * p, h + 2 * p, scale)
    overlay.draw(_Offset(c, p) if p else c, snap, ctx, w, h)
    return c.result()


def backdrop(w: int, h: int) -> Image.Image:
    """Fundo tipo 'jogo' (céu, pista) para avaliar a legibilidade."""
    img = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(img)
    for yy in range(h):
        t = yy / h
        if t < 0.45:
            col = (int(120 + 60 * t), int(160 + 50 * t), int(200 + 30 * t), 255)
        else:
            u = (t - 0.45) / 0.55
            col = (int(70 - 30 * u), int(74 - 30 * u), int(78 - 30 * u), 255)
        d.line([(0, yy), (w, yy)], fill=col)
    d.polygon([(w * 0.42, h * 0.45), (w * 0.58, h * 0.45), (w * 0.95, h), (w * 0.05, h)], fill=(52, 54, 58, 255))
    d.polygon([(w * 0.495, h * 0.45), (w * 0.505, h * 0.45), (w * 0.52, h), (w * 0.48, h)], fill=(230, 230, 230, 255))
    return img


def main(out_dir: str = "previews") -> None:
    from .overlays import ALL
    from .source_demo import DemoSource
    from .trackers import Trackers

    out = Path(out_dir)
    out.mkdir(exist_ok=True)
    demo = DemoSource()
    tr = Trackers(None)
    snap = ctx = None
    for _ in range(2400):  # ~8 min simulados para os trackers (mapa, consumo, delta) terem histórico
        demo.step(0.2)
        snap = demo.snapshot()
        ctx = tr.update(snap, now=demo.t)
    for cls in ALL:
        ov = cls()
        render(ov, snap, ctx).save(out / f"{ov.key}.png")
    print("ok", out.resolve())


if __name__ == "__main__":
    main(*sys.argv[1:])
