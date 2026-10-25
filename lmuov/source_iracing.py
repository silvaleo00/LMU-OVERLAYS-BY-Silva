"""Leitura da memória partilhada do iRacing (iRacing SDK, "Local\\IRSDKMemMapFileName").

Formato (irsdk_defines.h, público):
  - cabeçalho com 4 buffers de dados rotativos (o jogo escreve a 60 Hz);
  - lista de variáveis (nome, tipo, posição no buffer, nº de elementos);
  - texto YAML com a informação da sessão (pilotos, pista, sessões), que só muda às vezes.

Não precisa de bibliotecas extra: o cabeçalho lê-se com struct e o YAML com um leitor simples.

O iRacing não dá as posições no mundo dos outros carros, por isso:
  - radar (Blind Spot): carros à frente/atrás pela distância na volta e de lado pelo "spotter"
    do jogo (CarLeftRight);
  - mapa: o traçado desenha-se integrando a velocidade e a direção do teu carro na primeira volta, e
    os carros são postos pela distância na volta.
"""

from __future__ import annotations

import math
import mmap
import struct
import sys

from . import theme
from .model import (Player, Session, Snapshot, Tyre, Vehicle, assign_class_places,
                    session_kind_from_name)

MAP_NAME = "Local\\IRSDKMemMapFileName"
MAP_SIZE = 1164 * 1024
STATUS_CONNECTED = 1

_HEADER = struct.Struct("<12i")          # ver, status, tickRate, sessionInfoUpdate, sessionInfoLen,
#                                          sessionInfoOffset, numVars, varHeaderOffset, numBuf, bufLen, pad[2]
_VARBUF = struct.Struct("<4i")           # tickCount, bufOffset, pad[2]
_VARHDR = struct.Struct("<3i?3x32s64s32s")
VARBUF_OFFSET = _HEADER.size              # 48
VARHDR_SIZE = _VARHDR.size                # 144
# tipo -> (código struct, bytes)
_TYPES = {0: ("c", 1), 1: ("?", 1), 2: ("i", 4), 3: ("I", 4), 4: ("f", 4), 5: ("d", 8)}

# irsdk_Flags
F_CHECKERED, F_RED, F_BLUE, F_YELLOW, F_YELLOW_WAVING = 0x1, 0x10, 0x20, 0x8, 0x100
F_CAUTION, F_CAUTION_WAVING, F_BLACK, F_DQ = 0x4000, 0x8000, 0x10000, 0x20000
F_START_READY, F_START_SET = 0x20000000, 0x40000000
# irsdk_TrkLoc
TRK_NOT_IN_WORLD, TRK_OFF, TRK_PIT_STALL, TRK_APPROACH_PITS, TRK_ON_TRACK = -1, 0, 1, 2, 3
ENGINE_PIT_LIMITER = 0x10
# CarLeftRight -> (carros à esquerda, carros à direita)
SPOTTER = {2: (1, 0), 3: (0, 1), 4: (1, 1), 5: (2, 0), 6: (0, 2)}


# --------------------------------------------------------------------------- #
# YAML da sessão (só o subconjunto que o iRacing usa: mapas e listas por indentação)
# --------------------------------------------------------------------------- #
def _scalar(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def parse_yaml(text: str):
    """Leitor tolerante do YAML do iRacing. Os valores ficam em texto (quem usa converte).

    Aceita nomes com ':' ou acentos (o iRacing não põe aspas nos nomes dos pilotos/equipas).
    """
    toks: list[tuple[int, bool, str]] = []
    for raw in text.replace("\t", " ").splitlines():
        st = raw.strip()
        if not st or st in ("---", "...") or st.startswith("#"):
            continue
        ind = len(raw) - len(raw.lstrip(" "))
        if st == "-" or st.startswith("- "):
            toks.append((ind, True, st[2:].strip()))
        else:
            toks.append((ind, False, st))
    pos = [0]

    def block(ind):
        if pos[0] < len(toks) and toks[pos[0]][1] and toks[pos[0]][0] == ind:
            return seq(ind)
        return mapping(ind)

    def mapping(ind):
        d: dict = {}
        while pos[0] < len(toks):
            t_ind, item, s = toks[pos[0]]
            if t_ind != ind or item:
                break
            pos[0] += 1
            key, sep, val = s.partition(":")
            if not sep:
                continue
            key = key.strip()
            if val.strip():
                d[key] = _scalar(val)
            elif pos[0] < len(toks) and (toks[pos[0]][0] > ind or (toks[pos[0]][1] and toks[pos[0]][0] == ind)):
                d[key] = block(toks[pos[0]][0])
            else:
                d[key] = ""
        return d

    def seq(ind):
        out: list = []
        while pos[0] < len(toks) and toks[pos[0]][1] and toks[pos[0]][0] == ind:
            s = toks[pos[0]][2]
            if not s:
                pos[0] += 1
                out.append(block(toks[pos[0]][0]) if pos[0] < len(toks) and toks[pos[0]][0] > ind else "")
                continue
            if ":" in s and s[0] not in "\"'":
                toks[pos[0]] = (ind + 2, False, s)       # o resto do item vem com indentação ind+2
                out.append(mapping(ind + 2))
            else:
                pos[0] += 1
                out.append(_scalar(s))
        return out

    if not toks:
        return {}
    return block(toks[0][0])


def _num(v, default: float = 0.0) -> float:
    """'5.51 km' -> 5.51, '0x00ff00' -> 65280, '' -> default."""
    if v is None:
        return default
    s = str(v).strip()
    if s.lower().startswith("0x"):
        try:
            return float(int(s, 16))
        except ValueError:
            return default
    num = s.split()[0] if s else ""
    try:
        return float(num)
    except ValueError:
        return default


# --------------------------------------------------------------------------- #
# Memória do SDK
# --------------------------------------------------------------------------- #


def ir_sector_bounds(info) -> tuple:
    """Início do S2 e do S3 (fração da volta) a partir do SplitTimeInfo do iRacing. Se a pista tiver
    mais de 3 setores, usa os limites mais perto de 1/3 e 2/3."""
    try:
        secs = info.get("SplitTimeInfo", {}).get("Sectors") or []
        starts = sorted(float(s.get("SectorStartPct", 0)) for s in secs if isinstance(s, dict))
    except (AttributeError, TypeError, ValueError):
        starts = []
    starts = [x for x in starts if 0.02 < x < 0.98]
    if len(starts) >= 2:
        a = min(starts, key=lambda x: abs(x - 1 / 3))
        b = min((x for x in starts if x > a), key=lambda x: abs(x - 2 / 3), default=None)
        if b is not None:
            return (a, b)
    return (1 / 3, 2 / 3)


def _sector_of(p: float, bounds: tuple) -> int:
    return 0 if p < bounds[0] else (1 if p < bounds[1] else 2)

def ir_license(lic) -> str:
    """"A 4.32" -> "A4.32" (letra da licença + safety rating)."""
    if not isinstance(lic, str) or not lic.strip():
        return ""
    parts = lic.split()
    return (parts[0][:1] + (parts[1] if len(parts) > 1 else "")).upper() if parts else ""


def ir_rating(v) -> str:
    """iRating 2412 -> "2.4k"."""
    n = _num(v, 0)
    if n <= 0:
        return ""
    return f"{n / 1000:.1f}k" if n >= 1000 else f"{n:.0f}"

class IRSDK:
    """Lê a memória do iRacing SDK a partir de qualquer objeto tipo bytes (mmap, bytes, bytearray)."""

    def __init__(self, mem) -> None:
        self.mem = mem
        self.vars: dict[str, tuple[struct.Struct, int, int]] = {}
        self._var_key = None
        self._yaml_ver = None
        self.info: dict = {}

    def header(self) -> tuple:
        return _HEADER.unpack_from(self.mem, 0)

    def connected(self) -> bool:
        try:
            h = self.header()
        except struct.error:
            return False
        return bool(h[1] & STATUS_CONNECTED) and h[6] > 0 and h[8] > 0

    def _load_vars(self, num: int, off: int) -> None:
        if self._var_key == (num, off):
            return
        self.vars = {}
        for i in range(num):
            typ, offset, count, _ct, name, _desc, _unit = _VARHDR.unpack_from(self.mem, off + i * VARHDR_SIZE)
            code = _TYPES.get(typ)
            if code is None:
                continue
            nm = name.split(b"\0", 1)[0].decode("latin-1")
            self.vars[nm] = (struct.Struct(f"<{max(1, count)}{code[0]}"), offset, count)
        self._var_key = (num, off)

    def latest(self) -> tuple[int, bytes] | None:
        """(tick, cópia do buffer mais recente). Copia e confirma que o jogo não escreveu por cima."""
        h = self.header()
        num_buf, buf_len = max(0, min(4, h[8])), h[9]
        if num_buf == 0 or buf_len <= 0:
            return None
        self._load_vars(h[6], h[7])
        for _ in range(3):
            bufs = [_VARBUF.unpack_from(self.mem, VARBUF_OFFSET + 16 * i) for i in range(num_buf)]
            idx = max(range(num_buf), key=lambda i: bufs[i][0])
            tick, off = bufs[idx][0], bufs[idx][1]
            data = bytes(self.mem[off:off + buf_len])
            if _VARBUF.unpack_from(self.mem, VARBUF_OFFSET + 16 * idx)[0] == tick:
                return tick, data
        return tick, data

    def session_info(self) -> dict:
        """YAML da sessão, convertido só quando o jogo o atualiza."""
        h = self.header()
        if h[3] != self._yaml_ver:
            raw = bytes(self.mem[h[5]:h[5] + h[4]]).split(b"\0", 1)[0]
            try:
                self.info = parse_yaml(raw.decode("cp1252", errors="replace")) or {}
            except Exception:
                self.info = {}
            self._yaml_ver = h[3]
        return self.info

    def get(self, data: bytes, name: str, default=None):
        v = self.vars.get(name)
        if v is None:
            return default
        st, off, count = v
        try:
            vals = st.unpack_from(data, off)
        except struct.error:
            return default
        return vals[0] if count <= 1 else vals


# --------------------------------------------------------------------------- #
def _flag_phase(state: int, flags: int, race: bool) -> int:
    """Converte o estado da sessão do iRacing para as fases que os overlays usam (as do LMU)."""
    if flags & F_RED:
        return 7
    if state in (5, 6) or flags & F_CHECKERED:
        return 8
    if race and flags & (F_START_READY | F_START_SET):
        return 4
    if state == 3:
        return 3
    if state in (1, 2) and race:
        return 0
    if flags & (F_CAUTION | F_CAUTION_WAVING):
        return 6
    return 5


def _ori_from_yaw(yaw: float) -> tuple:
    fx, fz = math.cos(yaw), math.sin(yaw)
    return ((-fz, 0.0, -fx), (0.0, 1.0, 0.0), (fx, 0.0, -fz))


def _to_world(ori, pos, lx: float, lz: float) -> tuple[float, float, float]:
    return (pos[0] + ori[0][0] * lx + ori[0][2] * lz, pos[1], pos[2] + ori[2][0] * lx + ori[2][2] * lz)


class IRacingConverter:
    """Converte buffers do SDK em Snapshots. Guarda o pouco estado que o iRacing não dá
    (posição integrada do teu carro, velocidade dos outros, nº de paragens)."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.reason = ""
        self._key = None
        self._tick = None
        self._last: Snapshot | None = None
        self._pos = [0.0, 0.0, 0.0]
        self._prev_t = None
        self._prev_pct: dict[int, tuple[float, float]] = {}
        self._speed: dict[int, float] = {}
        self._was_pit: dict[int, bool] = {}
        self._stops: dict[int, int] = {}
        self._in_stall_before = False
        self._drv = (None, [])

    def _drivers(self, sdk: IRSDK, drivers: list) -> list[tuple]:
        """Dados fixos de cada piloto (só mudam quando o YAML muda), já convertidos."""
        if self._drv[0] == sdk._yaml_ver and self._drv[1]:
            return self._drv[1]
        out = []
        for drv in drivers:
            if not isinstance(drv, dict) or _num(drv.get("CarIsPaceCar")) or _num(drv.get("IsSpectator")):
                continue
            i = int(_num(drv.get("CarIdx"), -1))
            if i < 0:
                continue
            cls_name = drv.get("CarClassShortName") or drv.get("CarScreenNameShort") or drv.get("CarScreenName") or ""
            model = drv.get("CarScreenName") or drv.get("CarScreenNameShort") or ""
            num = str(drv.get("CarNumber") or "")
            user, team = drv.get("UserName") or "", drv.get("TeamName") or ""
            col = drv.get("CarClassColor")
            if cls_name and col:
                c = int(_num(col))
                theme.CLASS_COLORS.setdefault(cls_name, ((c >> 16) & 255, (c >> 8) & 255, c & 255, 255))
            out.append((i, user, team if team and team != user else "", f"{model} #{num}" if num else model, num,
                        cls_name, _num(drv.get("CarClassEstLapTime")), ir_license(drv.get("LicString")),
                        ir_rating(drv.get("IRating")), int(_num(drv.get("IRating"), 0))))
        self._drv = (sdk._yaml_ver, out)
        return out

    # ------------------------------------------------------------------ #
    def convert(self, sdk: IRSDK, tick: int, d: bytes) -> Snapshot | None:
        g = lambda name, default=0: sdk.get(d, name, default)   # noqa: E731
        info = sdk.session_info()
        wk = info.get("WeekendInfo", {}) if isinstance(info, dict) else {}
        di = info.get("DriverInfo", {}) if isinstance(info, dict) else {}
        drivers = di.get("Drivers") or []
        if not isinstance(drivers, list) or not drivers:
            self.reason = f"sem pilotos no YAML (secções: {', '.join(list(info)[:8]) if isinstance(info, dict) else '-'})"
            return None
        me_idx = int(g("PlayerCarIdx", int(_num(di.get("DriverCarIdx"), -1))))
        tl = str(wk.get("TrackLength") or "")
        L = _num(tl) * (1609.344 if "mi" in tl.lower() else 1000.0)
        if L <= 0 or me_idx < 0:
            self.reason = f"pista/jogador inválidos (TrackLength={tl!r}, PlayerCarIdx={me_idx})"
            return None
        sess_num = int(g("SessionNum", 0))
        sessions = (info.get("SessionInfo") or {}).get("Sessions") or []
        sess = next((x for x in sessions if isinstance(x, dict) and int(_num(x.get("SessionNum"), -1)) == sess_num), {})
        kind = session_kind_from_name(sess.get("SessionType") or sess.get("SessionName") or "")
        race = kind == "race"
        track = wk.get("TrackDisplayName") or wk.get("TrackName") or "iRacing"

        key = (track, sess_num, me_idx)
        if key != self._key:
            self.reset()
            self._key = key
        new_tick = tick != self._tick
        self._tick = tick

        t = float(g("SessionTime", 0.0))
        remain = float(g("SessionTimeRemain", -1.0))
        laps_total = int(g("SessionLapsTotal", 0))
        state, flags = int(g("SessionState", 0)), int(g("SessionFlags", 0))
        phase = _flag_phase(state, flags, race)
        caution = phase == 6
        sector_flags = [0, 0, 0]

        pct = g("CarIdxLapDistPct", ())
        laps = g("CarIdxLapCompleted", ())
        pos_ = g("CarIdxPosition", ())
        onpit = g("CarIdxOnPitRoad", ())
        surf = g("CarIdxTrackSurface", ())
        best = g("CarIdxBestLapTime", ())
        last = g("CarIdxLastLapTime", ())
        f2 = g("CarIdxF2Time", ())
        cflags = g("CarIdxSessionFlags", ())
        tcomp = g("CarIdxTireCompound", ())
        bounds = ir_sector_bounds(info)
        est_t = g("CarIdxEstTime", ())

        def arr(a, i, default):
            return a[i] if isinstance(a, tuple) and 0 <= i < len(a) else default

        # velocidade estimada dos outros carros (o iRacing só dá a do teu)
        dt = t - self._prev_t if self._prev_t is not None else 0.0
        vehicles: list[Vehicle] = []
        me = None
        for i, user, team, vname, num, cls_name, est, sr, dr, irt in self._drivers(sdk, drivers):
            p = float(arr(pct, i, -1.0))
            s = int(arr(surf, i, TRK_NOT_IN_WORLD))
            in_pit = bool(arr(onpit, i, False))
            lap_dist = max(0.0, p) * L
            if new_tick and dt > 0 and p >= 0:
                prev = self._prev_pct.get(i)
                if prev is not None:
                    dp = p - prev[0]
                    if dp < -0.5:
                        dp += 1.0
                    elif dp > 0.5:
                        dp -= 1.0
                    inst = max(0.0, dp * L / dt)
                    self._speed[i] = 0.7 * self._speed.get(i, inst) + 0.3 * inst
                self._prev_pct[i] = (p, t)
            if in_pit and not self._was_pit.get(i, False):
                self._stops[i] = self._stops.get(i, 0) + 1
            self._was_pit[i] = in_pit
            if s == TRK_PIT_STALL:
                ps = 3
            elif in_pit:
                ps = 2
            elif s == TRK_APPROACH_PITS:
                ps = 1                                   # a caminho das boxes: "BOX, BOX."
            else:
                ps = 0
            bl, ll = float(arr(best, i, -1.0)), float(arr(last, i, -1.0))
            cf = int(arr(cflags, i, 0))
            v = Vehicle(
                id=i, driver=user, vehicle_name=vname, team=team, number=num, cls=cls_name, place=int(arr(pos_, i, 0)), total_laps=max(0, int(arr(laps, i, 0))),
                lap_dist=lap_dist, best=bl if bl > 0 else 0.0, last=ll if ll > 0 else 0.0,
                t_behind_leader=max(0.0, float(arr(f2, i, 0.0))), in_pits=in_pit,
                in_garage=s == TRK_NOT_IN_WORLD, pit_state=ps, pitstops=self._stops.get(i, 0),
                is_player=i == me_idx, speed=self._speed.get(i, 0.0), flag=6 if cf & F_BLUE else 0,
                est_lap=est, sector=_sector_of(max(0.0, p), bounds), sr=sr, dr=dr, irating=irt,
                tyre={0: "D", 1: "W"}.get(int(arr(tcomp, i, -1)), ""),
                time_into_lap=max(0.0, float(arr(est_t, i, 0.0))),
            )
            vehicles.append(v)
            if v.is_player:
                me = v
        if me is None:
            self.reason = f"o teu carro (CarIdx {me_idx}) não está na lista de pilotos ({len(vehicles)} carros)"
            return None
        self.reason = ""
        self._prev_t = t

        # posições: as do jogo; quem ainda não tem fica a seguir, pela distância (corrida) ou volta
        ranked = sorted((v for v in vehicles if v.place > 0), key=lambda v: v.place)
        rest = [v for v in vehicles if v.place <= 0]
        if race:
            rest.sort(key=lambda v: -(v.total_laps + v.lap_dist / L))
        else:
            rest.sort(key=lambda v: (v.best <= 0, v.best))
        for n, v in enumerate(ranked + rest, 1):
            v.place = n
        lead = ranked[0] if ranked else (rest[0] if rest else me)
        lead_total = lead.total_laps + lead.lap_dist / L
        for v in vehicles:
            v.laps_behind_leader = max(0, int(lead_total - (v.total_laps + v.lap_dist / L))) if race else 0
        assign_class_places(vehicles)

        # o teu carro
        speed = float(g("Speed", 0.0))
        me.speed = speed
        yaw = float(g("Yaw", 0.0))
        if new_tick and 0 < dt < 0.5 and int(g("PlayerTrackSurface", TRK_ON_TRACK)) != TRK_NOT_IN_WORLD:
            vx, vy = float(g("VelocityX", 0.0)), float(g("VelocityY", 0.0))
            cy, sy = math.cos(yaw), math.sin(yaw)
            self._pos[0] += (vx * cy - vy * sy) * dt
            self._pos[2] += (vx * sy + vy * cy) * dt
        ori = _ori_from_yaw(yaw)
        ppos = (self._pos[0], 0.0, self._pos[2])
        in_stall = bool(g("PlayerCarInPitStall", False))
        if in_stall:
            me.pit_state = 3
        elif me.in_pits and self._in_stall_before:
            me.pit_state = 4                              # a sair da box
        self._in_stall_before = in_stall or (self._in_stall_before and me.in_pits)
        pit_pct = _num(di.get("DriverPitTrkPct"), -1.0)
        me.pit_lap_dist = pit_pct * L if pit_pct > 0 else 0.0
        if flags & (F_BLACK | F_DQ):
            me.penalties = 1
        if flags & F_BLUE:
            me.flag = 6
        if flags & (F_YELLOW | F_YELLOW_WAVING) and not caution:
            sector_flags[me.sector] = 1                   # amarela local: no teu setor

        # radar: à frente/atrás pela distância na volta, de lado pelo spotter do jogo
        side = SPOTTER.get(int(g("CarLeftRight", 0)), (0, 0))
        near: list[tuple[float, Vehicle]] = []
        for v in vehicles:
            if v is me or v.in_garage:
                v.pos, v.fwd = (1e6, 0.0, 1e6), (0.0, 0.0, -1.0)
                continue
            dz = v.lap_dist - me.lap_dist
            if dz > L / 2:
                dz -= L
            elif dz < -L / 2:
                dz += L
            near.append((abs(dz), v))
            v.pos = _to_world(ori, ppos, 0.0, -dz)
            v.fwd = (math.cos(yaw), 0.0, math.sin(yaw))
        near.sort(key=lambda e: e[0])
        lefts, rights = side
        for n, (adz, v) in enumerate(e for e in near if e[0] < 8.0 and not e[1].in_pits):
            lat = None
            if lefts:
                lat = 3.2 * (side[0] - lefts + 1)
                lefts -= 1
            elif rights:
                lat = -3.2 * (side[1] - rights + 1)
                rights -= 1
            if lat is None:
                break
            dz = v.lap_dist - me.lap_dist
            dz = dz - L if dz > L / 2 else (dz + L if dz < -L / 2 else dz)
            v.pos = _to_world(ori, ppos, lat, -dz)

        # vento: ângulo entre o vento e a frente do carro (os dois medidos a partir do norte)
        wv, wd = float(g("WindVel", 0.0)), float(g("WindDir", 0.0))
        a = wd - float(g("YawNorth", yaw))
        wl = (wv * math.sin(a), wv * math.cos(a))          # (esquerda, trás) no referencial do carro
        wind = (ori[0][0] * wl[0] + ori[0][2] * wl[1], 0.0, ori[2][0] * wl[0] + ori[2][2] * wl[1])

        wet = int(g("TrackWetness", 0))
        end_et = t + remain if 0 <= remain < 604800 else 0.0
        session = Session(
            track=track, kind=kind, raw=sess_num, phase=phase,
            yellow_state=(4 if g("PitsOpen", True) else 2) if caution else 0, sector_flags=tuple(sector_flags),
            current_et=t, end_et=end_et, max_laps=laps_total if 0 < laps_total < 32767 else 0, track_length=L,
            in_realtime=(bool(g("IsOnTrack", False)) or bool(g("IsOnTrackCar", False)))
            and not bool(g("IsReplayPlaying", False)),
            air_temp=float(g("AirTemp", 0.0)), track_temp=float(g("TrackTempCrew", g("TrackTemp", 0.0))),
            rain=float(g("Precipitation", 0.0)), wetness=max(0.0, min(1.0, (wet - 1) / 6.0)) if wet > 0 else 0.0,
            wind=wind, sector_bounds=bounds,
            sky=({0: 0, 1: 2, 2: 3, 3: 4}.get(int(g("Skies", -1)), -1) if g("Skies", None) is not None else -1),
        )
        if session.rain > 0.02 and session.sky >= 0:
            session.sky = 5 + min(5, int(session.rain * 6))          # mesma escala do LMU (5+ = a chover)
        session.wetness_min = session.wetness_max = session.wetness
        player = self._player(g, di, me, ori, ppos, t)
        # incidentes (o iRacing não tem track limits: os pontos de incidente fazem esse papel)
        inc = g("PlayerCarMyIncidentCount", None)
        if inc is not None:
            player.tl_points, player.tl_kind = float(inc), "inc"
            lim = (wk.get("WeekendOptions") or {}).get("IncidentLimit", "") if isinstance(wk, dict) else ""
            player.tl_limit = _num(lim)
        player.repair_req = float(g("PitRepairLeft", -1.0))
        player.repair_opt = float(g("PitOptRepairLeft", -1.0))
        ew = int(g("EngineWarnings", 0))
        player.warnings = ((1 if ew & 0x1 else 0) | (8 if ew & 0x2 else 0) | (4 if ew & 0x4 else 0)
                           | (16 if ew & 0x8 else 0) | (2 if ew & 0x40 else 0))
        player.overheating = bool(ew & 0x41)
        snap = Snapshot(session=session, vehicles=vehicles, me=me, player=player, source="iracing",
                        world_pos=False)
        self._last = snap
        return snap

    @staticmethod
    def _player(g, di, me, ori, ppos, t) -> Player:
        tyres = []
        for c in ("LF", "RF", "LR", "RR"):
            lcr = tuple(float(g(f"{c}temp{x}", 0.0)) for x in ("CL", "CM", "CR"))
            wear = [float(g(f"{c}wear{x}", 1.0)) for x in ("L", "M", "R")]
            tyres.append(Tyre(temp_lcr=lcr, inner_lcr=lcr, carcass=sum(lcr) / 3, pressure=float(g(f"{c}press", 0.0)),
                              wear=sum(wear) / 3, optimal=0.0))
        ang_max = float(g("SteeringWheelAngleMax", 0.0))
        steer = -float(g("SteeringWheelAngle", 0.0)) / ang_max if ang_max > 0 else 0.0
        thr = float(g("ThrottleRaw", g("Throttle", 0.0)))
        brk = float(g("BrakeRaw", g("Brake", 0.0)))
        clu = 1.0 - float(g("ClutchRaw", g("Clutch", 1.0)))     # iRacing: 1 = embraiado (pedal solto)
        cap = _num(di.get("DriverCarFuelMaxLtr")) * (_num(di.get("DriverCarMaxFuelPct"), 1.0) or 1.0)
        bat = g("EnergyERSBatteryPct", None)
        dl_ok = bool(g("LapDeltaToBestLap_OK", False))
        comp = int(g("PlayerTireCompound", -1))
        compound = {0: "Dry", 1: "Wet"}.get(comp, "")
        return Player(
            id=me.id, vehicle_model=me.vehicle_name.split(" #")[0],
            fuel=float(g("FuelLevel", 0.0)), fuel_capacity=cap, virtual_energy=0.0,
            battery=float(bat) if bat is not None else -1.0,
            lap_time_now=float(g("LapCurrentLapTime", 0.0)), elapsed=t, lap_invalid=False,
            delta_game=float(g("LapDeltaToBestLap", 0.0)) if dl_ok else 0.0,
            speed=float(g("Speed", 0.0)), rpm=float(g("RPM", 0.0)), max_rpm=_num(di.get("DriverCarRedLine")),
            gear=int(g("Gear", 0)), max_gears=0, water_temp=float(g("WaterTemp", 0.0)), oil_temp=float(g("OilTemp", 0.0)),
            throttle=max(0.0, min(1.0, thr)), brake=max(0.0, min(1.0, brk)), clutch=max(0.0, min(1.0, clu)),
            steering=max(-1.0, min(1.0, steer)), throttle_f=float(g("Throttle", thr)), brake_f=float(g("Brake", brk)),
            steering_range=math.degrees(2 * ang_max),
            tc=int(g("dcTractionControl", 0) or 0), abs=int(g("dcABS", 0) or 0),
            abs_active=bool(g("BrakeABSactive", False)), brake_bias=float(g("dcBrakeBias", 0.0) or 0.0),
            limiter_on=bool(int(g("EngineWarnings", 0)) & ENGINE_PIT_LIMITER),
            compound_front=compound, compound_rear=compound, tyres=tyres, pos=ppos, ori=ori,
        )


# --------------------------------------------------------------------------- #
class IRacingSource:
    """Fonte de dados do iRacing para a app (lê a memória partilhada a cada frame)."""

    label = "iRacing"

    def __init__(self) -> None:
        self._mm = None
        self.sdk: IRSDK | None = None
        self.conv = IRacingConverter()
        self.need_positions = True
        self.status = ("ir_waiting", "")
        self._retry_at = 0.0
        self.diag: dict = {"aberto": False}

    def _open(self) -> bool:
        if sys.platform != "win32":
            self.status = ("ir_windows_only", "")
            return False
        import time
        now = time.perf_counter()
        if now < self._retry_at:
            return False
        self._retry_at = now + 1.0
        try:
            # só abre se o iRacing já criou a memória (não cria uma vazia no lugar dele)
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.OpenFileMappingW.restype = ctypes.c_void_p
            h = k32.OpenFileMappingW(0x0004, False, MAP_NAME)        # FILE_MAP_READ
            if not h:
                self.status = ("ir_waiting", "")
                self.diag["memória"] = "o iRacing ainda não criou a memória partilhada (não está aberto?)"
                return False
            mem = self._map_view(k32, h)
            if mem is not None:                      # mapeia a memória inteira, seja qual for o tamanho
                self._handle, self._mm = h, mem
            else:
                k32.CloseHandle(ctypes.c_void_p(h))
                self._mm = mmap.mmap(-1, MAP_SIZE, MAP_NAME, access=mmap.ACCESS_READ)
            self.diag["memória"] = f"aberta ({len(self._mm)} bytes)"
            self.sdk = IRSDK(self._mm)
            return True
        except Exception as exc:  # pragma: no cover - só em Windows
            self.status = ("ir_open_error", str(exc))
            self.diag["memória"] = f"erro a abrir: {exc}"
            return False

    @staticmethod
    def _map_view(k32, h):
        """MapViewOfFile da secção inteira + VirtualQuery para saber o tamanho. None se falhar."""
        import ctypes
        from ctypes import wintypes
        try:
            k32.MapViewOfFile.restype = ctypes.c_void_p
            k32.MapViewOfFile.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                          ctypes.c_size_t]
            addr = k32.MapViewOfFile(ctypes.c_void_p(h), 0x0004, 0, 0, 0)
            if not addr:
                return None

            class MBI(ctypes.Structure):
                _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                            ("AllocationProtect", wintypes.DWORD), ("PartitionId", wintypes.WORD),
                            ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD),
                            ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD)]
            mbi = MBI()
            k32.VirtualQuery.argtypes = [ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
            if not k32.VirtualQuery(ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
                return None
            size = int(mbi.RegionSize)
            return (ctypes.c_char * size).from_address(addr) if size > 0 else None
        except Exception:
            return None

    def read(self) -> Snapshot | None:
        if self.sdk is None and not self._open():
            return None
        return self.read_from(self.sdk)

    def read_from(self, sdk: IRSDK) -> Snapshot | None:
        self.diag["aberto"] = True
        try:
            h = sdk.header()
            self.diag["cabeçalho"] = dict(zip(("ver", "status", "tickRate", "sessionInfoUpdate", "sessionInfoLen",
                                               "sessionInfoOffset", "numVars", "varHeaderOffset", "numBuf",
                                               "bufLen"), h[:10]))
        except Exception as exc:
            self.diag["cabeçalho"] = f"erro: {exc}"
        if not sdk.connected():
            self.status = ("ir_not_running", "")
            self.conv.reset()
            return None
        got = sdk.latest()
        if got is None:
            self.status = ("ir_no_data", "buffers vazios")
            return None
        try:
            snap = self.conv.convert(sdk, *got)
        except Exception as exc:
            import traceback
            self.diag["erro"] = traceback.format_exc()[-1500:]
            self.status = ("ir_no_data", f"erro: {exc}")
            return None
        info = sdk.info if isinstance(sdk.info, dict) else {}
        d = got[1]
        self.diag.update({
            "variáveis": len(sdk.vars), "yaml_secções": list(info)[:12],
            "pilotos": len((info.get("DriverInfo") or {}).get("Drivers") or []),
            "PlayerCarIdx": sdk.get(d, "PlayerCarIdx"), "IsOnTrack": sdk.get(d, "IsOnTrack"),
            "IsOnTrackCar": sdk.get(d, "IsOnTrackCar"), "IsReplayPlaying": sdk.get(d, "IsReplayPlaying"),
            "SessionNum": sdk.get(d, "SessionNum"), "TrackLength": (info.get("WeekendInfo") or {}).get("TrackLength"),
            "motivo": self.conv.reason,
        })
        if snap is None:
            self.status = ("ir_no_data", self.conv.reason)
        elif not snap.session.in_realtime:
            self.status = ("ir_not_driving", snap.session.track)
        else:
            self.status = ("ir_connected", snap.session.track)
        return snap
