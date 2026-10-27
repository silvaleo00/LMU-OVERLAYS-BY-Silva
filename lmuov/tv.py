"""Estilo "TV broadcast" (género WEC / Broadcast Control): blocos sólidos, cabeçalho branco,
placas de fabricante, faixas de classe, cores de tempos (roxo / verde / dourado)."""

from __future__ import annotations

from . import theme as T
from .canvas import alpha, mix

ROW = (13, 15, 21, 242)
ROW_ALT = (19, 22, 30, 242)
HEAD = (244, 246, 250, 252)
INK = (12, 14, 19, 255)
POS_BG = (233, 236, 241, 255)
PLATE = (40, 45, 56, 255)
PLATE_TXT = (205, 211, 222, 255)
GOLD = (255, 196, 0, 255)
PURPLE = (178, 92, 255, 255)
GREEN = (40, 222, 122, 255)
RED_WASH = (226, 28, 48, 255)
AMBER = (255, 146, 0, 255)
SLOW = (255, 196, 0, 255)

# código de 3 letras do fabricante, a partir do nome do carro (sem logótipos de marca)
BRANDS = [
    ("toyota", "TOY"), ("ferrari", "FER"), ("porsche", "POR"), ("cadillac", "CAD"), ("bmw", "BMW"),
    ("alpine", "ALP"), ("peugeot", "PEU"), ("aston", "AST"), ("lamborghini", "LAM"), ("isotta", "ISO"),
    ("glickenhaus", "GLI"), ("vanwall", "VAN"), ("oreca", "ORE"), ("ligier", "LIG"), ("ginetta", "GIN"),
    ("duqueine", "DUQ"), ("lexus", "LEX"), ("mclaren", "MCL"), ("corvette", "COR"), ("chevrolet", "COR"),
    ("ford", "FOR"), ("mustang", "FOR"), ("mercedes", "MER"), ("amg", "MER"), ("genesis", "GEN"),
    ("acura", "ACU"), ("honda", "HON"), ("nissan", "NIS"), ("audi", "AUD"),
]


def brand_code(name: str) -> str:
    low = name.lower()
    for key, code in BRANDS:
        if key in low:
            return code
    word = next((w for w in name.split() if w[:1].isalpha()), "")
    return word[:3].upper() or "—"


# cor de cada marca (fundo, texto), para as placas e o cartão de rádio. Só cores, sem logótipos.
_W, _K = (255, 255, 255, 255), (12, 14, 20, 255)
BRAND_COLORS = {
    "TOY": ((236, 238, 242, 255), (215, 10, 30, 255)), "FER": ((214, 0, 18, 255), (255, 214, 0, 255)),
    "POR": ((232, 234, 238, 255), _K), "CAD": ((244, 192, 0, 255), _K), "BMW": ((24, 102, 214, 255), _W),
    "ALP": ((0, 86, 255, 255), _W), "PEU": ((186, 214, 0, 255), _K), "AST": ((0, 102, 92, 255), _W),
    "LAM": ((26, 26, 28, 255), (214, 172, 64, 255)), "ISO": ((150, 20, 34, 255), _W),
    "GLI": ((200, 24, 34, 255), _W), "VAN": ((0, 92, 64, 255), _W), "ORE": ((0, 70, 160, 255), _W),
    "LIG": ((0, 104, 190, 255), _W), "GIN": ((30, 30, 34, 255), _W), "DUQ": ((0, 48, 112, 255), _W),
    "LEX": ((40, 42, 48, 255), _W), "MCL": ((255, 128, 0, 255), _K), "COR": ((250, 196, 0, 255), _K),
    "FOR": ((0, 56, 150, 255), _W), "MER": ((196, 202, 210, 255), _K), "GEN": ((110, 30, 40, 255), _W),
    "ACU": ((200, 16, 46, 255), _W), "HON": ((200, 16, 46, 255), _W), "NIS": ((200, 16, 46, 255), _W),
    "AUD": ((30, 30, 32, 255), _W),
}
DEFAULT_BRAND = ((70, 78, 120, 255), _W)


def brand_colors(name: str) -> tuple:
    """(fundo, texto) da marca do carro, a partir do nome do carro/equipa."""
    return BRAND_COLORS.get(brand_code(name), DEFAULT_BRAND)


def surname(name: str) -> str:
    parts = name.split()
    return (parts[-1] if parts else name).upper()


def _fold(s: str) -> str:
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))


def driver_code(name: str) -> str:
    """Código de 3 letras do piloto (como na TV): as 3 primeiras letras do apelido."""
    sn = "".join(ch for ch in _fold(surname(name)) if ch.isalpha())
    return (sn[:3] or name[:3]).upper()


def team_name(vehicle_name: str) -> str:
    """Nome da equipa a partir do nome do carro do jogo ("Ferrari AF Corse 2024 #50:LM" -> "FERRARI AF CORSE")."""
    import re
    s = re.sub(r"#\s?\d+(:\w+)?", " ", vehicle_name)
    s = re.sub(r"\b(19|20)\d\d\b", " ", s)
    s = re.sub(r"[_|:]+", " ", s)
    return " ".join(s.split()).upper() or vehicle_name.upper()


def vehicle_team(v) -> str:
    """Nome da equipa de um carro: o que o jogo dá à parte (iRacing) ou tirado do nome do carro (LMU)."""
    return v.team.upper() if getattr(v, "team", "") else team_name(v.vehicle_name)


def team_short(c, name: str, w: float, size: float, weight: int = 800, spacing: float = 0.0) -> str:
    """Nome da equipa que cabe em w: inteiro, só as duas primeiras palavras, ou 1.ª palavra + iniciais."""
    fits = lambda t: c.measure(t, size, weight, spacing) <= w   # noqa: E731
    if fits(name):
        return name
    words = name.split()
    two = " ".join(words[:2])
    if len(words) > 2 and not fits(two):
        abbr = words[0] + " " + "".join(x[0] for x in words[1:] if x[:1].isalnum())
        if fits(abbr):
            return abbr
    return two


def energy_color(frac: float) -> tuple:
    """Verde (cheio) → amarelo → vermelho (vazio)."""
    if frac >= 0.5:
        return mix(T.WARN, T.GOOD, (frac - 0.5) / 0.5)
    return mix(T.BAD, T.WARN, frac / 0.5)


# Linha do teu carro (o estilo pode trocar)
FOCUS_BG = (244, 246, 250, 252)
FOCUS_INK = (12, 14, 19, 255)
POS_INK = (12, 14, 19, 255)


# --- peças ------------------------------------------------------------------- #
def slant(c, x, y, w, h, fill, k=6):
    c.polygon([(x + k, y), (x + w, y), (x + w - k, y + h), (x, y + h)], fill)


def grad_slant(c, x, y, w, h, c1, c2, k=8, n=None) -> None:
    """Paralelogramo inclinado com gradiente horizontal, feito em fatias
    (os polígonos do canvas não têm gradiente). Base de x a x+w, topo deslocado k para a direita."""
    n = n or max(8, min(40, int(w / 5)))
    for i in range(n):
        x0 = x + w * i / n
        x1 = x + w * (i + 1) / n + (1.6 if i < n - 1 else 0)   # sobreposição: sem riscas entre fatias
        c.polygon([(x0 + k, y), (x1 + k, y), (x1, y + h), (x0, y + h)], T.mix(c1, c2, (i + 0.5) / n))


def row_bg(c, x, y, w, h, focus=False, alt=False) -> None:
    """Fundo de uma linha (torre, relativo, cartões), conforme o estilo ativo."""
    sk = T.SKIN
    style, r = sk.get("row", "solid"), sk.get("radius", 0)
    if style == "pill":
        r = min(h / 2, 14)
    k = sk.get("skew", 8)
    if focus:
        f = sk.get("focus", "white")
        acc2 = sk.get("accent2") or T.ACCENT
        if f == "gradient":
            T.neon_glow(c, x, y, w, h, T.ACCENT, 1.1)
            if style == "slant":
                grad_slant(c, x, y, w - k, h, T.ACCENT, acc2, k=k)
            else:
                c.rect(x, y, w, h, T.ACCENT, radius=r, fill2=acc2, horizontal=True)
            return
        if f == "outline":
            T.neon_glow(c, x, y, w, h, T.ACCENT, 0.9)
            c.rect(x, y, w, h, alpha(T.ACCENT, 40), radius=r, stroke=T.ACCENT, stroke_w=1.6)
            return
        if f == "glow":
            T.neon_glow(c, x, y, w, h, T.ME, 1.0)
            c.rect(x, y, w, h, FOCUS_BG, radius=r, stroke=T.ME, stroke_w=1.5)
        elif f == "bar":
            c.rect(x, y, w, h, FOCUS_BG, radius=r)
            c.rect(x, y + 3, 3, h - 6, T.ME)
        else:
            T.neon_glow(c, x, y, w, h, T.ME, 0.9)
            if style == "slant":
                slant(c, x, y, w, h, FOCUS_BG, k=k)
            else:
                c.rect(x, y, w, h, FOCUS_BG, radius=r)
            if f == "white":
                T.neon_line(c, x + 1.5, y + 2, x + 1.5, y + h - 2, T.ME, 3)
        return
    bg = ROW_ALT if alt else ROW
    if style == "lines":
        c.rect(x + 4, y + h, w - 8, 1, alpha(T.ACCENT, 46))
        return
    if style == "clear" or bg[3] == 0:
        return
    if style == "slant":
        slant(c, x, y, w, h, bg, k=k)
    else:
        c.rect(x, y, w, h, bg, radius=r)


def pos_box(c, x, y, w, h, text, focus=False):
    style = T.SKIN.get("pos", "box")
    if style == "outline":
        col = T.ME if focus else T.ACCENT
        c.rect(x + 1, y + 1, w - 2, h - 2, None, radius=3, stroke=col, stroke_w=1.5)
        c.text(x, y, w, h, text, 15, col, "c", 800)
    elif style == "circle":
        r = min(w, h) / 2
        c.ellipse(x + w / 2, y + h / 2, r, r, T.ME if focus else (255, 255, 255, 26))
        c.text(x, y, w, h, text, 14, POS_INK if focus else T.TEXT, "c", 800)
    elif style == "text":
        solid = T.SKIN.get("focus") in ("solid", "gradient")
        c.text(x, y, w, h, text, 16, (FOCUS_INK if solid else T.ME) if focus else T.TEXT, "c", 800)
    else:
        slant(c, x, y, w, h, T.ME if focus else POS_BG, k=5)
        c.text(x, y, w, h, text, 15, POS_INK, "c", 800)


# ---- logótipos das marcas ---------------------------------------------------------- #
# PNG em assets/logos (vão dentro da app) ou na pasta de dados da app em data/logos (os que
# cada um junta no painel). Nome do ficheiro: o código (FER.png) ou a marca (ferrari.png).
_logo_cache: dict = {}


def reload_logos() -> None:
    _logo_cache.clear()


def _logo_dirs() -> list:
    from .paths import app_dir, resource
    return [app_dir() / "data" / "logos", resource("assets/logos")]


def logo_names(code: str) -> list:
    names = [code, code.lower()] + [k for k, cd in BRANDS if cd == code]
    return [f"{n}.png" for n in names]


def logo_path(code: str):
    """Caminho do logótipo da marca (None se não houver ficheiro)."""
    if code in _logo_cache:
        return _logo_cache[code]
    found = None
    try:
        for d in _logo_dirs():
            for n in logo_names(code):
                if (d / n).is_file():
                    found = str(d / n)
                    break
            if found:
                break
    except OSError:
        found = None
    _logo_cache[code] = found
    return found


LOGO_BG = (244, 245, 248, 255)


def logo_plate(c, x, y, w, h, code, dim=False) -> bool:
    """Placa com o logótipo da marca. Devolve False se não houver logótipo (desenha-se o código)."""
    path = logo_path(code)
    if not path:
        return False
    c.rect(x, y, w, h, alpha(LOGO_BG, 120) if dim else LOGO_BG, radius=3)
    c.image(path, x + w / 2, y + h / 2, h, box=(w - 4, h - 3))
    return True


def plate(c, x, y, w, h, code, focus=False):
    if logo_plate(c, x, y, w, h, code):
        return
    if T.SKIN.get("plate") == "brand":                  # placa na cor da marca
        bg, ink = BRAND_COLORS.get(code, DEFAULT_BRAND)
        c.rect(x, y, w, h, bg, radius=2)
        c.rect(x, y + h * 0.55, w, h * 0.45, (0, 0, 0, 34), radius=2)
        c.text(x, y, w, h, code, max(8.0, h * 0.58), ink, "c", 800, spacing=0.3, italic=True)
        return
    if not T.SKIN.get("plate", True):
        c.text(x, y, w, h, code, 10, FOCUS_INK if focus else T.FAINT, "c", 800, spacing=0.6)
        return
    c.rect(x, y, w, h, (210, 214, 222, 255) if (focus and T.SKIN.get("focus") == "white") else PLATE, radius=3)
    c.text(x, y, w, h, code, 10, INK if (focus and T.SKIN.get("focus") == "white") else PLATE_TXT, "c", 800,
           spacing=0.6)


def header(c, w, left_tab: str, title: str, right: str, accent=None, h: float = 32) -> float:
    """Cabeçalho grande da torre (tipo de sessão · volta · relógio)."""
    acc = accent or T.ACCENT
    style = T.SKIN.get("header", "tv")
    if style == "tv":
        slant(c, 0, 0, w, h, HEAD, k=0)
        tab_w = max(54, c.measure(left_tab, 12, 800, 1) + 26)
        slant(c, 0, 0, tab_w, h, INK, k=0)
        c.polygon([(tab_w, 0), (tab_w + 10, 0), (tab_w, h)], INK)
        c.text(0, 0, tab_w, h, left_tab, 12, (255, 255, 255, 255), "c", 800, spacing=1)
        c.text(tab_w + 16, 0, w - tab_w - 100, h, title, 17, INK, "l", 800, spacing=0.4)
        c.text(w - 110, 0, 100, h, right, 17, INK, "r", 800)
        c.rect(0, h, w, 3, acc)
        T.neon_line(c, 0, h + 1.5, w, h + 1.5, acc, 2.5)
        return h + 3
    if style == "carbon":
        c.rect(0, 0, w, h, T.TV_HEAD)
        for k in range(0, int(w) + 40, 7):
            c.line(k, 0, k - 16, h, (255, 255, 255, 9), 2)
        tab_w = max(64, c.measure(left_tab, 12, 800, 1) + 30)
        c.polygon([(0, 0), (tab_w + 14, 0), (tab_w, h), (0, h)], acc)
        c.text(0, 0, tab_w, h, left_tab, 12, (255, 255, 255, 255), "c", 800, spacing=1)
        c.text(tab_w + 18, 0, w - tab_w - 110, h, title, 17, T.TEXT, "l", 800, spacing=0.4)
        c.text(w - 110, 0, 100, h, right, 17, T.TEXT, "r", 800)
        c.rect(0, h, w, 3, acc)
        T.neon_line(c, 0, h + 1.5, w, h + 1.5, acc, 2)
        return h + 3
    # restantes estilos: reaproveita o cabeçalho de bloco com o título composto
    T.tv_header(c, w, f"{left_tab}  ·  {title}", right, accent, h=h)
    return h + 3


def red_bar(c, x, y, w, h, text, color=None, size=12.0, right: str = "") -> None:
    T.wec_bar(c, x, y, w, h, text, color, size, right)


def class_band(c, x, y, w, h, short: str, color, right: str = "") -> None:
    style = T.SKIN.get("band", "fill")
    if style == "wec25":
        red_bar(c, x + 4, y + 1, w - 8, h - 2, short, color, 11, right)
        return
    if style == "line":
        c.text(x + 10, y, w - 60, h, short, 12, color, "l", 800, spacing=1.5)
        if right:
            c.text(x, y, w - 10, h, right, 10, T.DIM, "r", 700, spacing=0.5)
        T.neon_line(c, x + 4, y + h - 1.5, x + w - 4, y + h - 1.5, color, 1.5)
        return
    if style == "dot":
        c.ellipse(x + 14, y + h / 2, 4, 4, color)
        c.text(x + 24, y, w - 60, h, short, 11, T.TEXT, "l", 700, spacing=1.2)
        if right:
            c.text(x, y, w - 10, h, right, 10, T.FAINT, "r", 600)
        return
    T.neon_glow(c, x, y, w, h, color, 0.7)
    if T.SKIN.get("row") == "slant":
        slant(c, x, y, w, h, alpha(color, 235), k=8)
    else:
        c.rect(x, y, w, h, alpha(color, 235), radius=T.SKIN.get("radius", 0))
    if T.SKIN.get("radius", 0) == 0 and T.SKIN.get("row") != "slant":
        c.polygon([(x + w - 34, y), (x + w, y), (x + w, y + h), (x + w - 44, y + h)], alpha((0, 0, 0, 255), 60))
    c.text(x + 10, y, w - 60, h, short, 12, T.on_color(color), "l", 800, spacing=1.5)
    if right:
        c.text(x, y, w - 10, h, right, 10, T.on_color(color), "r", 700, spacing=0.5)


def gap_text(v, ref, race: bool) -> str:
    """Intervalo de v para ref (carro à frente ou líder), na mesma classe."""
    if race:
        laps = v.laps_behind_leader - ref.laps_behind_leader
        if laps >= 1:
            return f"+{laps} L"
        return f"+{max(0.0, v.t_behind_leader - ref.t_behind_leader):.1f}"
    if v.best > 0 and ref.best > 0:
        return f"+{v.best - ref.best:.3f}"
    return "—"


def gap_value(v, ref, race: bool) -> float | None:
    if race:
        if v.laps_behind_leader - ref.laps_behind_leader >= 1:
            return None
        return max(0.0, v.t_behind_leader - ref.t_behind_leader)
    if v.best > 0 and ref.best > 0:
        return v.best - ref.best
    return None


# ---- SR / DR ------------------------------------------------------------------------ #
LICENSE_COLORS = {"R": (226, 48, 48, 255), "D": (255, 140, 0, 255), "C": (255, 204, 0, 255),
                  "B": (40, 196, 90, 255), "A": (40, 110, 255, 255), "P": (30, 30, 34, 255)}
TIER_COLORS = {"BRZ": (196, 120, 56, 255), "SLV": (196, 202, 212, 255), "GLD": (255, 196, 0, 255),
               "PLT": (110, 214, 230, 255), "DIA": (170, 140, 255, 255), "ROO": (150, 156, 168, 255)}
RATING_NEUTRAL = (70, 76, 92, 255)


def rating_color(txt: str):
    """Cor da pastilha: nível do LMU (bronze, prata...) ou letra da licença do iRacing."""
    if not txt:
        return None
    if txt in TIER_COLORS:
        return TIER_COLORS[txt]
    if len(txt) == 2 and txt[0] in "BSGP" and txt[1].isdigit():          # LMU: "S2", "G1"...
        return TIER_COLORS[{"B": "BRZ", "S": "SLV", "G": "GLD", "P": "PLT"}[txt[0]]]
    if txt[:1] in LICENSE_COLORS and len(txt) > 1 and (txt[1:2].isdigit()):
        return LICENSE_COLORS[txt[:1]]
    return RATING_NEUTRAL


def rating_chip(c, x, y, w, h, txt: str, dim: bool = False) -> None:
    col = rating_color(txt)
    if col is None:
        c.text(x, y, w, h, "—", 10, T.FAINT, "c", 600)
        return
    if dim:
        col = alpha(col, 110)
    c.rect(x, y, w, h, col, radius=3)
    c.text(x, y, w, h, txt, 10, T.on_color(col), "c", 800)



# ---- caixa do Driver Rating como no LMU: [S3] 50% +18% ---------------------------------------- #
DR_TIER = {"B": (205, 128, 60, 255), "S": (214, 218, 224, 255), "G": (255, 196, 0, 255),
           "P": (120, 220, 232, 255), "D": (170, 140, 255, 255)}
DR_BOX = (150, 154, 162, 235)
_TIER_SHORT = {"BRZ": "B", "SLV": "S", "GLD": "G", "PLT": "P", "DIA": "D"}


def dr_parts(dr: str) -> tuple[str, str]:
    """"S3" -> ("S", "3"); "GLD" -> ("G", ""); outros -> ("", texto)."""
    if not dr:
        return "", ""
    if dr in _TIER_SHORT:
        return _TIER_SHORT[dr], ""
    if dr[:1] in DR_TIER and dr[1:].isdigit():
        return dr[:1], dr[1:]
    return "", dr


def dr_box(c, x, y, w, h, dr: str, pct: float = -1.0, delta: float = 0.0, dim: bool = False) -> None:
    tier, lvl = dr_parts(dr)
    if not tier:
        rating_chip(c, x, y, w, h, dr, dim)
        return
    tcol = DR_TIER[tier]
    box = alpha(DR_BOX, 120) if dim else DR_BOX
    c.rect(x, y, w, h, box, radius=3)
    cw = h + 6                                        # pastilha do nível: "S3"
    c.rect(x, y, cw, h, alpha(tcol, 130) if dim else tcol, radius=3)
    c.text(x, y, cw, h, tier + lvl, 9.5, T.on_color(tcol), "c", 800)
    ink = (20, 22, 28, 255)
    rest = w - cw
    if pct >= 0:
        c.text(x + cw + 2, y, rest * 0.45, h, f"{pct * 100:.0f}%", 9.5, ink, "c", 800)
    if delta:
        dcol = (0, 120, 50, 255) if delta > 0 else (190, 20, 30, 255)
        c.text(x + cw + rest * 0.45, y, rest * 0.55 - 2, h, f"{delta * 100:+.0f}%", 9.5, dcol, "c", 800)
    elif pct < 0:
        c.text(x + cw, y, rest, h, "", 9.5, ink, "c", 800)


# ---- ícone do Safety Rating (losango colorido) ----------------------------------------------- #
SR_ICON = {"PLT": (60, 220, 120, 255), "GLD": (60, 220, 120, 255), "SLV": (70, 140, 255, 255),
           "BRZ": (255, 150, 40, 255)}


def sr_icon(c, cx, cy, r, sr: str, dim: bool = False) -> bool:
    col = SR_ICON.get(sr)
    if col is None and len(sr) >= 2 and sr[1:].isdigit():            # "S2", "G1" ... (LMU)
        col = SR_ICON.get({"P": "PLT", "G": "GLD", "S": "SLV", "B": "BRZ"}.get(sr[:1], ""))
    if col is None:
        return False
    if dim:
        col = alpha(col, 110)
    c.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], col)
    c.polygon([(cx, cy - r * 0.45), (cx + r * 0.45, cy), (cx, cy + r * 0.45), (cx - r * 0.45, cy)],
              (255, 255, 255, 120))
    return True
