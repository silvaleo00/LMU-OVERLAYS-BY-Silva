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
        out.append(Rel(v=v, dist=d, gap=d / L * lap, lap_diff=lap_diff))
    return out
