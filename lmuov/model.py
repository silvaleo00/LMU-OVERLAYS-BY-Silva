"""Modelo de dados normalizado.

Todas as fontes (LMU, iRacing, demo) produzem um `Snapshot` com esta forma. Os overlays só
conhecem este modelo, nunca as estruturas cruas de cada jogo.

Unidades: temperaturas em °C, pressões em kPa, distâncias em metros,
tempos em segundos, velocidades em m/s. Coordenadas do mundo: y para cima.
Eixos locais do carro (rF2/LMU): +x esquerda, +y cima, +z trás.
"""

from __future__ import annotations

from dataclasses import dataclass, field

Vec3 = tuple[float, float, float]
IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def session_kind(raw: int) -> str:
    """mSession: 0=testday 1-4=practice 5-8=qual 9=warmup 10-13=race"""
    if raw <= 0:
        return "test"
    if raw <= 4:
        return "practice"
    if raw <= 8:
        return "qualy"
    if raw == 9:
        return "warmup"
    return "race"


def session_kind_from_name(name: str) -> str:
    """Tipo de sessão a partir do nome (iRacing: "Practice", "Open Qualify", "Lone Qualify", "Race"…)."""
    low = (name or "").lower()
    if "race" in low:
        return "race"
    if "qual" in low or "time trial" in low:
        return "qualy"
    if "warm" in low:
        return "warmup"
    if "test" in low:
        return "test"
    return "practice"


def session_group(kind: str) -> str:
    """Agrupa para os filtros do painel: practice / qualy / race."""
    return {"test": "practice", "warmup": "practice"}.get(kind, kind)


@dataclass
class Tyre:
    temp_lcr: tuple[float, float, float] = (0.0, 0.0, 0.0)   # superfície esq/centro/dir (°C)
    inner_lcr: tuple[float, float, float] = (0.0, 0.0, 0.0)  # camada interior (°C)
    carcass: float = 0.0          # °C
    pressure: float = 0.0         # kPa
    wear: float = 1.0             # piso restante 0..1 (1 = novo)
    optimal: float = 0.0          # temperatura ótima (°C), 0 = desconhecida
    brake_temp: float = 0.0       # °C
    flat: bool = False
    detached: bool = False


@dataclass
class Player:
    id: int = -1
    vehicle_model: str = ""
    # combustível / energia
    fuel: float = 0.0             # litros
    fuel_capacity: float = 0.0    # litros
    virtual_energy: float = 0.0   # fração 0..1 (0 se o carro não usa VE)
    battery: float = -1.0         # carga da bateria híbrida 0..1, -1 = sem híbrido
    # volta
    lap_time_now: float = 0.0
    elapsed: float = 0.0          # tempo de jogo da telemetria (mesma base do mCurrentET do scoring)
    lap_invalid: bool = False
    delta_game: float = 0.0
    # motor e caixa
    speed: float = 0.0            # m/s
    rpm: float = 0.0
    max_rpm: float = 0.0
    gear: int = 0                 # -1 R, 0 N, 1+
    max_gears: int = 0
    water_temp: float = 0.0
    oil_temp: float = 0.0
    # comandos (0..1, direção -1..1)
    throttle: float = 0.0
    brake: float = 0.0
    clutch: float = 0.0
    steering: float = 0.0
    throttle_f: float = 0.0       # depois do TC
    brake_f: float = 0.0          # depois do ABS
    steering_range: float = 0.0   # graus de volante (físico)
    # ajudas e afinações em pista
    tc: int = 0
    tc_max: int = 0
    tc_cut: int = 0
    tc_slip: int = 0
    abs: int = 0
    abs_max: int = 0
    tc_active: bool = False
    abs_active: bool = False
    brake_bias: float = 0.0       # % à frente (0 = desconhecido)
    motor_map: int = 0
    limiter_on: bool = False
    headlights: bool = False
    # pneus
    compound_front: str = ""
    compound_rear: str = ""
    tyres: list[Tyre] = field(default_factory=lambda: [Tyre() for _ in range(4)])  # FL FR RL RR
    # posição
    pos: Vec3 = (0.0, 0.0, 0.0)
    ori: tuple = IDENTITY         # linhas da matriz local->mundo
    # limites de pista: LMU = pontos de track limits; iRacing = pontos de incidente
    tl_points: float = -1.0       # -1 = o jogo não dá
    tl_limit: float = 0.0         # pontos até à penalização (0 = sem limite / desconhecido)
    tl_kind: str = "tl"           # "tl" (track limits) ou "inc" (incidentes do iRacing)
    # danos
    dents: tuple = ()             # 8 zonas à volta do carro (0 nada, 1 algum, 2 muito); vazio = o jogo não dá
    aero_detached: bool = False   # peças soltas (asa, carroçaria)
    overheating: bool = False
    impact_et: float = 0.0        # tempo de jogo do último toque
    impact_mag: float = 0.0
    repair_req: float = -1.0      # segundos de reparação obrigatória (iRacing), -1 = não se sabe
    repair_opt: float = -1.0
    warnings: int = 0             # 1 água quente, 2 óleo quente, 4 pressão do óleo, 8 pressão gasolina, 16 motor parado
    boost_temp: float = -1.0      # motor elétrico do híbrido (°C), -1 = não tem
    # danos pela API local do LMU (0 = intacto … 1 = destruído; -1 = sem dados)
    aero_damage: float = -1.0
    susp_damage: tuple = (-1.0, -1.0, -1.0, -1.0)     # FL FR RL RR
    brake_wear: tuple = (-1.0, -1.0, -1.0, -1.0)      # FL FR RL RR
    extra_damage: dict = field(default_factory=dict)  # outras peças que a API devolva (nome -> 0..1)


@dataclass
class Vehicle:
    id: int = -1
    driver: str = ""
    vehicle_name: str = ""
    team: str = ""                # nome da equipa quando o jogo o dá à parte (iRacing); vazio = tirado do nome do carro
    number: str = ""
    cls: str = ""                 # nome cru da classe
    place: int = 0                # posição geral (1 = primeiro)
    class_place: int = 0          # posição na classe (calculada)
    total_laps: int = 0           # voltas completas
    lap_dist: float = 0.0         # distância na volta atual (m)
    best: float = 0.0             # melhor volta (s), <=0 = sem tempo
    last: float = 0.0             # última volta (s), <=0 = inválida/sem tempo
    t_behind_leader: float = 0.0
    laps_behind_leader: int = 0
    in_pits: bool = False
    in_garage: bool = False
    pit_state: int = 0            # 0 nada, 1 pedido, 2 a entrar, 3 parado, 4 a sair
    pit_lap_dist: float = 0.0     # posição da box (distância na volta)
    pitstops: int = 0
    penalties: int = 0
    is_player: bool = False
    speed: float = 0.0
    flag: int = 0                 # 6 = azul
    finish_status: int = 0        # 0 none, 1 finished, 2 dnf, 3 dq
    time_into_lap: float = 0.0
    est_lap: float = 0.0
    sector: int = 0               # 0=S1 1=S2 2=S3 (já normalizado)
    under_yellow: bool = False
    fuel_frac: float = -1.0       # combustível/bateria restante 0..1 (-1 = desconhecido)
    pos: Vec3 = (0.0, 0.0, 0.0)   # posição no mundo
    fwd: Vec3 = (0.0, 0.0, -1.0)  # vetor "para a frente" do carro, no mundo
    sr: str = ""                  # safety rating já formatado (iRacing "A4.32"; LMU nível) — vazio = o jogo não dá
    dr: str = ""                  # driver rating (iRacing: iRating "2.4k"; LMU nível)
    irating: int = 0              # iRating em número (iRacing), para o SOF
    country: str = ""             # código do país (quando o jogo dá)
    tyre: str = ""                # composto dos pneus: "S" macio, "M" médio, "H" duro, "W" chuva, "D" seco


@dataclass
class Session:
    track: str = ""
    kind: str = "practice"
    raw: int = 0
    phase: int = 0                # mGamePhase
    yellow_state: int = 0         # mYellowFlagState (FCY)
    sector_flags: tuple[int, int, int] = (0, 0, 0)  # S1, S2, S3 (1 = amarela)
    current_et: float = 0.0
    end_et: float = 0.0
    sector_bounds: tuple = ()     # início do S2 e S3 (fração da volta) quando o jogo diz (iRacing)
    max_laps: int = 0             # 0 = sessão por tempo
    track_length: float = 0.0
    in_realtime: bool = False
    air_temp: float = 0.0
    track_temp: float = 0.0
    rain: float = 0.0             # 0..1
    wetness: float = 0.0          # 0..1 (média do traçado)
    wind: Vec3 = (0.0, 0.0, 0.0)  # m/s, coordenadas do mundo
    wetness_min: float = 0.0
    wetness_max: float = 0.0
    sky: int = -1                 # 0 limpo … 4 encoberto, 5+ com chuva (escala do LMU); -1 = desconhecido
    # previsão do jogo: [(segundos desde o início da sessão, probabilidade de chuva 0..1, céu)]
    forecast: list = field(default_factory=list)

    @property
    def time_left(self) -> float | None:
        if self.end_et > 0:
            return max(0.0, self.end_et - self.current_et)
        return None

    @property
    def wind_valid(self) -> bool:
        return any(abs(c) > 1e-6 for c in self.wind)


@dataclass
class Snapshot:
    session: Session
    vehicles: list[Vehicle]
    me: Vehicle                   # o carro do jogador (scoring)
    player: Player                # telemetria do jogador
    source: str = "lmu"
    world_pos: bool = True        # False = o jogo não dá posições no mundo dos outros carros (iRacing):
                                  # no mapa vão pela distância na volta; no radar pelo "spotter" do jogo

    def my_lap_dist(self) -> float:
        """Distância na volta do teu carro agora. O scoring só a atualiza ~5x/s; entre atualizações
        avança-se com a velocidade e o tempo de jogo da telemetria (a 60 fps não anda aos saltos)."""
        me, p, s = self.me, self.player, self.session
        d = me.lap_dist
        if p.elapsed > 0 and s.current_et > 0:
            d += max(0.0, min(0.5, p.elapsed - s.current_et)) * p.speed
        L = s.track_length
        return d - L if L > 0 and d >= L else d

    def total_dist(self, v: Vehicle) -> float:
        return v.total_laps * self.session.track_length + max(0.0, v.lap_dist)


def assign_class_places(vehicles: list[Vehicle]) -> None:
    """Calcula a posição dentro da classe a partir da posição geral."""
    by_class: dict[str, list[Vehicle]] = {}
    for v in vehicles:
        by_class.setdefault(v.cls, []).append(v)
    for group in by_class.values():
        group.sort(key=lambda v: v.place if v.place > 0 else 999)
        for i, v in enumerate(group, 1):
            v.class_place = i


def to_local(ori, d: Vec3) -> tuple[float, float, float]:
    """Vetor do mundo -> referencial do carro (ori = linhas da matriz local->mundo)."""
    return (ori[0][0] * d[0] + ori[1][0] * d[1] + ori[2][0] * d[2],
            ori[0][1] * d[0] + ori[1][1] * d[1] + ori[2][1] * d[2],
            ori[0][2] * d[0] + ori[1][2] * d[1] + ori[2][2] * d[2])
