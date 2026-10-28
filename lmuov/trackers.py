"""Estado que se acumula ao longo das voltas: consumo, delta, desgaste.

Tudo é alimentado com Snapshots (venham do LMU ou do demo), por isso estas
contas são as mesmas nos dois modos.
"""

from __future__ import annotations

import bisect
import json
import math
import statistics
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from .model import Snapshot


# --------------------------------------------------------------------------- #
# Combustível / energia virtual
# --------------------------------------------------------------------------- #
@dataclass
class FuelInfo:
    uses_ve: bool = False
    unit: str = "L"               # "L" ou "%"
    remaining: float = 0.0        # L ou % de VE
    capacity: float = 0.0         # L ou 100 (%)
    fuel_l: float = 0.0           # combustível em litros (mostrado em pequeno com VE)
    per_lap: float = 0.0          # média por volta (0 = ainda sem dados)
    last_lap: float = 0.0         # consumo da última volta válida
    estimating: bool = False      # média vem só da volta atual
    laps_in_tank: float = 0.0
    race_laps_left: float = 0.0   # voltas que faltam para acabar (estimativa)
    needed: float = 0.0           # total necessário até ao fim (+ margem)
    to_add: float = 0.0           # quanto falta pôr no carro
    stops: int = 0
    target_per_lap: float = 0.0   # consumo/volta para acabar sem reabastecer
    samples: int = 0


class FuelTracker:
    def __init__(self, avg_laps: int = 5, margin_laps: float = 0.5) -> None:
        self.avg_laps = avg_laps
        self.margin_laps = margin_laps
        self.reset()

    def reset(self) -> None:
        self.uses_ve = False
        self.hist_fuel: list[float] = []
        self.hist_ve: list[float] = []
        self.lap_times: list[float] = []
        self.start_fuel = None
        self.start_ve = None
        self.prev_laps = None
        self.lap_dirty = True       # primeira volta nunca conta (pode ser out-lap)
        self.prev_fuel = None
        self.prev_ve = None

    def update(self, snap: Snapshot) -> FuelInfo:
        p, me, s = snap.player, snap.me, snap.session
        ve = p.virtual_energy * 100.0
        if ve > 0.01:
            self.uses_ve = True

        # Reabastecimento ou pit: a volta deixa de contar
        if (self.prev_fuel is not None and p.fuel > self.prev_fuel + 0.05) or \
           (self.prev_ve is not None and ve > self.prev_ve + 0.05) or me.in_pits or s.phase == 6:
            self.lap_dirty = True
        self.prev_fuel, self.prev_ve = p.fuel, ve

        if self.prev_laps is None:
            self.prev_laps = me.total_laps
            self.start_fuel, self.start_ve = p.fuel, ve
        elif me.total_laps != self.prev_laps:
            if me.total_laps == self.prev_laps + 1 and not self.lap_dirty:
                used_f = (self.start_fuel or 0) - p.fuel
                used_v = (self.start_ve or 0) - ve
                if used_f > 0.01:
                    self.hist_fuel.append(used_f)
                if used_v > 0.01:
                    self.hist_ve.append(used_v)
                if me.last > 0:
                    self.lap_times.append(me.last)
            self.prev_laps = me.total_laps
            self.start_fuel, self.start_ve = p.fuel, ve
            self.lap_dirty = me.in_pits
            for h in (self.hist_fuel, self.hist_ve, self.lap_times):
                del h[:-self.avg_laps]

        info = FuelInfo(uses_ve=self.uses_ve, fuel_l=p.fuel)
        if self.uses_ve:
            info.unit, info.remaining, info.capacity = "%", ve, 100.0
            hist, start = self.hist_ve, self.start_ve
        else:
            info.unit, info.remaining, info.capacity = "L", p.fuel, p.fuel_capacity
            hist, start = self.hist_fuel, self.start_fuel

        info.samples = len(hist)
        progress = max(0.0, min(1.0, me.lap_dist / s.track_length)) if s.track_length else 0.0
        if hist:
            info.per_lap = sum(hist) / len(hist)
            info.last_lap = hist[-1]
        elif start is not None and progress > 0.25 and not self.lap_dirty:
            used = start - info.remaining
            if used > 0:
                info.per_lap = used / progress
                info.estimating = True

        if info.per_lap > 0:
            info.laps_in_tank = info.remaining / info.per_lap

        # Voltas que faltam até ao fim da sessão
        ref_lap = self._ref_lap(snap)
        if s.max_laps:
            info.race_laps_left = max(0.0, s.max_laps - me.total_laps - progress)
        elif s.time_left is not None and ref_lap > 0:
            t_left = s.time_left
            # o relógio chega a zero a meio de uma volta e ainda se acaba essa volta
            info.race_laps_left = math.ceil(progress + t_left / ref_lap) - progress
        if info.per_lap > 0 and info.race_laps_left > 0:
            info.needed = (info.race_laps_left + self.margin_laps) * info.per_lap
            info.to_add = max(0.0, info.needed - info.remaining)
            if info.to_add > 0 and info.capacity > 0:
                info.stops = math.ceil(info.to_add / info.capacity)
            info.target_per_lap = info.remaining / (info.race_laps_left + self.margin_laps)
        return info

    def _ref_lap(self, snap: Snapshot) -> float:
        if self.lap_times:
            return sum(self.lap_times) / len(self.lap_times)
        for t in (snap.me.best, snap.me.last, snap.me.est_lap):
            if t > 0:
                return t
        return 0.0


# --------------------------------------------------------------------------- #
# Delta para a melhor volta
# --------------------------------------------------------------------------- #
@dataclass
class DeltaInfo:
    has_ref: bool = False
    delta: float = 0.0
    trend: float = 0.0            # variação do delta (s por s)
    ref_time: float = 0.0
    predicted: float = 0.0
    lap_time: float = 0.0
    last: float = 0.0
    best_session: float = 0.0
    ref_label: str = ""
    invalid: bool = False


def _prefix(snap) -> str:
    """Ficheiros guardados (mapas, voltas de referência) separados por simulador.
    O LMU (e o demo) ficam sem prefixo, para continuarem a usar o que já estava guardado."""
    src = getattr(snap, "source", "lmu")
    return "" if src in ("lmu", "demo") else f"{src}__"


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")[:60] or "x"


class DeltaTracker:
    STEP = 5.0  # metros entre pontos guardados

    def __init__(self, store_dir: Path | None) -> None:
        self.store_dir = store_dir
        self.key = None
        self.reset()

    def reset(self) -> None:
        self.trace_d: list[float] = []
        self.trace_t: list[float] = []
        self.prev_laps = None
        self.lap_ok = False
        self.session_ref = None   # (dists, times, laptime)
        self.saved_ref = None
        self.hist: list[tuple[float, float]] = []
        self.last_delta = 0.0
        self._sc_dist = None      # último valor de lap_dist vindo do scoring
        self._sc_seen = 0.0       # quando é que esse valor apareceu

    def _load(self, key: str) -> None:
        self.saved_ref = None
        if not self.store_dir:
            return
        f = self.store_dir / f"{key}.json"
        try:
            data = json.loads(f.read_text("utf-8"))
            self.saved_ref = (data["d"], data["t"], float(data["lap"]))
        except Exception:
            pass

    def _save(self, ref) -> None:
        if not self.store_dir or not self.key:
            return
        try:
            self.store_dir.mkdir(parents=True, exist_ok=True)
            d, t, lap = ref
            (self.store_dir / f"{self.key}.json").write_text(
                json.dumps({"lap": lap, "d": [round(x, 1) for x in d], "t": [round(x, 3) for x in t]}),
                "utf-8")
        except Exception:
            pass

    @staticmethod
    def _interp(ref, dist: float) -> float:
        d, t, _ = ref
        i = bisect.bisect_left(d, dist)
        if i <= 0:
            return t[0] * (dist / d[0]) if d[0] > 0 else t[0]
        if i >= len(d):
            return t[-1]
        d0, d1, t0, t1 = d[i - 1], d[i], t[i - 1], t[i]
        return t0 + (t1 - t0) * (dist - d0) / (d1 - d0) if d1 > d0 else t0

    def update(self, snap: Snapshot, now: float | None = None) -> DeltaInfo:
        me, p, s = snap.me, snap.player, snap.session
        now = time.perf_counter() if now is None else now
        key = f"{_prefix(snap)}{_safe(s.track)}__{_safe(p.vehicle_model or me.vehicle_name)}"
        if key != self.key:
            self.key = key
            self.reset()
            self._load(key)

        L = s.track_length
        if self.prev_laps is None:
            self.prev_laps = me.total_laps
            self.lap_ok = False  # volta a meio quando abrimos a app
        elif me.total_laps != self.prev_laps:
            # volta concluída
            if me.total_laps == self.prev_laps + 1 and self.lap_ok and me.last > 0 and self.trace_d \
                    and self.trace_d[-1] > 0.9 * L:
                ref = (self.trace_d + [L], self.trace_t + [me.last], me.last)
                if self.session_ref is None or me.last < self.session_ref[2]:
                    self.session_ref = ref
                if self.saved_ref is None or me.last < self.saved_ref[2]:
                    self.saved_ref = ref
                    self._save(ref)
            self.prev_laps = me.total_laps
            self.trace_d, self.trace_t = [], []
            self.lap_ok = not me.in_pits
            self.hist.clear()

        # O scoring (lap_dist) só atualiza ~5x/s; a telemetria (tempo) ~100x/s.
        # Entre atualizações extrapola-se a distância com a velocidade: pelo tempo de jogo da
        # telemetria quando existe (exato), senão pelo relógio da app.
        if me.lap_dist != self._sc_dist:
            self._sc_dist, self._sc_seen = me.lap_dist, now
        if p.elapsed > 0 and s.current_et > 0:
            extra = max(0.0, min(0.3, p.elapsed - s.current_et)) * p.speed
        else:
            extra = min(now - self._sc_seen, 0.3) * p.speed
        dist = max(0.0, min(me.lap_dist + extra, L))
        t = p.lap_time_now

        if self.trace_d and dist < self.trace_d[-1] - 0.5 * L:
            # voltou para trás sem fechar volta (reset para as boxes, etc.)
            self.trace_d, self.trace_t, self.lap_ok = [], [], False
        if me.in_pits or p.lap_invalid:
            self.lap_ok = False
        if not self.trace_d or dist >= self.trace_d[-1] + self.STEP:
            if not self.trace_d or t >= self.trace_t[-1]:
                self.trace_d.append(dist)
                self.trace_t.append(t)

        ref = self.session_ref or self.saved_ref
        info = DeltaInfo(lap_time=t, last=me.last, best_session=me.best, invalid=p.lap_invalid)
        if ref is not None and dist > 1.0:
            info.has_ref = True
            info.ref_time = ref[2]
            info.ref_label = "session" if ref is self.session_ref else "saved"
            frac_t, frac_d = t / ref[2], dist / L
            if (frac_d > 0.9 and frac_t < 0.1) or (frac_d < 0.1 and frac_t > 0.9):
                info.delta = self.last_delta   # instante da passagem pela meta: tempo e distância desalinhados
            else:
                info.delta = t - self._interp(ref, dist)
                self.last_delta = info.delta
            info.predicted = ref[2] + info.delta
            self.hist.append((now, info.delta))
            while self.hist and now - self.hist[0][0] > 1.0:
                self.hist.pop(0)
            if len(self.hist) > 2 and self.hist[-1][0] - self.hist[0][0] > 0.2:
                info.trend = (self.hist[-1][1] - self.hist[0][1]) / (self.hist[-1][0] - self.hist[0][0])
        elif 0 < abs(p.delta_game) < 30:
            info.has_ref = True
            info.delta = p.delta_game
            info.ref_label = "game"
            if me.best > 0:
                info.ref_time = me.best
                info.predicted = me.best + info.delta
        return info


# --------------------------------------------------------------------------- #
# Desgaste dos pneus por volta
# --------------------------------------------------------------------------- #
class WearTracker:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.prev_laps = None
        self.start = None
        self.per_lap = [0.0, 0.0, 0.0, 0.0]   # pontos percentuais por volta
        self.dirty = True

    def update(self, snap: Snapshot) -> list[float]:
        wear = [t.wear for t in snap.player.tyres]
        if self.start and any(w > s0 + 0.02 for w, s0 in zip(wear, self.start)):
            self.dirty = True  # pneus trocados
        if snap.me.in_pits:
            self.dirty = True
        if self.prev_laps is None:
            self.prev_laps, self.start = snap.me.total_laps, wear
        elif snap.me.total_laps != self.prev_laps:
            if not self.dirty and snap.me.total_laps == self.prev_laps + 1:
                self.per_lap = [max(0.0, (s0 - w) * 100) for s0, w in zip(self.start, wear)]
            self.prev_laps, self.start, self.dirty = snap.me.total_laps, wear, snap.me.in_pits
        return self.per_lap


# --------------------------------------------------------------------------- #
# Mapa da pista (gravado a partir da tua própria volta)
# --------------------------------------------------------------------------- #
@dataclass
class TrackMap:
    length: float
    pts: list[tuple[float, float, float]]   # (distância, x, z)
    sectors: list[float]                    # distâncias onde começam S2 e S3


class TrackMapRecorder:
    STEP = 6.0

    def __init__(self, store_dir: Path | None) -> None:
        self.store_dir = store_dir
        self.key = None
        self.map: TrackMap | None = None
        self.reset_lap()

    def reset_lap(self) -> None:
        self.buf: list[tuple[float, float, float]] = []
        self.sec: list[float] = []
        self.prev_laps = None
        self.prev_sector = None
        self.lap_ok = False

    def progress(self, L: float) -> float:
        if self.map:
            return 0.0
        if getattr(self, "bins", None):
            return self.progress_all(L)
        if not self.buf or not self.lap_ok:
            return 0.0
        return max(0.0, min(1.0, self.buf[-1][0] / L))

    def _load(self) -> None:
        self.map = None
        if not self.store_dir:
            return
        try:
            data = json.loads((self.store_dir / f"{self.key}.json").read_text("utf-8"))
            self.map = TrackMap(float(data["length"]), [tuple(p) for p in data["pts"]], list(data.get("sectors", [])))
        except Exception:
            pass

    def _save(self) -> None:
        if not self.store_dir or not self.map:
            return
        try:
            self.store_dir.mkdir(parents=True, exist_ok=True)
            pts = [[round(d, 1), round(x, 2), round(z, 2)] for d, x, z in self.map.pts]
            (self.store_dir / f"{self.key}.json").write_text(
                json.dumps({"length": self.map.length, "pts": pts, "sectors": self.map.sectors}), "utf-8")
        except Exception:
            pass

    @staticmethod
    def _closed(buf: list, L: float) -> list:
        """Fecha a volta: se o traçado foi calculado a partir da velocidade (iRacing), o fim não
        bate certo com o início; o erro é repartido ao longo da volta. No LMU o erro é ~0."""
        if len(buf) < 3 or L <= 0:
            return list(buf)
        (d1, x1, z1), (d2, x2, z2) = buf[-2], buf[-1]
        n = math.hypot(x2 - x1, z2 - z1)
        if n <= 0 or d2 <= d1:
            return list(buf)
        k = (L - d2) / n                                  # prolonga até à meta
        ex, ez = x2 + (x2 - x1) * k, z2 + (z2 - z1) * k
        ox, oz = ex - buf[0][1], ez - buf[0][2]
        if math.hypot(ox, oz) > 0.25 * L:                 # erro grande demais: deixa como está
            return list(buf)
        return [(d, x - ox * d / L, z - oz * d / L) for d, x, z in buf]

    def update(self, snap: Snapshot) -> None:
        s, me = snap.session, snap.me
        key = _prefix(snap) + _safe(s.track)
        if key != self.key:
            self.key = key
            self._load()
            self.reset_lap()
            self.bins: dict[int, list] = {}
            self.s2: list[float] = []
            self.s3: list[float] = []
            self._vsec: dict[int, int] = {}
            self._sec_saved = bool(self.map and len(self.map.sectors) >= 2)
        L = s.track_length
        if L <= 0:
            return
        self._sectors(snap, L)
        if self.map is not None:
            return
        if snap.world_pos:
            self._from_all_cars(snap, L)
        else:
            self._from_my_lap(snap, L)

    # ---- setores: onde cada carro muda de S1->S2 e S2->S3 (mediana de várias passagens) ---- #
    def _sectors(self, snap, L) -> None:
        for v in snap.vehicles:
            prev = self._vsec.get(v.id)
            if prev is not None and v.sector != prev and not v.in_pits and v.lap_dist > 0:
                if prev == 0 and v.sector == 1:
                    self.s2.append(v.lap_dist)
                elif prev == 1 and v.sector == 2:
                    self.s3.append(v.lap_dist)
            self._vsec[v.id] = v.sector
        del self.s2[:-31], self.s3[:-31]
        if self.map is not None and self.s2 and self.s3:
            sec = [statistics.median(self.s2), statistics.median(self.s3)]
            if sec[0] < sec[1] and (not self.map.sectors or len(self.map.sectors) < 2
                                    or max(abs(x - y) for x, y in zip(sec, self.map.sectors)) > 15):
                self.map.sectors = sec
            if not self._sec_saved and len(self.s2) >= 3 and len(self.s3) >= 3:
                self._sec_saved = True
                self._save()

    # ---- LMU: posições de todos os carros (ficam em segundos com o grid em pista) ---------- #
    def _from_all_cars(self, snap, L) -> None:
        step = self.STEP
        for v in snap.vehicles:
            if v.in_pits or v.in_garage or v.speed < 8 or not (0 < v.lap_dist < L):
                continue
            x, _, z = snap.player.pos if v.is_player and any(snap.player.pos) else v.pos
            if x == 0 and z == 0:
                continue
            b = self.bins.setdefault(int(v.lap_dist / step), [0.0, 0.0, 0])
            if b[2] < 6:                       # chega uma média de poucas passagens
                b[0] += x
                b[1] += z
                b[2] += 1
        n = int(math.ceil(L / step))
        if len(self.bins) < 0.96 * n:
            return
        idx = sorted(self.bins)
        holes = max([b - a for a, b in zip(idx, idx[1:])] + [idx[0] + n - idx[-1]])
        if holes * step > 60:
            return
        pts = [((i + 0.5) * step, self.bins[i][0] / self.bins[i][2], self.bins[i][1] / self.bins[i][2]) for i in idx]
        sec = [statistics.median(self.s2), statistics.median(self.s3)] if self.s2 and self.s3 else []
        self.map = TrackMap(L, pts, sec)
        self._save()

    def progress_all(self, L: float) -> float:
        if self.map or L <= 0 or not getattr(self, "bins", None):
            return 0.0
        return min(1.0, len(self.bins) / (L / self.STEP) / 0.96)

    # ---- iRacing (sem posições dos outros): a tua própria volta ------------------------------ #
    def _from_my_lap(self, snap, L) -> None:
        me = snap.me
        if self.prev_laps is None:
            self.prev_laps = me.total_laps
            return
        if me.total_laps != self.prev_laps:
            ok = self.lap_ok and len(self.buf) > 20 and self.buf[0][0] < 80 and self.buf[-1][0] > L - 120
            if ok:
                gaps = [b[0] - a[0] for a, b in zip(self.buf, self.buf[1:])]
                ok = max(gaps) < 150
            if ok:
                bounds = getattr(snap.session, "sector_bounds", ())
                sec = [bounds[0] * L, bounds[1] * L] if len(bounds) == 2 else sorted(self.sec)[:2]
                self.map = TrackMap(L, self._closed(self.buf, L), sec)
                self._save()
                return
            self.buf, self.sec = [], []
            self.prev_laps = me.total_laps
            self.lap_ok = not me.in_pits
            self.prev_sector = me.sector
            return
        if me.in_pits:
            self.lap_ok = False
        if self.prev_sector is not None and me.sector != self.prev_sector and me.sector in (1, 2):
            self.sec.append(me.lap_dist)
        self.prev_sector = me.sector
        x, _, z = snap.player.pos
        if not self.buf or me.lap_dist >= self.buf[-1][0] + self.STEP:
            self.buf.append((me.lap_dist, x, z))


# --------------------------------------------------------------------------- #
# Histórico dos comandos (para o gráfico)
# --------------------------------------------------------------------------- #
class InputHistory:
    def __init__(self, seconds: float = 6.0) -> None:
        self.seconds = seconds
        self.buf: list[tuple[float, float, float, float, float]] = []

    def update(self, snap: Snapshot, now: float) -> list:
        p = snap.player
        self.buf.append((now, p.throttle, p.brake, p.clutch, p.steering, p.abs_active, p.tc_active))
        cut = now - self.seconds
        i = 0
        while i < len(self.buf) and self.buf[i][0] < cut:
            i += 1
        if i:
            del self.buf[:i]
        return self.buf


# --------------------------------------------------------------------------- #
# Eventos (para os overlays aparecerem só quando interessa)
# --------------------------------------------------------------------------- #
class EventTracker:
    """Regista quando aconteceram coisas ao jogador: volta, setor, posição, boxes."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.t: dict[str, float] = {}
        self._laps = None
        self._sector = None
        self._place = None
        self._in_pits = None
        self.radio: list = []                 # (instante, id do carro, "req" = pediu boxes | "in" = entrou)
        self._pit: dict[int, tuple] = {}      # id -> (pit_state, in_pits) da leitura anterior
        self._tl = None                       # pontos de track limits / incidentes na leitura anterior
        self.tl_lap_start = None              # pontos no início desta volta
        self.tl_last_lap = 0.0                # quantos se apanharam na volta anterior (0 = volta limpa)
        self.tl_last_add = 0.0                # quanto subiu da última vez
        self._impact = None
        self._dents = None
        self.hits: list = []                  # (instante, índice do painel, nível novo): onde bateu

    def update(self, snap: Snapshot, now: float) -> dict[str, float]:
        me = snap.me
        if self._laps is None:
            self.t["start"] = now
        else:
            if me.total_laps != self._laps:
                self.t["lap"] = now
            if me.sector != self._sector:
                self.t["sector"] = now
            if me.class_place != self._place:
                self.t["pos"] = now
            if self._in_pits and not me.in_pits:
                self.t["pit_exit"] = now
        p = snap.player
        if p.tl_points >= 0:                              # track limits / incidentes
            if self._tl is not None and p.tl_points > self._tl + 1e-6:
                self.t["tl"] = now
                self.tl_last_add = p.tl_points - self._tl
            if self.tl_lap_start is None:
                self.tl_lap_start = p.tl_points
            if self._laps is not None and me.total_laps != self._laps:
                self.tl_last_lap = p.tl_points - self.tl_lap_start
                self.tl_lap_start = p.tl_points
                self.t["lap_clean" if self.tl_last_lap <= 1e-6 else "lap_dirty"] = now
            self._tl = p.tl_points
        if p.impact_et > 0 and self._impact is not None and p.impact_et != self._impact and p.impact_mag > 0:
            self.t["impact"] = now                        # toque / dano novo
        self._impact = p.impact_et
        if p.dents:                                       # que painéis pioraram (= onde foi o toque)
            if self._dents is not None and len(self._dents) == len(p.dents):
                for i, (a, b) in enumerate(zip(self._dents, p.dents)):
                    if b > a:
                        self.hits.append((now, i, b))
                self.hits = self.hits[-12:]
            if self._dents is not None and sum(p.dents) < sum(self._dents):
                self.hits = []                            # reparado nas boxes
            self._dents = tuple(p.dents)
        self._laps, self._sector, self._place, self._in_pits = me.total_laps, me.sector, me.class_place, me.in_pits
        self._radio(snap, now)
        return self.t

    def _radio(self, snap: Snapshot, now: float) -> None:
        """Pedidos de boxes (de todos os carros) para o cartão de rádio."""
        seen = self._pit
        recent_req = {vid for t, vid, k in self.radio if k == "req" and now - t < 180}
        for v in snap.vehicles:
            prev = seen.get(v.id)
            if prev is not None:
                ps, ip = prev
                if v.pit_state == 1 and ps != 1:
                    self.radio.append((now, v.id, "req"))
                elif v.in_pits and not ip and v.id not in recent_req and not v.is_player:
                    self.radio.append((now, v.id, "in"))
            seen[v.id] = (v.pit_state, v.in_pits)
        if self.radio and now - self.radio[0][0] > 200:
            self.radio = [e for e in self.radio if now - e[0] <= 200][-12:]



class WeatherTracker:
    """Guarda chuva e água na pista ao longo do tempo (para a tendência e a previsão)."""

    def __init__(self) -> None:
        self.hist: list[tuple[float, float, float]] = []   # (tempo de jogo, chuva, água)

    def reset(self) -> None:
        self.hist = []

    def update(self, snap: Snapshot) -> list:
        s = snap.session
        t = s.current_et
        if self.hist and t < self.hist[-1][0]:
            self.hist = []
        if not self.hist or t - self.hist[-1][0] >= 2.0:
            self.hist.append((t, s.rain, s.wetness))
            while self.hist and t - self.hist[0][0] > 900:
                self.hist.pop(0)
        return self.hist


# --------------------------------------------------------------------------- #
@dataclass
class Context:
    fuel: FuelInfo = field(default_factory=FuelInfo)
    delta: DeltaInfo = field(default_factory=DeltaInfo)
    wear_per_lap: list[float] = field(default_factory=lambda: [0.0] * 4)
    track_map: TrackMap | None = None
    map_progress: float = 0.0
    inputs: list = field(default_factory=list)
    pit_stop_since: float = 0.0   # instante em que o carro parou na box (0 = não está parado)
    now: float = 0.0
    edit_mode: bool = False
    blink: bool = True            # alterna 2x por segundo (bandeiras a piscar)
    cfg: dict = field(default_factory=dict)  # opções globais (unidades, etc.)
    green_until: float = 0.0      # mostrar bandeira verde até este instante
    events: dict = field(default_factory=dict)   # nome -> instante (lap, sector, pos, pit_exit, start)
    peek_until: float = 0.0       # "espreitar": mostra tudo completo até este instante
    focus_field: int = 0          # campo da torre escolhido por botão (0 = automático)
    radio: list = field(default_factory=list)    # pedidos de boxes: (instante, id do carro, tipo)
    weather: list = field(default_factory=list)  # histórico (tempo de jogo, chuva, água na pista)
    tl_last_lap: float = 0.0      # track limits apanhados na volta anterior
    tl_last_add: float = 0.0      # quanto subiu da última vez
    hits: list = field(default_factory=list)     # danos novos: (instante, painel, nível)
    avg5: dict = field(default_factory=dict)     # id do carro -> média das últimas 5 voltas
    sec_delta: list = field(default_factory=lambda: [None, None, None])   # ganho/perda em cada setor desta volta
    sec_last: list = field(default_factory=lambda: [None, None, None])    # ... da volta anterior

    def since(self, name: str) -> float:
        """Segundos desde o evento (infinito se nunca aconteceu)."""
        t = self.events.get(name)
        return float("inf") if t is None else self.now - t

    @property
    def peek(self) -> bool:
        return self.now < self.peek_until


class LapAvgTracker:
    """Média das últimas N voltas de cada carro (sem voltas de boxes nem voltas inválidas)."""

    def __init__(self, n: int = 5) -> None:
        self.n = n
        self.reset()

    def reset(self) -> None:
        self.laps: dict[int, list] = {}
        self._seen: dict[int, int] = {}
        self._pitted: dict[int, bool] = {}
        self.avg: dict[int, float] = {}

    def update(self, snap: Snapshot) -> dict[int, float]:
        for v in snap.vehicles:
            if v.in_pits:
                self._pitted[v.id] = True
            prev = self._seen.get(v.id)
            if prev is not None and v.total_laps > prev:
                if v.last > 0 and not self._pitted.get(v.id) and v.total_laps - prev == 1:
                    lst = self.laps.setdefault(v.id, [])
                    lst.append(v.last)
                    del lst[:-self.n]
                    self.avg[v.id] = sum(lst) / len(lst)
                self._pitted[v.id] = v.in_pits
            self._seen[v.id] = v.total_laps
        return self.avg


class Trackers:
    def __init__(self, data_dir: Path | None, avg_laps: int = 5, margin_laps: float = 0.5) -> None:
        self.fuel = FuelTracker(avg_laps, margin_laps)
        self.delta = DeltaTracker(data_dir / "delta_refs" if data_dir else None)
        self.wear = WearTracker()
        self.map = TrackMapRecorder(data_dir / "track_maps" if data_dir else None)
        self.inputs = InputHistory()
        self.events = EventTracker()
        self.weather = WeatherTracker()
        self.laps = LapAvgTracker(5)
        self.ctx = Context()
        self._key = None
        self._last_et = 0.0
        self._last_phase = 0
        self._last_pit_state = 0
        self.track_inputs = True   # a app desliga isto quando o gráfico de comandos está escondido

    def update(self, snap: Snapshot | None, now: float | None = None) -> Context:
        now = time.perf_counter() if now is None else now
        self.ctx.now = now
        self.ctx.blink = int(now * 2) % 2 == 0
        if snap is None:
            return self.ctx
        s = snap.session
        key = (s.track, s.raw, snap.player.vehicle_model)
        if key != self._key or s.current_et < self._last_et - 5:
            self._key = key
            self.fuel.reset()
            self.wear.reset()
            self.delta.prev_laps = None
            self.delta.session_ref = None
            self.map.reset_lap()
            self.events.reset()
            self.weather.reset()
            self.laps.reset()
        self._last_et = s.current_et
        # Bandeira verde (partida/recomeço) durante alguns segundos
        if s.phase == 5 and self._last_phase in (3, 4, 6):
            self.ctx.green_until = now + float(self.ctx.cfg.get("green_flag_seconds", 5))
        self._last_phase = s.phase
        # cronómetro da paragem
        ps = snap.me.pit_state
        if ps == 3 and self._last_pit_state != 3:
            self.ctx.pit_stop_since = now
        elif ps != 3:
            self.ctx.pit_stop_since = 0.0
        self._last_pit_state = ps

        self.ctx.fuel = self.fuel.update(snap)
        self.ctx.delta = self.delta.update(snap, now)
        self.ctx.wear_per_lap = self.wear.update(snap)
        self.map.update(snap)
        self.ctx.track_map = self.map.map
        self.ctx.map_progress = self.map.progress(s.track_length)
        self.ctx.inputs = self.inputs.update(snap, now) if self.track_inputs else self.ctx.inputs
        self.ctx.events = self.events.update(snap, now)
        self.ctx.radio = self.events.radio
        self.ctx.tl_last_lap = self.events.tl_last_lap
        self.ctx.hits = self.events.hits
        self.ctx.tl_last_add = self.events.tl_last_add
        self.ctx.weather = self.weather.update(snap)
        self.ctx.avg5 = self.laps.update(snap)
        self._sector_deltas(snap)
        return self.ctx

    def _sector_deltas(self, snap) -> None:
        """Quanto ganhaste/perdeste em cada setor (pelo delta para a volta de referência)."""
        sec, d = snap.me.sector, self.ctx.delta
        prev = getattr(self, "_sd_sec", None)
        if prev is None:
            self._sd_sec, self._sd_start = sec, d.delta
            return
        if sec != prev:
            cur = self.ctx.sec_delta
            if d.has_ref and 0 <= prev < 3:
                end = self._sd_last_delta if sec == 0 else d.delta    # na meta o delta volta a 0
                cur[prev] = end - self._sd_start
            if sec == 0:
                self.ctx.sec_last = list(cur)
                self.ctx.sec_delta = [None, None, None]
                self._sd_start = 0.0
            else:
                self._sd_start = d.delta
            self._sd_sec = sec
        self._sd_last_delta = d.delta
