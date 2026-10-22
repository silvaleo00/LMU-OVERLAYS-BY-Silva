"""Memória do iRacing SDK de mentira, construída a partir da corrida simulada (DemoSource).

Serve para testar o leitor do iRacing sem o jogo: escreve o cabeçalho, as variáveis, os buffers
rotativos e o YAML da sessão exatamente no formato do SDK (irsdk_defines.h).
"""

from __future__ import annotations

import math
import struct

from lmuov.model import to_local
from lmuov.source_iracing import _HEADER, _VARBUF, _VARHDR, VARHDR_SIZE

TYPES = {"c": 0, "?": 1, "i": 2, "I": 3, "f": 4, "d": 5}
SIZES = {"c": 1, "?": 1, "i": 4, "I": 4, "f": 4, "d": 8}

SCALARS = [
    ("SessionTime", "d"), ("SessionTimeRemain", "d"), ("SessionNum", "i"), ("SessionState", "i"),
    ("SessionFlags", "I"), ("SessionLapsTotal", "i"), ("PlayerCarIdx", "i"), ("IsOnTrack", "?"),
    ("IsReplayPlaying", "?"), ("PitsOpen", "?"), ("AirTemp", "f"), ("TrackTempCrew", "f"), ("Precipitation", "f"),
    ("TrackWetness", "i"), ("WindVel", "f"), ("WindDir", "f"), ("Speed", "f"), ("RPM", "f"), ("Gear", "i"),
    ("Throttle", "f"), ("Brake", "f"), ("Clutch", "f"), ("ThrottleRaw", "f"), ("BrakeRaw", "f"), ("ClutchRaw", "f"),
    ("SteeringWheelAngle", "f"), ("SteeringWheelAngleMax", "f"), ("FuelLevel", "f"), ("LapCurrentLapTime", "f"),
    ("LapDeltaToBestLap", "f"), ("LapDeltaToBestLap_OK", "?"), ("WaterTemp", "f"), ("OilTemp", "f"),
    ("dcTractionControl", "f"), ("dcABS", "f"), ("dcBrakeBias", "f"), ("BrakeABSactive", "?"),
    ("EngineWarnings", "I"), ("PlayerCarInPitStall", "?"), ("OnPitRoad", "?"), ("PlayerTireCompound", "i"),
    ("EnergyERSBatteryPct", "f"), ("Yaw", "f"), ("YawNorth", "f"), ("VelocityX", "f"), ("VelocityY", "f"),
    ("PlayerTrackSurface", "i"), ("CarLeftRight", "i"), ("PlayerCarMyIncidentCount", "i"), ("PitRepairLeft", "f"),
    ("PitOptRepairLeft", "f"), ("Skies", "i"),
] + [(f"{c}{k}", "f") for c in ("LF", "RF", "LR", "RR")
     for k in ("tempCL", "tempCM", "tempCR", "press", "wearL", "wearM", "wearR")]
ARRAYS = [
    ("CarIdxLapDistPct", "f"), ("CarIdxLapCompleted", "i"), ("CarIdxPosition", "i"), ("CarIdxClassPosition", "i"),
    ("CarIdxOnPitRoad", "?"), ("CarIdxTrackSurface", "i"), ("CarIdxBestLapTime", "f"), ("CarIdxLastLapTime", "f"),
    ("CarIdxF2Time", "f"), ("CarIdxSessionFlags", "I"), ("CarIdxEstTime", "f"),
]
N = 64
CLASS = {"Hyper": ("GTP", "0xff3040"), "LMP2": ("LMP2", "0x2f86ff"), "LMP3": ("LMP3", "0xa86bff"),
         "GT3": ("GT3", "0x1fbf62")}


class FakeIRacing:
    def __init__(self, session_type: str = "Race") -> None:
        self.session_type = session_type
        self.vars: dict[str, tuple[str, int, int]] = {}
        off = 0
        for name, code in SCALARS:
            self.vars[name] = (code, off, 1)
            off += SIZES[code]
        for name, code in ARRAYS:
            self.vars[name] = (code, off, N)
            off += SIZES[code] * N
        self.buf_len = off
        self.tick = 0
        self.yaml_ver = 0
        self.yaml = ""
        self.mem = bytearray()
        self.connected = True

    # ------------------------------------------------------------------ #
    def _yaml(self, snap) -> str:
        L = snap.session.track_length
        lines = ["---", "WeekendInfo:", f" TrackName: demo circuit", f" TrackDisplayName: {snap.session.track}",
                 f" TrackLength: {L / 1000:.2f} km", " WeekendOptions:", "  NumStarters: 30", "  IncidentLimit: 17",
                 "SessionInfo:", " Sessions:",
                 " - SessionNum: 0", "   SessionLaps: unlimited", "   SessionTime: 3600.0000 sec",
                 f"   SessionType: {self.session_type}", "   ResultsPositions:",
                 "   - Position: 1", "     CarIdx: 1", "   - Position: 2", "     CarIdx: 2",
                 "SplitTimeInfo:", " Sectors:", " - SectorNum: 0", "   SectorStartPct: 0.000000",
                 " - SectorNum: 1", "   SectorStartPct: 0.333000",
                 "DriverInfo:", f" DriverCarIdx: {snap.me.id + 1}", " DriverCarFuelMaxLtr: 110.000",
                 " DriverCarMaxFuelPct: 1.000", " DriverCarRedLine: 9000.000",
                 f" DriverPitTrkPct: {snap.me.pit_lap_dist / L:.6f}", " Drivers:",
                 " - CarIdx: 0", "   UserName: Pace Car", "   TeamName: Pace Car", '   CarNumber: "0"',
                 "   CarScreenName: safety pcporsche911cup", "   CarClassShortName: ", "   CarIsPaceCar: 1",
                 "   IsSpectator: 0"]
        for v in snap.vehicles:
            short, col = CLASS.get(v.cls, (v.cls, "0x888888"))
            model = v.vehicle_name.split(" #")[0]
            team = f"{model} Racing: Équipe {v.number}" if v.id % 3 == 0 else v.driver   # ':' e acentos de propósito
            lines += [f" - CarIdx: {v.id + 1}", f"   UserName: {v.driver}", f"   TeamName: {team}",
                      f'   CarNumber: "{v.number}"', f"   CarScreenName: {model}", f"   CarClassShortName: {short}",
                      f"   CarClassColor: {col}", f"   CarClassEstLapTime: {v.est_lap:.4f}", "   CarIsPaceCar: 0",
                      "   IsSpectator: 0"]
        return "\n".join(lines) + "\n...\n"

    def _values(self, snap) -> dict:
        s, me, p = snap.session, snap.me, snap.player
        L = s.track_length
        fx, fz = -p.ori[0][2], -p.ori[2][2]
        yaw = math.atan2(fz, fx)
        flags = 0
        if s.phase == 6:
            flags |= 0x4000
        if s.phase == 7:
            flags |= 0x10
        if me.flag == 6:
            flags |= 0x20
        if any(s.sector_flags) and s.phase != 6:
            flags |= 0x8
        left = right = 0
        for v in snap.vehicles:
            if v is me:
                continue
            d = (v.pos[0] - p.pos[0], v.pos[1] - p.pos[1], v.pos[2] - p.pos[2])
            lx, _, lz = to_local(p.ori, d)
            if abs(lz) < 5.5 and 1.5 < abs(lx) < 8:
                if lx > 0:
                    left += 1
                else:
                    right += 1
        clr = {(0, 0): 1, (1, 0): 2, (0, 1): 3, (2, 0): 5, (0, 2): 6}.get((min(left, 2), min(right, 2)), 4)
        vals = {
            "SessionTime": s.current_et, "SessionTimeRemain": s.time_left if s.time_left is not None else 604800.0,
            "SessionNum": 0, "SessionState": {8: 5, 3: 3}.get(s.phase, 4), "SessionFlags": flags,
            "SessionLapsTotal": 32767, "PlayerCarIdx": me.id + 1, "IsOnTrack": s.in_realtime,
            "IsReplayPlaying": False, "PitsOpen": s.yellow_state != 2, "AirTemp": s.air_temp,
            "TrackTempCrew": s.track_temp, "Precipitation": s.rain, "TrackWetness": 1, "WindVel": 3.9,
            "WindDir": 1.0, "Speed": p.speed, "RPM": p.rpm, "Gear": p.gear, "Throttle": p.throttle_f,
            "Brake": p.brake_f, "Clutch": 1.0 - p.clutch, "ThrottleRaw": p.throttle, "BrakeRaw": p.brake,
            "ClutchRaw": 1.0 - p.clutch, "SteeringWheelAngle": -p.steering * math.radians(225),
            "SteeringWheelAngleMax": math.radians(225), "FuelLevel": p.fuel, "LapCurrentLapTime": p.lap_time_now,
            "LapDeltaToBestLap": 0.12, "LapDeltaToBestLap_OK": True, "WaterTemp": p.water_temp,
            "OilTemp": p.oil_temp, "dcTractionControl": p.tc, "dcABS": p.abs, "dcBrakeBias": p.brake_bias,
            "BrakeABSactive": p.abs_active, "EngineWarnings": 0x10 if p.limiter_on else 0,
            "PlayerCarInPitStall": me.pit_state == 3, "OnPitRoad": me.in_pits, "PlayerTireCompound": 0,
            "EnergyERSBatteryPct": max(0.0, p.battery), "Yaw": yaw, "YawNorth": yaw, "VelocityX": p.speed,
            "VelocityY": 0.0, "PlayerTrackSurface": 3, "CarLeftRight": clr,
            "PlayerCarMyIncidentCount": int(max(0, p.tl_points)), "PitRepairLeft": p.repair_req,
            "PitOptRepairLeft": p.repair_opt, "Skies": 1,
        }
        for i, c in enumerate(("LF", "RF", "LR", "RR")):
            t = p.tyres[i]
            vals.update({f"{c}tempCL": t.temp_lcr[0], f"{c}tempCM": t.temp_lcr[1], f"{c}tempCR": t.temp_lcr[2],
                         f"{c}press": t.pressure, f"{c}wearL": t.wear, f"{c}wearM": t.wear, f"{c}wearR": t.wear})
        arrs = {name: [0] * N for name, _ in ARRAYS}
        arrs["CarIdxLapDistPct"] = [-1.0] * N
        arrs["CarIdxTrackSurface"] = [-1] * N
        for v in snap.vehicles:
            i = v.id + 1
            arrs["CarIdxLapDistPct"][i] = (v.lap_dist / L) % 1.0
            arrs["CarIdxLapCompleted"][i] = v.total_laps
            arrs["CarIdxPosition"][i] = v.place
            arrs["CarIdxClassPosition"][i] = v.class_place
            arrs["CarIdxOnPitRoad"][i] = v.in_pits
            arrs["CarIdxTrackSurface"][i] = 1 if v.pit_state == 3 else (2 if v.pit_state == 1 else 3)
            arrs["CarIdxBestLapTime"][i] = v.best if v.best > 0 else -1.0
            arrs["CarIdxLastLapTime"][i] = v.last if v.last > 0 else -1.0
            arrs["CarIdxF2Time"][i] = v.t_behind_leader
            arrs["CarIdxSessionFlags"][i] = 0x20 if v.flag == 6 else 0
            arrs["CarIdxEstTime"][i] = v.time_into_lap
        arrs["CarIdxLapDistPct"][0] = 0.5     # carro de segurança (não deve aparecer)
        arrs["CarIdxTrackSurface"][0] = 3
        return {**vals, **arrs}

    # ------------------------------------------------------------------ #
    def write(self, snap) -> bytearray:
        """Escreve um novo frame (tick) a partir de um Snapshot do demo e devolve a memória."""
        y = self._yaml(snap)
        if y != self.yaml:
            self.yaml = y
            self.yaml_ver += 1
        yb = self.yaml.encode("cp1252", errors="replace") + b"\0"
        nvars = len(self.vars)
        var_off = 112
        yaml_off = var_off + nvars * VARHDR_SIZE
        buf0 = (yaml_off + len(yb) + 4096 + 15) // 16 * 16       # folga para o YAML crescer
        size = buf0 + 3 * self.buf_len
        if len(self.mem) < size:
            self.mem = bytearray(size)
        mem = self.mem
        status = 1 if self.connected else 0
        _HEADER.pack_into(mem, 0, 2, status, 60, self.yaml_ver, len(yb), yaml_off, nvars, var_off, 3,
                          self.buf_len, 0, 0)
        for k, (name, (code, off, count)) in enumerate(self.vars.items()):
            _VARHDR.pack_into(mem, var_off + k * VARHDR_SIZE, TYPES[code], off, count, False,
                              name.encode(), b"", b"")
        mem[yaml_off:yaml_off + len(yb)] = yb
        self.tick += 1
        slot = self.tick % 3
        boff = buf0 + slot * self.buf_len
        vals = self._values(snap)
        for name, (code, off, count) in self.vars.items():
            v = vals.get(name, 0)
            if count == 1:
                struct.pack_into(f"<{code}", mem, boff + off, v if code != "c" else b"\0")
            else:
                struct.pack_into(f"<{count}{code}", mem, boff + off, *v)
        for s in range(3):
            tick = self.tick - ((slot - s) % 3)
            _VARBUF.pack_into(mem, 48 + 16 * s, max(0, tick), buf0 + s * self.buf_len, 0, 0)
        return mem
