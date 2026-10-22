"""Interface de desenho independente da biblioteca gráfica.

Os overlays desenham sempre em "unidades base" (px a escala 1.0). Cada
backend (Qt na app real, Pillow para pré-visualizações/testes) aplica a escala.
Cores: tuplos (r, g, b) ou (r, g, b, a) com 0..255.
"""

from __future__ import annotations

from typing import Protocol, Sequence

Color = tuple


class Canvas(Protocol):
    def rect(self, x: float, y: float, w: float, h: float, fill: Color | None = None,
             radius: float = 0, stroke: Color | None = None, stroke_w: float = 1.0,
             fill2: Color | None = None, horizontal: bool = False) -> None:
        """Retângulo (arredondado). Com fill2 faz um gradiente fill->fill2 (vertical por defeito)."""

    def line(self, x1: float, y1: float, x2: float, y2: float, color: Color, width: float = 1.0) -> None: ...

    def polyline(self, pts: Sequence[tuple[float, float]], color: Color, width: float = 1.0,
                 closed: bool = False) -> None: ...

    def polygon(self, pts: Sequence[tuple[float, float]], fill: Color | None = None,
                stroke: Color | None = None, stroke_w: float = 1.0) -> None: ...

    def ellipse(self, cx: float, cy: float, rx: float, ry: float, fill: Color | None = None,
                stroke: Color | None = None, stroke_w: float = 1.0) -> None: ...

    def text(self, x: float, y: float, w: float, h: float, s: str, size: float, color: Color,
             align: str = "l", weight: int = 400, spacing: float = 0.0, italic: bool = False) -> None:
        """Texto numa caixa, centrado na vertical. align: l/c/r. Corta com '…' se não couber.
        italic=True inclina o texto (feito com uma transformação, não precisa de fonte itálica)."""

    def measure(self, s: str, size: float, weight: int = 400, spacing: float = 0.0) -> float: ...

    def image(self, path: str, cx: float, cy: float, size: float, angle: float = 0.0, box=None) -> None:
        """Imagem (PNG) centrada em (cx, cy), a caber num quadrado `size` (ou no retângulo box=(w, h)),
        rodada `angle` graus."""

    def mark_static(self) -> None:
        """Tudo o que foi desenhado até aqui é fundo que raramente muda: a app guarda-o numa imagem
        e só redesenha o que vem depois. É só uma otimização; desenhar sem isto dá o mesmo resultado."""


def rgba(c: Color, a: int | None = None) -> tuple[int, int, int, int]:
    if len(c) == 4 and a is None:
        return tuple(int(v) for v in c)  # type: ignore[return-value]
    return (int(c[0]), int(c[1]), int(c[2]), 255 if a is None else int(a))


def alpha(c: Color, a: int) -> tuple[int, int, int, int]:
    return (int(c[0]), int(c[1]), int(c[2]), int(max(0, min(255, a))))


def hex_color(h: str, a: int = 255) -> tuple[int, int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def mix(a: Color, b: Color, t: float) -> tuple[int, int, int, int]:
    a, b = rgba(a), rgba(b)
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(4))  # type: ignore[return-value]


def scale_rgb(c: Color, k: float) -> tuple[int, int, int, int]:
    c = rgba(c)
    return (int(min(255, c[0] * k)), int(min(255, c[1] * k)), int(min(255, c[2] * k)), c[3])
