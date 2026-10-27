"""Fonte de dados simulada: uma corrida multiclasse num circuito inventado,
para testar e posicionar os overlays sem o jogo (modo demo)."""

from __future__ import annotations

import bisect
import math
import random
import time

from .model import Player, Session, Snapshot, Tyre, Vehicle, assign_class_places

TRACK = "Demo Circuit"
L = 5412.0

CLASSES = [  # nome cru como o LMU o envia, volta base (s), carros
    ("Hyper", 107.0, ["Toyota GR010", "Ferrari 499P", "Porsche 963", "Cadillac V-Series.R",
                      "BMW M Hybrid V8", "Alpine A424", "Peugeot 9X8", "Aston Martin Valkyrie"]),
    ("LMP2", 112.5, ["Oreca 07"] * 5),
    ("LMP3", 124.0, ["Ligier JS P325", "Ginetta G61-LT-P3-25", "Duqueine D09"] * 2),
    ("GT3", 121.0, ["Ferrari 296 LMGT3", "Porsche 911 LMGT3 R", "BMW M4 LMGT3", "Aston Martin Vantage LMGT3",
                    "Lexus RC F LMGT3", "McLaren 720S LMGT3 Evo", "Corvette Z06 LMGT3.R", "Ford Mustang LMGT3",
                    "Mercedes-AMG LMGT3", "Lamborghini Huracan LMGT3 Evo2"]),
]
# nomes de equipa (como o LMU os põe no nome do carro); o resto usa o modelo
TEAMS = {"Toyota GR010": "Toyota Gazoo Racing", "Ferrari 499P": "Ferrari AF Corse", "Porsche 963": "Porsche Penske Motorsport",
         "Cadillac V-Series.R": "Cadillac Hertz Team Jota", "BMW M Hybrid V8": "BMW M Team WRT",
         "Alpine A424": "Alpine Endurance Team", "Peugeot 9X8": "Peugeot TotalEnergies",
         "Aston Martin Valkyrie": "Aston Martin Thor Team"}
FIRST = ["Lucas", "Mateo", "Kenji", "Antonio", "Kevin", "Sebastien", "Nicolas", "Rui", "Felipe", "Tom",
         "Marco", "Alex", "Daniel", "Pietro", "Jonas", "Yuki", "Oliver", "Hugo", "Filipe", "Nico",
         "Luca", "Mikkel", "Sam", "Andre", "Raffaele", "Earl", "Ben", "Jack", "Ian", "Matt", "Leo"]
LAST = ["Silva", "Moreau", "Tanaka", "Rossi", "Muller", "Dupont", "Costa", "Hansen", "Albuquerque", "Kubica",
        "Vanthoor", "Lynn", "Estre", "Calado", "Nato", "Buemi", "Hartley", "Jarvis", "Rast", "Pier Guidi",
        "Fuoco", "Bamber", "Ferreira", "Lotterer", "Derani", "Gounon", "Habsburg", "Laurens", "Stevens"]


class _Track:
    """Traçado fechado parametrizado por distância, com curvatura e perfil de velocidade."""

    N = 1600

    def __init__(self) -> None:
        raw = []
        for i in range(self.N):
            th = 2 * math.pi * i / self.N
            x = math.cos(th) + 0.30 * math.cos(2 * th) - 0.12 * math.sin(3 * th) + 0.05 * math.cos(5 * th)
            z = 0.62 * math.sin(th) - 0.18 * math.sin(2 * th) + 0.10 * math.cos(3 * th) + 0.06 * math.sin(4 * th)
            raw.append((x, z))
        seg = [math.dist(raw[i], raw[(i + 1) % self.N]) for i in range(self.N)]
        k = L / sum(seg)
        self.pts = [(x * k, z * k) for x, z in raw]
        self.cum = [0.0]
        for s in seg[:-1]:
            self.cum.append(self.cum[-1] + s * k)
        # direção e curvatura em cada ponto
        self.head = []
        for i in range(self.N):
            (x0, z0), (x1, z1) = self.pts[i], self.pts[(i + 1) % self.N]
            self.head.append(math.atan2(z1 - z0, x1 - x0))
        curv = []
        for i in range(self.N):
            dh = (self.head[(i + 1) % self.N] - self.head[i] + math.pi) % (2 * math.pi) - math.pi
            curv.append(dh / max(1e-6, seg[i] * k))
        win = 12
        self.curv = [sum(curv[(i + j) % self.N] for j in range(-win, win + 1)) / (2 * win + 1) for i in range(self.N)]
        cmax = max(abs(c) for c in self.curv) or 1
        raw_slope = [0.72 + 1.15 * (abs(c) / cmax) ** 0.7 for c in self.curv]
        # trava-se antes da curva: média deslocada para a frente
        sm = [sum(raw_slope[(i + j) % self.N] for j in range(0, 40)) / 40 for i in range(self.N)]
        mean = sum(sm) / self.N
        self.slope = [s / mean for s in sm]
        self.cmax = cmax

    def _i(self, p: float) -> tuple[int, float]:
        s = (p % 1.0) * L
        i = max(0, bisect.bisect_right(self.cum, s) - 1)
        nxt = self.cum[i + 1] if i + 1 < self.N else L
        return i, (s - self.cum[i]) / max(1e-6, nxt - self.cum[i])

    def at(self, p: float):
        i, f = self._i(p)
        (x0, z0), (x1, z1) = self.pts[i], self.pts[(i + 1) % self.N]
        return x0 + (x1 - x0) * f, z0 + (z1 - z0) * f, self.head[i]

    def slope_at(self, p: float) -> float:
        return self.slope[self._i(p)[0]]

    def curv_at(self, p: float) -> float:
        return self.curv[self._i(p)[0]] / self.cmax


class _Car:
    def __init__(self, idx, cls, base, model, driver, number, rng):
        self.id = idx
        self.cls = cls
        self.base = base + rng.uniform(-0.8, 1.6)
        self.model = model
        self.driver = driver
        self.number = number
        self.rng = rng
        self.laps = 0
        self.p = 0.0
        self.tau = 0.0
        self.best = 0.0
        self.last = 0.0
        self.T = self.base
        self.sector_f = [1.0, 1.0, 1.0]
        self.pitstops = 0
        self.pit_until = -1.0
        self.stopped_until = -1.0
        self.speed = 0.0
        self.lane = (1 if idx % 2 else -1) * (2.6 + (idx % 3) * 0.5)
        self.lane_override = None

    def new_lap_pace(self, is_player):
        self.T = self.base + self.rng.gauss(0.25, 0.35)
        if is_player:
            self.sector_f = [1 + self.rng.gauss(0, 0.004) for _ in range(3)]

    def advance(self, dt, now, is_player, track):
        if now < self.stopped_until:
            self.speed = 0.0
            self.tau += dt
            return
        f = self.sector_f[min(2, int(self.p * 3))] if is_player else 1.0
        slow = 0.38 if now < self.pit_until else 1.0
        dp = dt / (self.T * f * track.slope_at(self.p)) * slow
        self.speed = dp * L / dt if dt > 0 else self.speed
        self.p += dp
        self.tau += dt
        if self.p >= 1.0:
            self.p -= 1.0
            self.laps += 1
            lap_time = self.tau - self.p * self.T
            self.tau = self.p * self.T
            if self.laps > 0:  # a passagem da grelha para a meta não é uma volta
                self.last = lap_time
                if lap_time > 0 and (self.best <= 0 or lap_time < self.best):
                    self.best = lap_time
            self.new_lap_pace(is_player)


class DemoSource:
    label = "Demo"

    def __init__(self, seed: int = 11, time_scale: float = 1.0) -> None:
        self.rng = random.Random(seed)
        self.track = _Track()
        self.time_scale = time_scale
        self.status = ("demo", "")
        self.race_len = 3600.0
        self.t = 0.0
        self.cars: list[_Car] = []
        names = [f"{f} {l}" for f, l in zip(self.rng.sample(FIRST, 30), self.rng.sample(LAST, 29) + ["Leonardo"])]
        nums = {"Hyper": [7, 8, 50, 51, 6, 5, 15, 20], "LMP2": [22, 23, 28, 37, 43],
                "LMP3": [4, 11, 17, 31, 88, 12], "GT3": [21, 27, 31, 33, 46, 54, 59, 60, 61, 77]}
        idx = 0
        for cls, base, models in CLASSES:
            for k, model in enumerate(models):
                self.cars.append(_Car(idx, cls, base, model, names[idx % len(names)], str(nums[cls][k]), self.rng))
                idx += 1
        self.player = self.cars[3]
        self.player.driver = "Leonardo Silva"
        self.player.base = 107.6
        self.player.lane = 0.0
        for g, c in enumerate(self.cars):
            c.p = 1.0 - 0.0016 * (g + 1)
            c.laps = -1
            c.new_lap_pace(c is self.player)
        self.ve_per_lap = 3.65
        self.fuel_per_lap = 2.95
        self.pit_box = 0.018 * L
        self.override_flags: dict | None = None
        self.override_me: dict = {}
        self.override_player: dict = {}
        self._wall = None
        self.step(23 * 60.0)

    # ------------------------------------------------------------------ #
    def step(self, dt: float) -> None:
        while dt > 0:
            h = min(dt, 0.05)
            self.t += h
            dt -= h
            for c in self.cars:
                c.advance(h, self.t, c is self.player, self.track)
            self._events()

    def _pit_lap(self, c) -> bool:
        return c is not self.player and c.laps > 0 and c.laps % 13 == (c.id % 13) and c.pit_until < self.t

    def _wants_pit(self, c) -> bool:
        """Pediu boxes nesta volta (para o cartão de rádio)."""
        return self._pit_lap(c) and 0.80 < c.p < 0.95

    def _events(self):
        t = self.t
        for c in self.cars:
            if self._pit_lap(c) and 0.95 < c.p < 0.951:
                c.pit_until = t + 34
                c.pitstops += 1
        cyc = t % 240
        if 40 <= cyc < 40.06 and not any(c.stopped_until > t for c in self.cars):
            pc = self.player
            cands = [c for c in self.cars if c is not pc and 300 < ((c.p - pc.p) % 1.0) * L < 1500]
            if cands:
                min(cands, key=lambda c: abs(((c.p - pc.p) % 1.0) * L - 700)).stopped_until = t + 22

    def force_alongside(self, side: int = 1, dz: float = -1.0) -> None:
        """Põe um carro ao lado do jogador (para testar o ângulo morto). side +1 = esquerda."""
        pc = self.player
        other = min((c for c in self.cars if c is not pc and c.lane_override is None),
                    key=lambda c: abs(((c.p - pc.p + 0.5) % 1.0) - 0.5))
        other.p = (pc.p + dz / L) % 1.0
        other.lane_override = 3.1 * side

    def read(self) -> Snapshot:
        now = time.perf_counter()
        if self._wall is not None:
            self.step((now - self._wall) * self.time_scale)
        self._wall = now
        return self.snapshot()

    # ------------------------------------------------------------------ #
    def _world(self, c: _Car):
        x, z, hd = self.track.at(c.p)
        fx, fz = math.cos(hd), math.sin(hd)
        lane = c.lane_override if c.lane_override is not None else c.lane + 0.8 * math.sin(self.t * 0.2 + c.id)
        if c is self.player:
            lane = 0.0
        lx, lz = -fz, fx                     # esquerda do carro (mundo esquerdo, y para cima)
        return (x + lx * lane, 0.0, z + lz * lane), (fx, 0.0, fz)

    def snapshot(self) -> Snapshot:
        t = self.t
        trk = self.track
        order = sorted(self.cars, key=lambda c: -(c.laps + c.p))
        lead = order[0]
        vehicles = []
        for place, c in enumerate(order, 1):
            gap_laps = (lead.laps + lead.p) - (c.laps + c.p)
            pos, fwd = self._world(c)
            vehicles.append(Vehicle(
                id=c.id, driver=c.driver, vehicle_name=f"{TEAMS.get(c.model, c.model)} #{c.number}", number=c.number,
                cls=c.cls,
                place=place, total_laps=max(0, c.laps), lap_dist=c.p * L, best=c.best, last=c.last,
                t_behind_leader=gap_laps * lead.T, laps_behind_leader=int(gap_laps),
                in_pits=t < c.pit_until, pit_state=3 if t < c.pit_until else (1 if self._wants_pit(c) else 0),
                pitstops=c.pitstops,
                is_player=c is self.player, speed=c.speed, time_into_lap=c.tau, est_lap=c.base,
                sector=min(2, int(c.p * 3)), pos=pos, fwd=fwd, pit_lap_dist=self.pit_box,
                fuel_frac=max(0.04, 1.0 - ((c.laps + c.p + c.id * 0.7) % 14) / 14.0),
                sr=("BRZ", "SLV", "GLD", "PLT")[(c.id * 7) % 4],
                dr=("B3", "S1", "S2", "S3", "S2", "G1", "S3", "P1")[(c.id * 3 + 1) % 8],
                dr_pct=((c.id * 37) % 10) / 10.0, dr_delta=(((c.id * 53) % 21) - 8) / 100.0 * 4,
                country=("PRT", "FRA", "GBR", "ITA", "DEU", "ESP", "NLD", "BRA")[(c.id * 5) % 8],
                tyre=("M", "M", "H", "S")[c.id % 4],
            ))
        assign_class_places(vehicles)
        me = next(v for v in vehicles if v.is_player)

        pc = self.player
        laps_in_stint = (pc.laps + pc.p) % 24  # 'paragem' a cada 24 voltas
        ve = max(0.0, 100.0 - laps_in_stint * self.ve_per_lap)
        fuel = max(0.0, 88.0 - laps_in_stint * self.fuel_per_lap)
        tyres = []
        base_temps = [(84, 89, 93), (92, 88, 83), (88, 92, 95), (96, 91, 86)]
        for i in range(4):
            wob = 3.5 * math.sin(t * 0.7 + i) + 6 * math.sin(2 * math.pi * 3 * pc.p + i * 0.5)
            lcr = tuple(b + wob + (2 if i in (2, 3) else 0) for b in base_temps[i])
            tyres.append(Tyre(
                temp_lcr=lcr, inner_lcr=tuple(x + 6 for x in lcr), carcass=sum(lcr) / 3 - 2 + 0.5 * i,
                pressure=171.0 + 2.5 * math.sin(t * 0.3 + i) + (1.5 if i % 2 else 0),
                wear=1.0 - laps_in_stint * (0.0105 + 0.0012 * i) % 0.6, optimal=88.0,
                brake_temp=430 + 180 * max(0, math.sin(2 * math.pi * 3 * pc.p + 1.2)) - (60 if i > 1 else 0),
            ))

        # comandos, mudança e RPM a partir do perfil de velocidade da pista
        kmh = pc.speed * 3.6
        here = trk.slope_at(pc.p)
        ahead = trk.slope_at(pc.p + 0.01)
        rv = here / ahead - 1.0                    # >0 vai acelerar, <0 vai travar
        brake = max(0.0, min(1.0, (-rv - 0.04) * 4.5))
        if brake > 0.02:
            throttle = 0.0
        elif rv > 0.015:
            throttle = 1.0
        else:
            throttle = max(0.45, min(1.0, 0.8 + rv * 12 + 0.05 * math.sin(t * 7)))
        bands = [0, 95, 135, 170, 205, 240, 275, 330]
        gear = max(1, min(7, bisect.bisect_right(bands, kmh)))
        lo, hi = bands[gear - 1], bands[gear]
        rpm = 4300 + (8900 - 4300) * max(0.0, min(1.0, (kmh - lo) / (hi - lo)))
        steer = max(-1.0, min(1.0, trk.curv_at(pc.p) * 0.9 + 0.03 * math.sin(t * 3)))
        pos, fwd = self._world(pc)
        fx, fz = fwd[0], fwd[2]
        ori = ((-fz, 0.0, -fx), (0.0, 1.0, 0.0), (fx, 0.0, -fz))
        player = Player(
            id=pc.id, vehicle_model=pc.model, fuel=fuel, fuel_capacity=90.0, virtual_energy=ve / 100.0,
            battery=0.55 + 0.35 * math.sin(t * 0.15),
            lap_time_now=pc.tau, lap_invalid=False, delta_game=0.0, speed=pc.speed, rpm=rpm, max_rpm=9000,
            gear=gear, max_gears=7, water_temp=86 + 6 * math.sin(t * 0.05) + (14 if 150 <= t % 240 < 175 else 0),
            oil_temp=104 + 5 * math.sin(t * 0.04 + 1),
            throttle=throttle, brake=brake, clutch=0.0, steering=steer, throttle_f=throttle * (0.85 if gear <= 2 else 1),
            brake_f=brake, steering_range=380.0, tc=3, tc_max=11, tc_cut=2, tc_slip=4, abs=4, abs_max=12,
            tc_active=throttle > 0.9 and gear <= 3, abs_active=brake > 0.8, brake_bias=54.5, motor_map=2,
            limiter_on=False, compound_front="Medium", compound_rear="Medium", tyres=tyres, pos=pos, ori=ori,
        )

        cyc = t % 240
        # track limits (2 por ciclo), toques/danos e híbrido
        player.tl_points, player.tl_limit = float((int(t // 240) * 2 + (cyc > 60) + (cyc > 150)) % 6), 5.0
        if t > 600:
            player.dents = (0, 1, 0, 0, 0, 0, 2 if t > 900 else 0, 0)
            player.impact_et, player.impact_mag = t - (cyc - 100 if cyc > 100 else cyc + 140), 1800.0
        else:
            player.dents = (0,) * 8
        player.boost_temp = 58 + 8 * math.sin(t * 0.03)
        hit = max(0.0, min(1.0, (t - 600) / 900))
        player.aero_damage = 0.18 * hit
        player.susp_damage = (0.0, 0.05 * hit, 0.42 * hit, 0.0)
        player.brake_wear = tuple(0.2 + 0.01 * ((t / 60) % 40) + 0.02 * i for i in range(4))
        if player.water_temp > 100:
            player.warnings |= 1
        phase, ystate, sflags = 5, 0, [0, 0, 0]
        for c in self.cars:
            if c.stopped_until > t:
                sflags[min(2, int(c.p * 3))] = 1
        if 120 <= cyc < 128:
            me.flag = 6
        if 180 <= cyc < 205:
            phase, ystate = 6, 4
        if 205 <= cyc < 235:
            me.pit_state = 1  # pediu boxes: mostra a ajuda nas boxes
        if self.override_flags:
            phase = self.override_flags.get("phase", phase)
            ystate = self.override_flags.get("yellow_state", ystate)
            sflags = list(self.override_flags.get("sector_flags", sflags))
            me.flag = self.override_flags.get("flag", me.flag)
            me.penalties = self.override_flags.get("penalties", me.penalties)
        for k, v in self.override_me.items():
            setattr(me, k, v)
        for k, v in self.override_player.items():
            setattr(player, k, v)

        # meteorologia: chuva entre os 30 e os 45 min de corrida; a pista seca devagar depois
        rain = max(0.0, math.sin(math.pi * (t - 1800) / 900)) * 0.55 if 1800 <= t <= 2700 else 0.0
        wet = 0.0
        if t > 1800:
            wet = min(0.7, (min(t, 2700) - 1800) / 900 * 0.9) if t <= 2700 else max(0.0, 0.7 - (t - 2700) / 600 * 0.7)
        session = Session(
            track=TRACK, kind="race", raw=10, phase=phase, yellow_state=ystate, sector_flags=tuple(sflags),
            current_et=t, end_et=self.race_len, max_laps=0, track_length=L, in_realtime=True,
            air_temp=24.0, track_temp=33.5, rain=rain, wetness=wet, wind=(2.4, 0.0, -3.1),
            wetness_min=max(0.0, wet - 0.06), wetness_max=min(1.0, wet + 0.08),
            sky=(5 + min(5, int(rain * 8))) if rain > 0.02 else (3 if wet > 0 else 1),
            forecast=[(0.0, 0.1, 1), (900.0, 0.2, 2), (1800.0, 0.7, 7), (2700.0, 0.6, 6), (3600.0, 0.1, 2)],
        )
        return Snapshot(session=session, vehicles=vehicles, me=me, player=player, source="demo")
