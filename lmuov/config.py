"""config.json: língua, unidades, posições, tamanhos e opções de cada overlay."""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path

from .overlays import ALL
from .theme import DEFAULT_CLASSES

log = logging.getLogger("lmuov")
CONFIG_VERSION = 2

# Frequência de redesenho de cada overlay (fps). Os que têm movimento (barras, ponteiros, mapa,
# radar) acompanham o ecrã; os de texto (tempos que só mudam ~5x/s) redesenham-se menos vezes,
# desfasados entre si para o trabalho não cair todo no mesmo frame.
DEFAULT_FPS = {"delta": 20, "advanced": 20, "blind_spot": 20, "inputs": 15, "pitbox": 10, "team_radio": 10,
               "track_map": 5, "battle": 5, "relative": 5, "track_limits": 5, "flags": 10, "digital_flag": 10,
               "tower": 2, "standings": 2, "tyres": 2, "damage": 2, "engine_temps": 1, "fuel": 1, "wind": 1,
               "lap_counter": 1, "weather": 1}
_OLD_FPS = [
    {"delta": 30, "inputs": 20, "advanced": 20, "blind_spot": 20, "track_map": 10, "pitbox": 10, "flags": 8,
     "digital_flag": 6, "team_radio": 20, "relative": 8, "standings": 4, "tower": 5, "battle": 8, "tyres": 8,
     "fuel": 4, "wind": 4},
    {"delta": 60, "inputs": 60, "advanced": 60, "blind_spot": 60, "track_map": 60, "pitbox": 60, "team_radio": 60,
     "battle": 20, "relative": 20, "tower": 15, "flags": 15, "digital_flag": 15, "fuel": 10, "standings": 10,
     "tyres": 10, "wind": 10, "track_limits": 20, "damage": 10, "weather": 4, "lap_counter": 10, "engine_temps": 10},
    {"delta": 60, "advanced": 60, "inputs": 30, "blind_spot": 30, "pitbox": 30, "team_radio": 30, "track_map": 15,
     "battle": 10, "relative": 10, "track_limits": 10, "flags": 8, "digital_flag": 8, "tower": 5, "standings": 5,
     "tyres": 4, "damage": 4, "engine_temps": 4, "fuel": 2, "wind": 2, "lap_counter": 2, "weather": 1},
]
FPS_VERSION = 4
# modos de desempenho (o utilizador só escolhe isto): frames por segundo dos overlays
PERF_MODES = {"light": 10, "balanced": 20, "smooth": 40}
HZ_CHOICES = tuple(PERF_MODES.values())

GLOBAL_DEFAULTS = {
    "sim": "lmu",                     # simulador: lmu, iracing
    "show_in_garage": True,           # overlays também na garagem/monitor (endurance)
    "update_repo": "",                # "utilizador/repositório" no GitHub (vazio = o que vem na app)
    "language": "en",                 # en, pt, es, fr, de, it
    "perf": "balanced",               # light (10 fps), balanced (20), smooth (40)
    "hz": 20,
    "fps_v": FPS_VERSION,
    "opacity": 1.0,
    "skin": "wec25",                  # wec25, wec, cyber, glass, carbon, hud, retro, horizon, aurora, hologram, capsule, inferno
    "accent": "auto",                 # auto (cor do estilo), cyan, red, orange, green, purple, white ou "#rrggbb"
    "neon": True,                     # brilho néon (na cor de destaque)
    "speed_unit": "kmh",              # kmh ou mph
    "pressure_unit": "kPa",           # kPa, psi ou bar
    "hide_when_not_driving": True,    # esconde tudo nos menus / monitor
    "hotkeys": {"toggle_all": "ctrl+shift+o", "toggle_edit": "ctrl+shift+l", "show_panel": "ctrl+shift+p",
                "peek": "ctrl+shift+space", "tower_field": "ctrl+shift+t"},
    # botões do volante: ação -> [n.º do dispositivo, n.º do botão] (atribuídos no painel)
    "buttons": {"peek": None, "tower_field": None, "toggle_all": None, "toggle_edit": None},
    "peek_s": 8.0,                    # quanto tempo o "espreitar" mostra tudo
    "low_priority": True,             # processo com prioridade abaixo do normal (o jogo primeiro)
    "fast_text": True,                # texto com layout em cache (desliga se o texto aparecer estranho)
    "font_families": ["Barlow Semi Condensed", "Bahnschrift", "Segoe UI", "Arial"],
    "class_rules": DEFAULT_CLASSES,   # [texto a procurar no nome da classe, sigla, cor]
}


def defaults(screen_w: int = 1920, screen_h: int = 1080) -> dict:
    sx, sy = screen_w / 1920, screen_h / 1080
    cfg = {"version": CONFIG_VERSION, "global": copy.deepcopy(GLOBAL_DEFAULTS), "overlays": {}}
    for cls in ALL:
        x, y = cls.default_pos
        cfg["overlays"][cls.key] = {
            "enabled": cls.default_enabled, "x": int(x * sx), "y": int(y * sy), "scale": 1.0,
            "sessions": list(cls.default_sessions), "fps": DEFAULT_FPS.get(cls.key, 10),
            **({"mode": cls.default_mode} if cls.smart_capable else {}),
            **copy.deepcopy(cls.defaults)}
    return cfg


def _merge(base: dict, user: dict) -> dict:
    out = dict(base)
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load(path: Path, screen_w: int = 1920, screen_h: int = 1080) -> dict:
    base = defaults(screen_w, screen_h)
    if path.exists():
        try:
            user = json.loads(path.read_text("utf-8"))
            if user.get("version") != CONFIG_VERSION:
                # versão anterior: o layout mudou todo, por isso só se aproveitam as opções gerais
                old_g = user.get("global", {})
                old_unit = user.get("overlays", {}).get("tyres", {}).get("pressure_unit")
                user = {"global": {k: v for k, v in old_g.items() if k in ("opacity", "hide_when_not_driving", "hz")}}
                if old_unit:
                    user["global"]["pressure_unit"] = old_unit
            user["version"] = CONFIG_VERSION
            ug = user.setdefault("global", {})
            if "skin" not in ug and ug.get("accent") in (None, "cyan"):
                ug["accent"] = "auto"      # versões anteriores gravavam "cyan" por defeito
            ovs = user.get("overlays", {})
            if ovs and "tower" not in ovs and ovs.get("standings", {}).get("enabled", True):
                # a Timing Tower apareceu: mesma posição da classificação antiga, que fica desligada
                st = ovs.setdefault("standings", {})
                ovs["tower"] = {"x": st.get("x", base["overlays"]["tower"]["x"]),
                                "y": st.get("y", base["overlays"]["tower"]["y"])}
                st["enabled"] = False
            if ug.get("fps_v", 1) < FPS_VERSION:          # passa para os valores leves (só uma vez)
                ug["fps_v"] = FPS_VERSION
                ug["perf"], ug["hz"] = "balanced", PERF_MODES["balanced"]
                for k, o in ovs.items():
                    if isinstance(o, dict) and any(o.get("fps") == old.get(k) for old in _OLD_FPS):
                        o["fps"] = DEFAULT_FPS.get(k, o["fps"])
            for k in ("flags", "digital_flag"):            # bandeiras ao mesmo tempo que as do jogo
                if isinstance(ovs.get(k), dict) and ovs[k].get("fps") == 4:
                    ovs[k]["fps"] = 10
            tw = ovs.get("tower", {})
            if tw.get("fields") == ["interval", "gap", "last"]:
                tw["fields"] = list(base["overlays"]["tower"]["fields"])   # ecrãs novos (piloto, equipa, top 8)
            return _merge(base, user)
        except Exception as exc:
            log.error("config.json inválido (%s); a usar valores por defeito", exc)
    return base


def save(path: Path, cfg: dict) -> None:
    try:
        path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), "utf-8")
    except Exception as exc:
        log.error("não foi possível guardar config.json: %s", exc)
