"""Linguagem visual: cores, classes, formatação e peças de desenho partilhadas.

Estilo "broadcast": vidro escuro com gradiente, fonte condensada, etiquetas
inclinadas na cor da classe e um destaque âmbar para o teu carro.
"""

from __future__ import annotations

from .canvas import alpha, hex_color, mix, scale_rgb  # noqa: F401

# --- cores base --------------------------------------------------------------
BG_TOP = (26, 30, 39, 238)
BG_BOT = (9, 11, 15, 238)
EDGE = (255, 255, 255, 22)
SHEEN = (255, 255, 255, 14)
TEXT = (242, 245, 249, 255)
DIM = (156, 165, 180, 255)
FAINT = (98, 106, 121, 255)
ROW_ALT = (255, 255, 255, 7)
TRACK = (255, 255, 255, 26)
ME = (255, 186, 0, 255)            # o teu carro
GOOD = (38, 214, 118, 255)
BAD = (255, 66, 78, 255)
WARN = (255, 196, 36, 255)
INFO = (48, 148, 255, 255)
BEST = (180, 112, 255, 255)
PIT = (255, 140, 40, 255)
DARK_TEXT = (12, 14, 18, 255)

ACCENTS = {"cyan": "#19c3ff", "red": "#ff3b4e", "orange": "#ff8a1f", "green": "#2bd67b",
           "purple": "#a66bff", "white": "#e9edf3"}
ACCENT = hex_color(ACCENTS["cyan"])


def set_accent(name_or_hex: str) -> None:
    global ACCENT
    try:
        ACCENT = hex_color(ACCENTS.get(name_or_hex, name_or_hex))
    except Exception:
        pass


# --- classes -----------------------------------------------------------------
DEFAULT_CLASSES = [
    ["hyper", "HYP", "#e8343f"],
    ["gtp", "GTP", "#e8343f"],
    ["lmh", "HYP", "#e8343f"],
    ["lmdh", "HYP", "#e8343f"],
    ["lmp2", "LMP2", "#2f86ff"],
    ["lmp3", "LMP3", "#a86bff"],
    ["gte", "GTE", "#ff8a1f"],
    ["gt3", "GT3", "#1fbf62"],
]
_class_rules = [(k, s, hex_color(c)) for k, s, c in DEFAULT_CLASSES]


def set_class_rules(rules: list) -> None:
    global _class_rules
    try:
        _class_rules = [(str(k).lower(), str(s), hex_color(c)) for k, s, c in rules]
    except Exception:
        pass


# cores de classes que o jogo indica (iRacing dá a cor de cada classe) e que não estão nas regras
CLASS_COLORS: dict[str, tuple] = {}


def class_info(raw: str) -> tuple[str, tuple]:
    low = raw.lower().replace(" ", "")
    for key, short, color in _class_rules:
        if key in low:
            return short, color
    return (raw[:4].upper() or "?"), CLASS_COLORS.get(raw, (130, 138, 150, 255))


def class_order(raw: str) -> int:
    low = raw.lower().replace(" ", "")
    for i, (key, _s, _c) in enumerate(_class_rules):
        if key in low:
            return i
    return 99


def temp_color(t: float, optimal: float) -> tuple:
    """Azul (frio) → verde (janela ótima) → amarelo → vermelho (quente)."""
    d = t - optimal
    stops = [(-28, (55, 105, 255)), (-12, (40, 185, 235)), (-4, (38, 214, 118)), (4, (38, 214, 118)),
             (14, (255, 196, 36)), (26, (255, 66, 78))]
    if d <= stops[0][0]:
        return stops[0][1] + (255,)
    for (d0, c0), (d1, c1) in zip(stops, stops[1:]):
        if d <= d1:
            return mix(c0, c1, (d - d0) / (d1 - d0))
    return stops[-1][1] + (255,)


TYRE_BANDS = ((50, (55, 105, 255)), (60, (150, 232, 150)), (75, (38, 214, 118)), (85, (255, 196, 36)))
TYRE_HOT = (255, 66, 78)


def tyre_band_color(t: float, bands=TYRE_BANDS) -> tuple:
    """Escala fixa por graus: até 50 azul, 51-60 verde claro, 61-75 verde, 76-85 amarelo, acima vermelho."""
    for top, col in bands:
        if t <= top:
            return col + (255,)
    return TYRE_HOT + (255,)


def on_color(bg: tuple) -> tuple:
    r, g, b = bg[0], bg[1], bg[2]
    return DARK_TEXT if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else TEXT


# --- formatação --------------------------------------------------------------
def laptime(s: float) -> str:
    if not s or s <= 0 or s > 36000:
        return "-:--.---"
    m, sec = divmod(s, 60)
    return f"{int(m)}:{sec:06.3f}"


def clock(s: float | None) -> str:
    if s is None or s < 0:
        return "--:--"
    s = int(s)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def short_name(name: str, max_len: int = 18) -> str:
    if len(name) <= max_len:
        return name
    parts = name.split()
    if len(parts) >= 2:
        s = f"{parts[0][0]}. {' '.join(parts[1:])}"
        if len(s) <= max_len:
            return s
    return name[: max_len - 1] + "…"


def driver_label(name: str) -> str:
    """Estilo transmissão: 'Earl Hansen' -> 'E. HANSEN'."""
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[0][0]}. {' '.join(parts[1:]).upper()}"
    return name.upper()


# --- peças de desenho ----------------------------------------------------------
HEADER_H = 26
SKEW = 5


def skew_rect(c, x, y, w, h, fill, skew=SKEW, stroke=None):
    """Paralelogramo inclinado (as 'etiquetas' das transmissões)."""
    c.polygon([(x + skew, y), (x + w, y), (x + w - skew, y + h), (x, y + h)], fill, stroke=stroke)


# --- néon ------------------------------------------------------------------- #
# Brilho desenhado com camadas translúcidas (barato: 3-4 primitivas por elemento).
# Os overlays ganham uma margem NEON_PAD à volta para o brilho poder sair do bloco.
NEON = True
NEON_PAD = 9
USER_NEON = True

# Estilo ativo (ver skins.py). Estes valores são os do estilo "WEC Broadcast".
SKIN: dict = {"key": "wec", "header": "tv", "radius": 0, "row": "solid", "focus": "white", "pos": "box",
              "plate": True, "band": "fill", "neon": True, "text_shadow": False, "accent2": None,
              "head_ink": (255, 255, 255, 255)}


def set_neon(on) -> None:
    global NEON, USER_NEON
    USER_NEON = bool(on)
    NEON = USER_NEON and bool(SKIN.get("neon", True))


def lighten(c, t: float = 0.55):
    return mix(c, (255, 255, 255, c[3] if len(c) > 3 else 255), t)


def neon_line(c, x1, y1, x2, y2, color, width: float = 2.0) -> None:
    """Tubo de néon: halo largo e fraco + núcleo claro."""
    if NEON:
        for extra, a in ((12, 34), (7, 70), (3.5, 135)):
            c.line(x1, y1, x2, y2, alpha(color, a), width + extra)
        c.line(x1, y1, x2, y2, color, width)
        c.line(x1, y1, x2, y2, lighten(color, 0.65), max(1.0, width * 0.4))
    else:
        c.line(x1, y1, x2, y2, color, width)


def neon_polyline(c, pts, color, width: float = 2.0) -> None:
    if NEON and len(pts) > 1:
        for extra, a in ((8, 22), (4, 55)):
            c.polyline(pts, alpha(color, a), width + extra)
    c.polyline(pts, color, width)


def corner_brackets(c, x, y, w, h, color, arm: float = 14, width: float = 2.0) -> None:
    """Cantos tipo mira (estilo holograma)."""
    for (cx, cy, dx, dy) in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        neon_line(c, cx, cy, cx + dx * arm, cy, color, width)
        neon_line(c, cx, cy, cx, cy + dy * arm, color, width)


def neon_frame(c, x, y, w, h, color, strength: float = 1.0) -> None:
    """Brilho à volta de um bloco (cai na margem NEON_PAD da janela)."""
    frame = SKIN.get("frame", "neon")
    if frame == "bracket":
        corner_brackets(c, x - 3, y - 3, w + 6, h + 6, color, 16, 2.0)
        return
    if not NEON or frame == "none":
        return
    for d, a in ((8, 20), (6, 36), (4, 62), (2.2, 115)):
        c.rect(x - d, y - d, w + 2 * d, h + 2 * d, None, stroke=alpha(color, min(255, int(a * strength))), stroke_w=2.4)
    c.rect(x - 0.5, y - 0.5, w + 1, h + 1, None, stroke=alpha(lighten(color, 0.35), min(255, int(230 * strength))),
           stroke_w=1.6)


LITE = True       # modos Leve/Equilibrado: sem brilhos por trás das partes que mexem (menos pintura)


def neon_glow(c, x, y, w, h, color, strength: float = 1.0) -> None:
    """Brilho por trás de um elemento aceso (LED, barra, faixa)."""
    if not NEON or LITE:
        return
    c.rect(x - 6, y - 6, w + 12, h + 12, alpha(color, min(255, int(30 * strength))), radius=7)
    c.rect(x - 3, y - 3, w + 6, h + 6, alpha(color, min(255, int(75 * strength))), radius=4)


# Estilo TV (WEC): blocos sólidos de cantos retos, cabeçalho branco com separador preto
# inclinado e uma risca da cor de destaque por baixo.
TV_BODY = (13, 15, 21, 242)
TV_HEAD = (244, 246, 250, 252)
TV_INK = (12, 14, 19, 255)


def wec_bar(c, x, y, w, h, text, color=None, size=12.0, right: str = "", align: str = "c") -> None:
    """Faixa do estilo WEC 2025: cor sólida com riscas diagonais finas e texto em itálico."""
    col = color or SKIN.get("bar", (214, 20, 30, 255))
    c.rect(x, y, w, h, col, radius=2, fill2=scale_rgb(col, 0.78))
    sk = h * 0.6
    k = x + w * 0.62
    while k + 3 <= x + w - 2:                                        # riscas finas à direita
        c.polygon([(k, y), (k + 3, y), (k + 3 - sk, y + h), (k - sk, y + h)], (0, 0, 0, 34))
        k += 8
    ink = on_color(col)
    if right or align == "l":
        c.text(x + 9, y, w - 18, h, text, size, ink, "l", 800, spacing=1.0, italic=True)
        if right:
            c.text(x + 9, y, w - 18, h, right, size, ink, "r", 700, italic=True)
    else:
        c.text(x, y, w, h, text, size, ink, "c", 800, spacing=1.2, italic=True)


class _OnlyText:
    """Canvas que só deixa passar o texto `s` (para desenhar só o texto da direita do cabeçalho)."""

    def __init__(self, c, s: str) -> None:
        self.c, self.s = c, s

    def text(self, x, y, w, h, s, *a, **k):
        if s == self.s:
            self.c.text(x, y, w, h, s, *a, **k)

    def measure(self, *a, **k):
        return self.c.measure(*a, **k)

    def __getattr__(self, name):
        return lambda *a, **k: None


def tv_header(c, w, title: str, right: str = "", accent=None, h: float = HEADER_H - 3, part: str = "all") -> None:
    """Cabeçalho do bloco, conforme o estilo ativo.

    part="bg" desenha tudo menos o texto da direita; part="right" só esse texto. Assim o
    cabeçalho fica no fundo em cache e só o texto que muda (relógio, tempo previsto) é redesenhado.
    """
    if part == "bg":
        right = ""
    elif part == "right":
        if not right:
            return
        c = _OnlyText(c, right)
    acc = accent or ACCENT
    acc2 = SKIN.get("accent2") or acc
    style = SKIN.get("header", "tv")
    t = title.upper()
    if style == "tv":                                   # branco + separador preto inclinado
        c.rect(0, 0, w, h, TV_HEAD)
        tab = c.measure(t, 12, 800, 1.2) + 24
        c.polygon([(0, 0), (tab + 10, 0), (tab, h), (0, h)], TV_INK)
        c.rect(0, 0, 3, h, acc)
        c.text(11, 0, tab, h, t, 12, (255, 255, 255, 255), "l", 800, spacing=1.2)
        if right:
            c.text(tab + 16, 0, w - tab - 26, h, right, 13, TV_INK, "r", 800)
        c.rect(0, h, w, 3, acc)
        neon_line(c, 0, h + 1.5, w, h + 1.5, acc, 2.5)
    elif style == "neon":                               # escuro, título a néon, linha dupla
        c.rect(0, 0, w, h + 3, TV_HEAD, radius=SKIN.get("radius", 0))
        c.text(10, 0, w - 20, h, t, 13, acc, "l", 800, spacing=2.0)
        if right:
            c.text(10, 0, w - 20, h, right, 13, TEXT, "r", 700)
        neon_line(c, 6, h + 1.5, w - 6, h + 1.5, acc2, 2)
    elif style == "glass":                              # sem faixa: título discreto e linha fina
        c.text(12, 1, w - 24, h, t, 11, DIM, "l", 700, spacing=1.5)
        if right:
            c.text(12, 1, w - 24, h, right, 12, TEXT, "r", 600)
        c.rect(12, h + 1, w - 24, 1, (255, 255, 255, 34))
    elif style == "carbon":                             # faixa vermelha inclinada sobre preto
        c.rect(0, 0, w, h, TV_HEAD)
        for k in range(0, int(w) + 40, 7):              # textura de carbono (riscas finas)
            c.line(k, 0, k - 14, h, (255, 255, 255, 9), 2)
        tab = c.measure(t, 13, 800, 1.2) + 30
        c.polygon([(0, 0), (tab + 14, 0), (tab, h), (0, h)], acc)
        c.text(10, 0, tab, h, t, 13, (255, 255, 255, 255), "l", 800, spacing=1.2)
        if right:
            c.text(tab + 16, 0, w - tab - 26, h, right, 13, TEXT, "r", 800)
        c.rect(0, h, w, 3, acc)
        neon_line(c, 0, h + 1.5, w, h + 1.5, acc, 2)
    elif style == "hud":                                # só texto, sem fundo
        c.text(4, 0, w - 8, h, t, 11, acc, "l", 800, spacing=2.0)
        if right:
            c.text(4, 0, w - 8, h, right, 13, TEXT, "r", 700)
        c.rect(4, h + 1, 46, 2, acc)
    elif style == "gradient":                           # barra em gradiente vivo com chevrons
        c.rect(0, 0, w, h, acc, fill2=acc2, horizontal=True)
        for i in range(3):
            x0 = w - 54 + i * 13
            c.polygon([(x0, 0), (x0 + 7, 0), (x0 + 15, h / 2), (x0 + 7, h), (x0, h), (x0 + 8, h / 2)],
                      (255, 255, 255, 70 + 50 * i))
        c.text(12, 0, w - 24, h, t, 13, (255, 255, 255, 255), "l", 800, spacing=1.6)
        if right:
            c.text(12, 0, w - 74, h, right, 13, (255, 255, 255, 255), "r", 800)
        neon_line(c, 0, h + 1.5, w, h + 1.5, acc2, 2)
    elif style == "pill":                               # título numa cápsula em gradiente
        tw = c.measure(t, 12, 800, 1.4) + 28
        neon_glow(c, 8, 4, tw, h - 6, acc, 0.8)
        c.rect(8, 4, tw, h - 6, acc, radius=(h - 6) / 2, fill2=acc2, horizontal=True)
        c.text(8, 4, tw, h - 6, t, 12, (255, 255, 255, 255), "c", 800, spacing=1.4)
        if right:
            c.text(tw + 20, 0, w - tw - 32, h, right, 13, TEXT, "r", 700)
    elif style == "bracket":                            # holograma: título com marcas e linha fina
        c.text(12, 0, w - 24, h, "// " + t, 12, acc, "l", 800, spacing=2.2)
        if right:
            c.text(12, 0, w - 24, h, right, 13, acc2, "r", 700)
        c.rect(12, h + 1, w - 24, 1, alpha(acc, 110))
        for k in range(12, int(w) - 12, 24):
            c.rect(k, h - 1, 1, 3, alpha(acc, 150))
    elif style == "wec25":                              # WEC 2025: faixa vermelha com título em itálico
        wec_bar(c, 4, 4, w - 8, h - 3, t, None, 12.5, right, "l")
    else:                                               # retro: faixa azul-escura + duas riscas
        c.rect(0, 0, w, h, TV_HEAD, radius=SKIN.get("radius", 0))
        c.text(12, 0, w - 24, h, t, 13, SKIN.get("head_ink", (255, 255, 255, 255)), "l", 800, spacing=1.5)
        if right:
            c.text(12, 0, w - 24, h, right, 13, SKIN.get("head_ink", (255, 255, 255, 255)), "r", 700)
        c.rect(0, h, w, 2, acc)
        c.rect(0, h + 2, w, 2, acc2)


def body(c, x, y, w, h, color=None) -> None:
    """Fundo de um bloco: cantos, gradiente, cantos cortados e linhas de varrimento do estilo ativo."""
    col = TV_BODY if color is None else color
    if col[3] <= 0:
        return
    ch = SKIN.get("chamfer", 0)
    if ch:
        c.polygon([(x + ch, y), (x + w, y), (x + w, y + h - ch), (x + w - ch, y + h), (x, y + h), (x, y + ch)], col)
    else:
        c.rect(x, y, w, h, col, radius=SKIN.get("radius", 0), fill2=SKIN.get("body2") if color is None else None)
    if SKIN.get("scanlines") and color is None:
        sc = alpha(ACCENT, 14)
        for yy in range(int(y) + 3, int(y + h) - 2, 4):
            c.rect(x + 3, yy, w - 6, 1, sc)


def panel(c, w, h, title: str = "", right: str = "", right_color=DIM, accent=None, part: str = "all") -> float:
    """Bloco do estilo ativo + cabeçalho. Devolve o y onde começa o conteúdo.
    part: "all", "bg" (sem o texto da direita) ou "right" (só esse texto) — ver tv_header."""
    acc = accent or ACCENT
    if part == "right":
        if title:
            tv_header(c, w, title, right, accent, part="right")
            return HEADER_H + 5
        return 8
    neon_frame(c, 0, 0, w, h, acc, 0.8)
    if not title:
        body(c, 0, 0, w, h)
        if SKIN.get("header") in ("tv", "carbon", "neon"):
            neon_line(c, 0, h - 1, w, h - 1, acc, 2)
        return 8
    if SKIN.get("header") in ("tv", "carbon"):
        body(c, 0, HEADER_H, w, h - HEADER_H)
    else:
        body(c, 0, 0, w, h)
    tv_header(c, w, title, right, accent, part=part)
    return HEADER_H + 5


def me_row(c, x, y, w, h):
    """Destaque da linha do jogador."""
    c.rect(x, y, w, h, alpha(ME, 64), radius=3, fill2=alpha(ME, 6), horizontal=True)
    c.rect(x, y + 2, 3, h - 4, ME, radius=1.5)


def chip(c, x, y, w, h, text, bg, fg=None, size=11, weight=700):
    skew_rect(c, x, y, w, h, bg, skew=4)
    c.text(x, y, w, h, text, size, fg or on_color(bg), "c", weight, spacing=0.5)


def pos_badge(c, x, y, w, h, text, color, me=False):
    """Posição numa etiqueta inclinada na cor da classe."""
    if me:
        skew_rect(c, x, y, w, h, ME)
        c.text(x, y, w, h, text, 14, DARK_TEXT, "c", 800)
    else:
        skew_rect(c, x, y, w, h, alpha(color, 235))
        c.text(x, y, w, h, text, 14, on_color(color), "c", 800)


def placeholder(c, w, h, text):
    c.rect(1, 1, w - 2, h - 2, (11, 13, 17, 140), stroke=FAINT, stroke_w=1)
    c.text(8, 0, w - 16, h, text, 12, DIM, "c", 600, spacing=0.8)
