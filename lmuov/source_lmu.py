"""Leitura da memória partilhada nativa do Le Mans Ultimate ("LMU_Data").

O jogo só publica estes dados com  Settings > Gameplay > Enable Plugins  ligado.
As estruturas vêm de pyLMUSharedMemory (MIT), que espelha o ficheiro
SharedMemoryInterface.hpp que a S397 inclui em  Le Mans Ultimate/Support/SharedMemoryInterface.

O scoring (posições, tempos) só muda ~5x por segundo, por isso só é convertido
quando muda; a telemetria (comandos, RPM, posições no mundo) é lida a cada leitura.
"""

from __future__ import annotations

import ctypes
import math
import mmap
import re
import sys

from pyLMUSharedMemory import lmu_data as L

from .model import Player, Session, Snapshot, Tyre, Vehicle, assign_class_places, session_kind

K = 273.15
MAXV = L.LMUConstants.MAX_MAPPED_VEHICLES
_NUM_RE = re.compile(r"#\s?(\d{1,3})")


class Skip(Exception):
    """Dados momentaneamente inconsistentes (o jogo está a meio de uma escrita)."""


def _s(raw: bytes) -> str:
    for enc in ("utf-8", "cp1252"):
        try:
            return raw.decode(enc).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace").strip()


def _signed_char(v) -> int:
    if isinstance(v, (bytes, bytearray)):
        v = v[0] if v else 0
    v = int(v)
    return v - 256 if v > 127 else v


def _fin(x: float, default: float = 0.0) -> float:
    return x if isinstance(x, (int, float)) and math.isfinite(x) else default


def _speed(vec) -> float:
    return math.sqrt(vec.x * vec.x + vec.y * vec.y + vec.z * vec.z)


def _sector(raw: int) -> int:
    """LMU: 0=S3, 1=S1, 2=S2  ->  0=S1, 1=S2, 2=S3"""
    return (int(raw) + 2) % 3


def _fwd(ori) -> tuple[float, float, float]:
    """Frente do carro (-z local) no mundo = -(3.ª coluna da matriz local->mundo)."""
    return (-ori[0].z, -ori[1].z, -ori[2].z)


# --------------------------------------------------------------------------- #
def parse_scoring(d: L.LMUObjectOut) -> tuple[Session, list[Vehicle], Vehicle] | None:
    si = d.scoring.scoringInfo
    nveh = min(int(si.mNumVehicles), MAXV)
    track_len = _fin(si.mLapDist)
    if nveh <= 0 or track_len <= 0:
        return None
    vehicles: list[Vehicle] = []
    me = None
    pname = _s(si.mPlayerName).strip().lower()
    by_name = by_ctrl = None
    for i in range(nveh):
        vs = d.scoring.vehScoringInfo[i]
        name = _s(vs.mVehicleName)
        m = _NUM_RE.search(name)
        v = Vehicle(
            id=int(vs.mID), driver=_s(vs.mDriverName), vehicle_name=name, number=m.group(1) if m else "",
            cls=_s(vs.mVehicleClass), place=int(vs.mPlace), total_laps=int(vs.mTotalLaps),
            lap_dist=_fin(vs.mLapDist), best=_fin(vs.mBestLapTime), last=_fin(vs.mLastLapTime),
            t_behind_leader=_fin(vs.mTimeBehindLeader), laps_behind_leader=int(vs.mLapsBehindLeader),
            in_pits=bool(vs.mInPits), in_garage=bool(vs.mInGarageStall), pit_state=int(vs.mPitState),
            pit_lap_dist=_fin(vs.mPitLapDist), pitstops=int(vs.mNumPitstops), penalties=int(vs.mNumPenalties),
            is_player=bool(vs.mIsPlayer), speed=_fin(_speed(vs.mLocalVel)), flag=int(vs.mFlag),
            finish_status=int(vs.mFinishStatus), time_into_lap=_fin(vs.mTimeIntoLap),
            est_lap=_fin(vs.mEstimatedLapTime), sector=_sector(vs.mSector), under_yellow=bool(vs.mUnderYellow),
            fuel_frac=int(vs.mFuelFraction) / 255.0,
            pos=(_fin(vs.mPos.x), _fin(vs.mPos.y), _fin(vs.mPos.z)), fwd=_fwd(vs.mOri),
        )
        v.ai = int(vs.mControl) == 1
        vehicles.append(v)
        if v.is_player:
            me = v
        elif by_name is None and pname and v.driver.strip().lower() == pname:
            by_name = v
        elif by_ctrl is None and int(vs.mControl) == 0:
            by_ctrl = v
    if me is None:                       # garagem / colega a conduzir: usa o carro da equipa
        me = by_name or by_ctrl
        if me is None:
            return None
        me.is_player = True
    assign_class_places(vehicles)
    session = Session(
        track=_s(si.mTrackName), kind=session_kind(int(si.mSession)), raw=int(si.mSession),
        phase=int(si.mGamePhase), yellow_state=_signed_char(si.mYellowFlagState),
        # mSectorFlag segue a mesma convenção de mSector (0=S3, 1=S1, 2=S2)
        sector_flags=(int(si.mSectorFlag[1]), int(si.mSectorFlag[2]), int(si.mSectorFlag[0])),
        current_et=_fin(si.mCurrentET), end_et=_fin(si.mEndET),
        max_laps=int(si.mMaxLaps) if 0 < si.mMaxLaps < 10000 else 0, track_length=track_len,
        in_realtime=bool(si.mInRealtime), air_temp=_fin(si.mAmbientTemp), track_temp=_fin(si.mTrackTemp),
        rain=_fin(si.mRaining), wetness=_fin(si.mAvgPathWetness),
        wetness_min=_fin(si.mMinPathWetness), wetness_max=_fin(si.mMaxPathWetness), sky=int(si.mCloudCoverage),
        wind=(_fin(si.mWind.x), _fin(si.mWind.y), _fin(si.mWind.z)),
    )
    return session, vehicles, me


def parse_player(tel) -> Player:
    tyres = []
    for w in tel.mWheels:
        tyres.append(Tyre(
            temp_lcr=tuple(_fin(t) - K for t in w.mTemperature),
            inner_lcr=tuple(_fin(t) - K for t in w.mTireInnerLayerTemperature),
            carcass=_fin(w.mTireCarcassTemperature) - K, pressure=_fin(w.mPressure),
            wear=_fin(w.mWear, 1.0), optimal=_fin(w.mOptimalTemp), brake_temp=_fin(w.mBrakeTemp),
            flat=bool(w.mFlat), detached=bool(w.mDetached),
        ))
    rear_bias = _fin(tel.mRearBrakeBias)
    return Player(
        id=int(tel.mID), vehicle_model=_s(tel.mVehicleModel),
        fuel=_fin(tel.mFuel), fuel_capacity=_fin(tel.mFuelCapacity), virtual_energy=_fin(tel.mVirtualEnergy),
        battery=_fin(tel.mBatteryChargeFraction) if tel.mElectricBoostMotorState else -1.0,
        lap_time_now=max(0.0, _fin(tel.mElapsedTime - tel.mLapStartET)), elapsed=_fin(tel.mElapsedTime),
        lap_invalid=bool(tel.mLapInvalidated),
        delta_game=_fin(tel.mDeltaBest),
        speed=_fin(_speed(tel.mLocalVel)), rpm=_fin(tel.mEngineRPM), max_rpm=_fin(tel.mEngineMaxRPM),
        gear=int(tel.mGear), max_gears=int(tel.mMaxGears),
        water_temp=_fin(tel.mEngineWaterTemp), oil_temp=_fin(tel.mEngineOilTemp),
        throttle=_fin(tel.mUnfilteredThrottle), brake=_fin(tel.mUnfilteredBrake),
        clutch=_fin(tel.mUnfilteredClutch), steering=_fin(tel.mUnfilteredSteering),
        throttle_f=_fin(tel.mFilteredThrottle), brake_f=_fin(tel.mFilteredBrake),
        steering_range=_fin(tel.mPhysicalSteeringWheelRange),
        tc=int(tel.mTC), tc_max=int(tel.mTCMax), tc_cut=int(tel.mTCCut), tc_slip=int(tel.mTCSlip),
        abs=int(tel.mABS), abs_max=int(tel.mABSMax), tc_active=bool(tel.mTCActive),
        abs_active=bool(tel.mABSActive),
        brake_bias=(1.0 - rear_bias) * 100 if 0 < rear_bias < 1 else 0.0,
        motor_map=int(tel.mMotorMap), limiter_on=bool(tel.mSpeedLimiterActive or tel.mSpeedLimiter),
        headlights=bool(tel.mHeadlights),
        dents=tuple(int(x) for x in tel.mDentSeverity), aero_detached=bool(tel.mDetached),
        overheating=bool(tel.mOverheating), impact_et=_fin(tel.mLastImpactET), impact_mag=_fin(tel.mLastImpactMagnitude),
        warnings=1 if tel.mOverheating else 0,
        boost_temp=_fin(tel.mElectricBoostMotorTemperature) if tel.mElectricBoostMotorState else -1.0,
        compound_front=_s(tel.mFrontTireCompoundName), compound_rear=_s(tel.mRearTireCompoundName),
        tyres=tyres, pos=(_fin(tel.mPos.x), _fin(tel.mPos.y), _fin(tel.mPos.z)),
        ori=tuple((r.x, r.y, r.z) for r in tel.mOri),
    )


COMPOUND = {0: "S", 1: "M", 2: "H", 3: "W"}


def parse(d: L.LMUObjectOut, cached=None, need_positions: bool = True, need_tyres: bool = False) -> Snapshot | None:
    """Converte a estrutura crua num Snapshot. None = sem sessão ativa.

    `cached` = resultado anterior de parse_scoring (reutilizado se o scoring não mudou).
    """
    tb = d.telemetry
    sc = cached if cached is not None else parse_scoring(d)
    if sc is None:
        return None
    session, vehicles, me = sc

    by_id = {v.id: v for v in vehicles}
    player_tel = None
    idx = int(tb.playerVehicleIdx)
    if 0 <= idx < MAXV and tb.telemInfo[idx].mID == me.id:
        player_tel = tb.telemInfo[idx]
    for j in range(min(int(tb.activeVehicles), MAXV)):
        if not need_positions and not need_tyres and player_tel is not None:
            break                      # radar e mapa escondidos: não é preciso ler os outros carros
        t = tb.telemInfo[j]
        v = by_id.get(int(t.mID))
        if v is None:
            continue
        if v is me and player_tel is None:
            player_tel = t
        if need_tyres:
            v.tyre = COMPOUND.get(int(t.mWheels[0].mCompoundType), "")
        # posições/velocidade a 100 Hz (o scoring só tem 5 Hz) para o radar e o mapa
        v.pos = (_fin(t.mPos.x), _fin(t.mPos.y), _fin(t.mPos.z))
        v.fwd = _fwd(t.mOri)
        v.speed = _fin(_speed(t.mLocalVel))
    if player_tel is None:
        # sem telemetria do teu carro (estás na garagem e outro piloto conduz): o resto continua a funcionar
        from .model import Player
        player = Player(id=me.id, vehicle_model=me.vehicle_name, speed=me.speed)
        return Snapshot(session=session, vehicles=vehicles, me=me, player=player, source="lmu")
    player = parse_player(player_tel)
    if not player.vehicle_model:
        player.vehicle_model = me.vehicle_name
    si = d.scoring.scoringInfo
    spp = int(si.mTrackLimitsStepsPerPoint)
    if spp > 0:                                    # pontos de track limits (o jogo conta em "passos")
        player.tl_points = int(player_tel.mTrackLimitsSteps) / spp
        player.tl_limit = int(si.mTrackLimitsStepsPerPenalty) / spp
    return Snapshot(session=session, vehicles=vehicles, me=me, player=player, source="lmu")


class LMUSource:
    """Lê LMU_Data por cópia (evita ler a meio de uma escrita do jogo)."""

    label = "LMU"

    def __init__(self) -> None:
        self._size = ctypes.sizeof(L.LMUObjectOut)
        self._mm: mmap.mmap | None = None
        self._live: L.LMUObjectOut | None = None
        self._copy = L.LMUObjectOut()
        self._last: Snapshot | None = None
        self._sc_key = None
        self._sc = None
        self.need_positions = True
        self.need_tyres = False         # composto de todos os carros (colunas dos pneus no relativo/classificação)
        self.status = ("waiting", "")
        self.weather = None             # previsão pela API local do jogo (arranca quando há sessão)
        self.repair = None              # danos da API local (suspensão, aero, travões)
        self.standings = None           # (já não é usado: a API local não tem ratings)
        self.ratings = None             # SR/DR pelo serviço de ratings do LMU (ver ratings_service.py)
        self.use_ratings = True
        self._dr_start: dict = {}       # rating de cada piloto no início da corrida (para o +/-)
        self._dr_key = None
        self.pitest = None              # tempo de reparação estimado pelo jogo

    def _open(self) -> bool:
        if sys.platform != "win32":
            self.status = ("windows_only", "")
            return False
        try:
            # Igual ao que o TinyPedal faz: abre (ou cria vazio) o mapeamento com este nome.
            self._mm = mmap.mmap(-1, self._size, L.LMUConstants.LMU_SHARED_MEMORY_FILE)
            self._live = L.LMUObjectOut.from_buffer(self._mm)
            return True
        except Exception as exc:  # pragma: no cover - só em Windows
            self.status = ("open_error", str(exc))
            return False

    def read(self) -> Snapshot | None:
        if self._live is None and not self._open():
            return None
        ctypes.memmove(ctypes.addressof(self._copy), ctypes.addressof(self._live), self._size)
        return self.read_from(self._copy)

    def _apply_ratings(self, snap) -> None:
        """SR/DR de cada piloto (treino, qualificação e corrida). Na corrida, também quanto o DR
        mudou desde o início dela."""
        from .ratings_service import rating_value
        rs = self.ratings
        rs.request(v.driver for v in snap.vehicles if not v.ai)
        s = snap.session
        key = (s.track, s.raw)
        if key != self._dr_key:
            self._dr_key, self._dr_start = key, {}
        race = s.kind == "race"
        for v in snap.vehicles:
            r = rs.get(v.driver) if not v.ai else None
            if not r:
                continue
            v.dr, v.dr_pct, v.sr, v.sr_pct = r["dr"], r["dr_pct"], r["sr"], r["sr_pct"]
            v.country = v.country or r["country"]
            val = rating_value(v.dr, v.dr_pct)
            if race and val is not None:
                start = self._dr_start.setdefault(v.driver, val)
                v.dr_delta = val - start                 # em "níveis": 0.18 = +18% de um nível
            else:
                v.dr_delta = 0.0

    @property
    def diag(self) -> dict:
        out = {"estado": list(self.status)}
        if self._last is not None:
            out["carros"] = len(self._last.vehicles)
            out["sessao"] = self._last.session.kind
        out["vento"] = list(getattr(self, "wind_src", ("memória partilhada", 0, 0)))
        if self.ratings is not None:
            out["ratings"] = {"estado": self.ratings.status, "pilotos_com_rating": self.ratings.found,
                              "pedidos": len(self.ratings.wanted)}
        for name, f in (("api_meteorologia", self.weather), ("api_danos", self.repair),
                        ("api_reparacao", self.pitest)):
            out[name] = f.status() if f is not None else "não iniciada"
        return out

    def read_from(self, d: L.LMUObjectOut) -> Snapshot | None:
        tb = d.telemetry
        si = d.scoring.scoringInfo
        if si.mNumVehicles > 0 and tb.activeVehicles and tb.activeVehicles != si.mNumVehicles:
            return self._last  # scoring e telemetria fora de sincronia, usa o anterior
        key = (si.mCurrentET, si.mNumVehicles, si.mSession, si.mGamePhase)
        if key != self._sc_key:
            self._sc_key = key
            self._sc = parse_scoring(d)
        try:
            snap = parse(d, self._sc, self.need_positions, self.need_tyres) if self._sc is not None else None
        except Skip:
            return self._last
        if snap is None:
            self.status = ("connected_waiting", "") if d.generic.gameVersion else ("waiting", "")
        else:
            self.status = ("connected", snap.session.track)
            if self.weather is None and sys.platform == "win32":
                from .lmu_rest import WeatherFetcher
                self.weather = WeatherFetcher()
                self.weather.start()
            if self.repair is None and sys.platform == "win32":
                from .lmu_rest import RepairFetcher
                self.repair = RepairFetcher()
                self.repair.start()
            if self.use_ratings and self.ratings is None and sys.platform == "win32":
                from .paths import app_dir
                from .ratings_service import RatingsService
                self.ratings = RatingsService(app_dir() / "data" / "ratings.json")
                self.ratings.start()
            if self.ratings is not None and self.use_ratings:
                self._apply_ratings(snap)
            if self.pitest is None and sys.platform == "win32":
                from .lmu_rest import PitEstimateFetcher
                self.pitest = PitEstimateFetcher()
                self.pitest.start()
            if self.pitest is not None:
                est = self.pitest.estimate()
                snap.player.repair_est, snap.player.pit_est = est["repair"], est["total"]
            wr = self.repair.wearables() if self.repair is not None else None
            if wr:
                p = snap.player
                p.aero_damage, p.susp_damage, p.brake_wear = wr["aero"], wr["suspension"], wr["brakes"]
                p.extra_damage = wr["extra"]
            if self.weather is not None and snap.session.end_et > 0:
                snap.session.forecast = self.weather.forecast(snap.session.kind, snap.session.end_et)
            if self.weather is not None and not snap.session.wind_valid:     # mWind vem sempre a 0 no LMU
                s = snap.session
                prog = s.current_et / s.end_et if s.end_et > 0 else 0.0
                wd = self.weather.wind(s.kind, prog)
                if wd and wd[0] > 0.05:
                    from .lmu_rest import wind_vector
                    s.wind = wind_vector(*wd)
                    self.wind_src = ("api", round(wd[0], 1), int(wd[1]))
                else:
                    self.wind_src = ("sem vento na API" if wd else "sem dados", 0, 0)
        self._last = snap
        return snap
