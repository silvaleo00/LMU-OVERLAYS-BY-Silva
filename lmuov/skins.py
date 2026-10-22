"""Estilos visuais (skins). Mudam cores, cabeçalhos, linhas e efeitos de todos os overlays.

Cada estilo é um conjunto de valores aplicados aos módulos theme e tv. Para criar um novo,
copia um bloco, muda o que quiseres e acrescenta-o a SKINS.
"""

from __future__ import annotations

from . import theme as T
from . import tv
from .canvas import hex_color

_THEME_KEYS = ("TV_BODY", "TV_HEAD", "TV_INK", "TEXT", "DIM", "FAINT", "ME", "TRACK", "WARN")
_TV_KEYS = ("ROW", "ROW_ALT", "HEAD", "INK", "POS_BG", "POS_INK", "PLATE", "PLATE_TXT", "FOCUS_BG", "FOCUS_INK",
            "GOLD")

# valores de origem (estilo WEC), para se poder voltar a ele
_BASE_THEME = {k: getattr(T, k) for k in _THEME_KEYS}
_BASE_TV = {k: getattr(tv, k) for k in _TV_KEYS}
_BASE_SKIN = dict(T.SKIN)

SKINS: dict[str, dict] = {
    "wec": {
        "name": "WEC Broadcast",
        "accent": "#19c3ff",
        "skin": {},
        "theme": {},
        "tv": {},
    },
    "cyber": {
        "name": "Cyber Neon",
        "accent": "#00f0ff",
        "skin": {"header": "neon", "radius": 4, "focus": "glow", "pos": "outline", "band": "line",
                 "accent2": (255, 43, 214, 255)},
        "theme": {"TV_BODY": (9, 7, 22, 228), "TV_HEAD": (16, 10, 38, 236), "TV_INK": (235, 240, 255, 255),
                  "TEXT": (236, 242, 255, 255), "DIM": (150, 160, 205, 255), "FAINT": (98, 102, 145, 255),
                  "ME": (255, 43, 214, 255)},
        "tv": {"ROW": (13, 9, 30, 222), "ROW_ALT": (18, 12, 40, 222), "HEAD": (16, 10, 38, 236),
               "POS_BG": (30, 20, 60, 255), "PLATE": (28, 18, 56, 255), "PLATE_TXT": (0, 240, 255, 255),
               "FOCUS_BG": (54, 14, 78, 235), "FOCUS_INK": (255, 255, 255, 255)},
    },
    "glass": {
        "name": "Glass",
        "accent": "#5ac8fa",
        "skin": {"header": "glass", "radius": 10, "focus": "soft", "pos": "circle", "plate": False,
                 "band": "dot", "neon": False},
        "theme": {"TV_BODY": (22, 24, 30, 178), "TV_HEAD": (0, 0, 0, 0), "TEXT": (246, 247, 249, 255),
                  "DIM": (172, 178, 188, 255), "FAINT": (122, 128, 138, 255), "ME": (90, 200, 250, 255)},
        "tv": {"ROW": (0, 0, 0, 0), "ROW_ALT": (255, 255, 255, 10), "PLATE": (0, 0, 0, 0),
               "FOCUS_BG": (255, 255, 255, 46), "FOCUS_INK": (255, 255, 255, 255), "POS_INK": (10, 12, 16, 255)},
    },
    "carbon": {
        "name": "Carbon",
        "accent": "#e10600",
        "skin": {"header": "carbon", "row": "slant", "focus": "accent"},
        "theme": {"TV_BODY": (10, 10, 11, 240), "TV_HEAD": (14, 14, 15, 250), "TEXT": (245, 245, 245, 255),
                  "DIM": (160, 160, 166, 255), "FAINT": (106, 106, 112, 255), "ME": (225, 6, 0, 255)},
        "tv": {"ROW": (18, 18, 20, 238), "ROW_ALT": (25, 25, 28, 238), "POS_BG": (242, 242, 242, 255),
               "POS_INK": (10, 10, 10, 255), "PLATE": (36, 36, 40, 255), "PLATE_TXT": (205, 205, 210, 255),
               "FOCUS_BG": (225, 6, 0, 245), "FOCUS_INK": (255, 255, 255, 255)},
    },
    "hud": {
        "name": "HUD",
        "accent": "#ffc400",
        "skin": {"header": "hud", "row": "clear", "focus": "bar", "pos": "text", "plate": False, "band": "dot",
                 "neon": False, "text_shadow": True},
        "theme": {"TV_BODY": (0, 0, 0, 60), "TV_HEAD": (0, 0, 0, 0), "TEXT": (255, 255, 255, 255),
                  "DIM": (214, 218, 224, 255), "FAINT": (168, 172, 180, 255), "ME": (255, 196, 0, 255)},
        "tv": {"ROW": (0, 0, 0, 0), "ROW_ALT": (0, 0, 0, 0), "PLATE": (0, 0, 0, 0),
               "FOCUS_BG": (255, 196, 0, 38), "FOCUS_INK": (255, 255, 255, 255)},
    },
    "retro": {
        "name": "Retro Endurance",
        "accent": "#f28c28",
        "skin": {"header": "retro", "radius": 3, "focus": "accent", "neon": False,
                 "accent2": (108, 180, 228, 255), "head_ink": (240, 235, 222, 255)},
        "theme": {"TV_BODY": (240, 235, 222, 242), "TV_HEAD": (22, 42, 74, 250), "TV_INK": (22, 42, 74, 255),
                  "TEXT": (28, 30, 36, 255), "DIM": (88, 90, 98, 255), "FAINT": (140, 138, 132, 255),
                  "ME": (242, 140, 40, 255), "TRACK": (0, 0, 0, 40), "WARN": (196, 118, 0, 255)},
        "tv": {"ROW": (240, 235, 222, 242), "ROW_ALT": (230, 223, 206, 242), "HEAD": (22, 42, 74, 250),
               "INK": (22, 42, 74, 255), "POS_BG": (22, 42, 74, 255), "POS_INK": (240, 235, 222, 255),
               "PLATE": (214, 208, 192, 255), "PLATE_TXT": (22, 42, 74, 255),
               "FOCUS_BG": (242, 140, 40, 250), "FOCUS_INK": (20, 20, 24, 255), "GOLD": (186, 112, 0, 255)},
    },
    # ---- gráficos da WEC de 2025 -------------------------------------------- #
    "wec25": {
        "name": "WEC 2025",
        "accent": "#3d7bff",
        "skin": {"header": "wec25", "radius": 6, "row": "lines", "focus": "solid", "pos": "text", "plate": "brand",
                 "band": "wec25", "accent2": (0, 200, 255, 255), "body2": (5, 8, 36, 244),
                 "bar": (214, 20, 30, 255), "tower": "wec25", "value_box": (76, 82, 130, 240)},
        "theme": {"TV_BODY": (14, 20, 70, 242), "TV_HEAD": (214, 20, 30, 255), "TEXT": (255, 255, 255, 255),
                  "DIM": (178, 188, 230, 255), "FAINT": (116, 126, 182, 255), "ME": (0, 200, 255, 255)},
        "tv": {"ROW": (0, 0, 0, 0), "ROW_ALT": (0, 0, 0, 0), "POS_INK": (255, 255, 255, 255),
               "FOCUS_BG": (36, 99, 235, 252), "FOCUS_INK": (255, 255, 255, 255), "PLATE": (40, 48, 100, 255),
               "PLATE_TXT": (220, 228, 255, 255)},
    },
    "iracing": {
        "name": "iRacing Broadcast",
        "accent": "#2f8cff",
        "skin": {"header": "wec25", "radius": 6, "row": "lines", "focus": "solid", "pos": "text", "plate": "brand",
                 "band": "wec25", "accent2": (255, 138, 0, 255), "body2": (8, 9, 12, 246),
                 "bar": (22, 112, 232, 255), "tower": "wec25", "value_box": (56, 62, 76, 240), "emblem": "iRACING"},
        "theme": {"TV_BODY": (24, 27, 34, 244), "TV_HEAD": (22, 112, 232, 255), "TEXT": (255, 255, 255, 255),
                  "DIM": (176, 184, 200, 255), "FAINT": (112, 120, 138, 255), "ME": (255, 138, 0, 255)},
        "tv": {"ROW": (0, 0, 0, 0), "ROW_ALT": (0, 0, 0, 0), "POS_INK": (255, 255, 255, 255),
               "FOCUS_BG": (255, 122, 0, 252), "FOCUS_INK": (255, 255, 255, 255), "PLATE": (44, 48, 60, 255),
               "PLATE_TXT": (220, 226, 240, 255)},
    },
    # ---- estilos "chamativos" ---------------------------------------------- #
    "horizon": {
        "name": "Horizon Pop",
        "accent": "#ff2e88",
        "skin": {"header": "gradient", "row": "slant", "skew": 12, "focus": "gradient", "band": "fill",
                 "accent2": (255, 176, 0, 255), "body2": (12, 6, 20, 236)},
        "theme": {"TV_BODY": (34, 14, 46, 236), "TEXT": (255, 255, 255, 255), "DIM": (214, 190, 228, 255),
                  "FAINT": (150, 120, 168, 255), "ME": (255, 46, 136, 255)},
        "tv": {"ROW": (34, 16, 48, 232), "ROW_ALT": (44, 20, 60, 232), "POS_BG": (255, 255, 255, 255),
               "PLATE": (60, 30, 80, 255), "PLATE_TXT": (255, 200, 230, 255),
               "FOCUS_INK": (255, 255, 255, 255)},
    },
    "aurora": {
        "name": "Aurora",
        "accent": "#22d3ee",
        "skin": {"header": "pill", "row": "pill", "radius": 16, "focus": "gradient", "pos": "circle",
                 "plate": False, "band": "dot", "accent2": (168, 85, 247, 255), "body2": (12, 36, 72, 214)},
        "theme": {"TV_BODY": (46, 20, 92, 214), "TEXT": (248, 250, 255, 255), "DIM": (196, 200, 236, 255),
                  "FAINT": (140, 146, 190, 255), "ME": (34, 211, 238, 255)},
        "tv": {"ROW": (255, 255, 255, 16), "ROW_ALT": (255, 255, 255, 8), "PLATE": (0, 0, 0, 0),
               "FOCUS_INK": (255, 255, 255, 255), "POS_INK": (10, 12, 30, 255)},
    },
    "hologram": {
        "name": "Hologram",
        "accent": "#00e5ff",
        "skin": {"header": "bracket", "row": "lines", "focus": "outline", "pos": "outline", "band": "line",
                 "frame": "bracket", "chamfer": 12, "scanlines": True, "accent2": (124, 255, 203, 255)},
        "theme": {"TV_BODY": (0, 22, 30, 168), "TEXT": (214, 250, 255, 255), "DIM": (120, 200, 214, 255),
                  "FAINT": (70, 140, 152, 255), "ME": (124, 255, 203, 255)},
        "tv": {"ROW": (0, 0, 0, 0), "ROW_ALT": (0, 0, 0, 0), "PLATE": (0, 60, 72, 200),
               "PLATE_TXT": (0, 229, 255, 255), "FOCUS_INK": (255, 255, 255, 255)},
    },
    "capsule": {
        "name": "Capsule",
        "accent": "#0a84ff",
        "skin": {"header": "pill", "row": "pill", "radius": 20, "focus": "solid", "pos": "circle",
                 "plate": False, "band": "dot", "neon": False, "accent2": (255, 55, 95, 255)},
        "theme": {"TV_BODY": (0, 0, 0, 236), "TEXT": (255, 255, 255, 255), "DIM": (172, 172, 178, 255),
                  "FAINT": (110, 110, 116, 255), "ME": (10, 132, 255, 255)},
        "tv": {"ROW": (28, 28, 30, 255), "ROW_ALT": (22, 22, 24, 255), "FOCUS_BG": (10, 132, 255, 255),
               "FOCUS_INK": (255, 255, 255, 255), "POS_INK": (255, 255, 255, 255)},
    },
    "inferno": {
        "name": "Inferno",
        "accent": "#ff3d00",
        "skin": {"header": "gradient", "row": "slant", "skew": 7, "focus": "gradient", "band": "fill",
                 "accent2": (255, 179, 0, 255), "body2": (30, 9, 2, 238)},
        "theme": {"TV_BODY": (12, 6, 4, 238), "TEXT": (255, 244, 236, 255), "DIM": (220, 176, 150, 255),
                  "FAINT": (150, 110, 90, 255), "ME": (255, 120, 0, 255)},
        "tv": {"ROW": (24, 10, 6, 236), "ROW_ALT": (32, 13, 7, 236), "POS_BG": (255, 196, 90, 255),
               "PLATE": (52, 20, 10, 255), "PLATE_TXT": (255, 190, 140, 255), "FOCUS_INK": (255, 255, 255, 255)},
    },
}

SKINS = {"wec25": SKINS.pop("wec25"), "iracing": SKINS.pop("iracing"), **SKINS}     # o estilo por defeito aparece primeiro na lista

CURRENT = "wec"


def names() -> dict[str, str]:
    return {k: v["name"] for k, v in SKINS.items()}


def apply(key: str, accent: str = "auto") -> None:
    """Ativa o estilo `key`. accent="auto" usa a cor do estilo; outro valor sobrepõe-se."""
    global CURRENT
    sk = SKINS.get(key) or SKINS["wec"]
    CURRENT = key if key in SKINS else "wec"
    for k, v in _BASE_THEME.items():
        setattr(T, k, sk["theme"].get(k, v))
    for k, v in _BASE_TV.items():
        setattr(tv, k, sk["tv"].get(k, v))
    T.SKIN.clear()
    T.SKIN.update(_BASE_SKIN)
    T.SKIN.update(sk["skin"])
    T.SKIN["key"] = CURRENT
    if accent and accent != "auto":
        T.set_accent(accent)
    else:
        T.ACCENT = hex_color(sk["accent"])
    T.set_neon(T.USER_NEON)
