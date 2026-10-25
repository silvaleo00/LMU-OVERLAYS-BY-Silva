"""Que bandeiras estão ativas para o jogador (partilhado por Flags e Digital Flag).

Prioridade: vermelha > xadrez > FCY > amarela à frente > azul > penalidade >
partida/formação > verde. Só conta o que está à frente e só com o carro em pista.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import theme as T
from .i18n import tr
from .relcalc import relatives

FLAG_DEFAULTS = {"yellow_range_m": 800, "slow_kmh": 60, "blue_lookback_m": 400}

COLORS = {
    "red": T.BAD, "chequered": (238, 240, 244, 255), "fcy": T.WARN, "yellow": T.WARN, "blue": T.INFO,
    "penalty": (24, 24, 26, 255), "start": T.BAD, "formation": (90, 98, 112, 255), "green": T.GOOD,
}
BLINK = {"red", "fcy", "yellow", "blue"}


@dataclass
class Flag:
    kind: str
    text: str
    sub: str

    @property
    def color(self):
        return COLORS[self.kind]

    @property
    def blink(self) -> bool:
        return self.kind in BLINK


def active_flags(snap, ctx, cfg: dict | None = None) -> list[Flag]:
    cfg = {**FLAG_DEFAULTS, **(cfg or {})}
    if snap is None or snap.me.in_garage or snap.me.in_pits and snap.me.speed < 1:
        return []
    s, me = snap.session, snap.me
    out: list[Flag] = []
    race = s.kind == "race"

    if s.phase == 7:
        out.append(Flag("red", tr("flag.red"), tr("flag.red_sub")))
    leader_done = race and any(v.finish_status == 1 for v in snap.vehicles)
    if me.finish_status == 1:
        out.append(Flag("chequered", tr("flag.finished"), tr("flag.finished_sub", p=me.place, c=me.class_place)))
    elif s.phase == 8 or leader_done:
        sub = tr("flag.chequered_sub") if race else tr("flag.session_over")
        out.append(Flag("chequered", tr("flag.chequered"), sub))
    if s.phase == 6:
        out.append(Flag("fcy", tr("flag.fcy"), tr(f"flag.fcy{s.yellow_state}" if 1 <= s.yellow_state <= 6
                                                     else "flag.fcy0")))
    if s.phase != 6:
        y = _yellow_here(snap, cfg)
        if y:
            out.append(y)
    if me.flag == 6:
        out.append(Flag("blue", tr("flag.blue"), _blue_sub(snap, cfg)))
    if me.penalties > 0:
        out.append(Flag("penalty", tr("flag.penalty"), tr("flag.penalty_sub", n=me.penalties)))
    if s.phase == 4:
        out.append(Flag("start", tr("flag.start"), tr("flag.start_sub")))
    elif s.phase == 3:
        out.append(Flag("formation", tr("flag.formation"), tr("flag.formation_sub")))
    if ctx is not None and ctx.now < ctx.green_until and s.phase == 5:
        out.append(Flag("green", tr("flag.green"), tr("flag.green_sub")))
    return out


def _yellow_here(snap, cfg):
    """Amarela como no LMU: só quando o jogo a mostra ao teu carro (estás sob amarela) ou quando o
    setor onde ESTÁS tem amarela. Nada de avisos antecipados do setor seguinte."""
    me, s = snap.me, snap.session
    cur = me.sector if 0 <= me.sector < 3 else 0
    if not (me.under_yellow or (len(s.sector_flags) > cur and s.sector_flags[cur] == 1)):
        return None
    rng = float(cfg["yellow_range_m"])
    slow = float(cfg["slow_kmh"]) / 3.6
    cands = [r for r in relatives(snap, include_pits=False) if 0 < r.dist <= rng and r.v.speed < slow]
    if cands:                                   # quem está lento à frente, para saberes onde
        r = min(cands, key=lambda r: r.dist)
        who = f"#{r.v.number} " if r.v.number else ""
        state = tr("flag.stopped") if r.v.speed < 3 else tr("flag.slow")
        return Flag("yellow", tr("flag.yellow_sector", n=cur + 1),
                    tr("flag.yellow_car", who=who, state=state, d=f"{r.dist:.0f}"))
    return Flag("yellow", tr("flag.yellow_sector", n=cur + 1), tr("flag.yellow_sector_sub"))


def _blue_sub(snap, cfg):
    look = float(cfg["blue_lookback_m"])
    my_cls = T.class_order(snap.me.cls)
    # quem pede passagem: carro atrás que já me deu volta(s) ou de uma classe mais rápida
    behind = [r for r in relatives(snap, include_pits=False) if -look <= r.dist < 0
              and (r.lap_diff > 0 or T.class_order(r.v.cls) < my_cls)]
    if not behind:
        return tr("flag.blue_generic")
    r = max(behind, key=lambda r: r.dist)
    short, _ = T.class_info(r.v.cls)
    who = f"{short} #{r.v.number}" if r.v.number else short
    return tr("flag.blue_sub", who=who, g=f"{abs(r.gap):.1f}")
