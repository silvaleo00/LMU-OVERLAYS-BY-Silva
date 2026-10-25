"""Contas de posição relativa em pista (usadas pelo Relativo e pelas Bandeiras)."""

from __future__ import annotations

from dataclasses import dataclass

from .model import Snapshot, Vehicle


@dataclass
class Rel:
    v: Vehicle
    dist: float      # metros: >0 à frente em pista, <0 atrás
    gap: float       # segundos (mesmo sinal que dist)
    lap_diff: int    # >0 = está voltas à minha frente na corrida; <0 = atrás


def ref_lap(snap: Snapshot) -> float:
    me = snap.me
    for t in (me.est_lap, me.best, me.last):
        if t and t > 0:
            return t
    return 100.0


def time_gap(me: Vehicle, v: Vehicle, d: float, L: float, lap: float) -> float:
    """Diferença em segundos, como o relativo do próprio jogo: pela "posição em tempo" que o jogo
    estima para cada carro (LMU mTimeIntoLap / iRacing CarIdxEstTime). Se o jogo não der, usa a
    distância convertida pelo teu tempo de volta."""
    linear = d / L * lap
    a, b = v.time_into_lap, me.time_into_lap
    if a > 0 and b > 0 and lap > 0:
        raw = a - b
        g = min((raw, raw + lap, raw - lap), key=lambda c: abs(c - linear))
        if abs(g - linear) < 0.35 * lap and (g * linear >= 0 or abs(g) < 1.0):
            return g
    return linear


def relatives(snap: Snapshot, include_pits: bool = True) -> list[Rel]:
    me, L = snap.me, snap.session.track_length
    if L <= 0:
        return []
    lap = ref_lap(snap)
    my_total = snap.total_dist(me)
    out = []
    for v in snap.vehicles:
        if v is me or v.in_garage or v.finish_status in (2, 3):
            continue
        if v.in_pits and not include_pits:
            continue
        d = v.lap_dist - me.lap_dist
        if d > L / 2:
            d -= L
        elif d <= -L / 2:
            d += L
        total = snap.total_dist(v) - my_total
        lap_diff = round((total - d) / L)
        out.append(Rel(v=v, dist=d, gap=time_gap(me, v, d, L, lap), lap_diff=lap_diff))
    return out
