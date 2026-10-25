"""Testes sem jogo nem Qt:  python -m tests.test_core   (a partir da pasta do projeto)"""

from __future__ import annotations

import ctypes
import math
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyLMUSharedMemory import lmu_data as L  # noqa: E402
from lmuov.model import Player, Session, Snapshot, Vehicle  # noqa: E402
from lmuov.overlays.wind import wind_relative  # noqa: E402
from lmuov.relcalc import relatives  # noqa: E402
from lmuov.source_lmu import parse  # noqa: E402
from lmuov.trackers import Trackers  # noqa: E402


class CheckCanvas:
    """Canvas de teste sem bibliotecas gráficas: verifica que as coordenadas são números finitos."""

    def __init__(self):
        self.ops = 0

    def _chk(self, *vals):
        for v in vals:
            if isinstance(v, (list, tuple)):
                self._chk(*v)
            elif isinstance(v, float):
                assert math.isfinite(v), vals

    def __getattr__(self, name):
        def f(*a, **k):
            self.ops += 1
            self._chk(*[x for x in a if not isinstance(x, str)])
        return f

    def measure(self, s, size, weight=400, spacing=0.0):
        return len(s) * size * 0.5


def make_raw():
    d = L.LMUObjectOut()
    si = d.scoring.scoringInfo
    si.mTrackName = b"Le Mans"
    si.mSession = 10
    si.mGamePhase = 5
    si.mYellowFlagState = b"\xff"   # -1
    si.mSectorFlag[0] = 1           # índice 0 = S3 no LMU
    si.mNumVehicles = 2
    si.mLapDist = 13626.0
    si.mCurrentET = 600.0
    si.mEndET = 3600.0
    si.mMaxLaps = 2147483647
    si.mInRealtime = True
    si.mAmbientTemp, si.mTrackTemp = 21.5, 30.0
    si.mWind.x, si.mWind.z = 3.0, -4.0
    for i, (name, drv, cls, place, player) in enumerate([
            (b"Toyota #7", b"Ana", b"Hyper", 1, False),
            (b"Porsche #6 2025", "José Ferreira".encode("cp1252"), b"Hyper", 2, True)]):
        v = d.scoring.vehScoringInfo[i]
        v.mID = 10 + i
        v.mVehicleName = name
        v.mDriverName = drv
        v.mVehicleClass = cls
        v.mPlace = place
        v.mIsPlayer = player
        v.mTotalLaps = 5
        v.mLapDist = 1000.0 + 500 * i
        v.mSector = 1       # S1
        v.mBestLapTime = 210.5 + i
        v.mLocalVel.z = -60.0
        v.mFlag = 6 if player else 0
    t = d.telemetry
    t.activeVehicles = 2
    t.playerHasVehicle = True
    t.playerVehicleIdx = 1
    pt = t.telemInfo[1]
    pt.mID = 11
    pt.mFuel, pt.mFuelCapacity, pt.mVirtualEnergy = 40.0, 90.0, 0.62
    pt.mElapsedTime, pt.mLapStartET = 600.0, 540.0
    pt.mVehicleModel = b"Porsche 963"
    pt.mLocalVel.z = -60.0
    pt.mEngineRPM, pt.mEngineMaxRPM, pt.mGear = 7200.0, 9000.0, 4
    pt.mRearBrakeBias = 0.455
    pt.mUnfilteredThrottle, pt.mUnfilteredBrake = 0.8, 0.1
    pt.mPos.x, pt.mPos.z = 100.0, -50.0
    t.telemInfo[0].mID = 10
    t.telemInfo[0].mPos.x, t.telemInfo[0].mPos.z = 103.0, -51.0
    pt.mFrontTireCompoundName = b"Medium"
    for k in range(3):
        pt.mOri[k].x, pt.mOri[k].y, pt.mOri[k].z = [(1, 0, 0), (0, 1, 0), (0, 0, 1)][k]
    for w in pt.mWheels:
        w.mTemperature[0], w.mTemperature[1], w.mTemperature[2] = 363.15, 361.15, 359.15
        w.mPressure, w.mWear, w.mOptimalTemp = 172.0, 0.91, 90.0
        w.mTireCarcassTemperature = 358.15
        w.mBrakeTemp = 450.0
    return d


def test_layout():
    # A estrutura tem de ter tamanho estável e plausível (centenas de KB)
    size = ctypes.sizeof(L.LMUObjectOut)
    assert 200_000 < size < 2_000_000, size
    print("sizeof(LMUObjectOut) =", size)


def test_parse():
    snap = parse(make_raw())
    assert snap is not None
    s, me, p = snap.session, snap.me, snap.player
    assert s.kind == "race" and s.track == "Le Mans"
    assert s.yellow_state == -1
    assert s.sector_flags == (0, 0, 1), s.sector_flags          # S3 amarela
    assert s.max_laps == 0 and abs(s.time_left - 3000) < 1e-6
    assert me.driver == "José Ferreira" and me.number == "6" and me.place == 2 and me.class_place == 2
    assert me.sector == 0 and me.flag == 6 and abs(me.speed - 60) < 1e-6
    assert p.vehicle_model == "Porsche 963" and abs(p.virtual_energy - 0.62) < 1e-6
    assert abs(p.lap_time_now - 60) < 1e-6
    assert p.gear == 4 and p.rpm == 7200 and abs(p.brake_bias - 54.5) < 1e-6 and p.throttle == 0.8
    other = next(v for v in snap.vehicles if v.id == 10)
    assert other.pos == (103.0, 0.0, -51.0), other.pos            # posição vem da telemetria
    ty = p.tyres[0]
    assert [round(x, 2) for x in ty.temp_lcr] == [90.0, 88.0, 86.0] and round(ty.carcass, 2) == 85.0
    assert ty.optimal == 90.0 and ty.wear == 0.91
    print("parse ok:", me.driver, s.sector_flags, [round(x) for x in ty.temp_lcr])


def test_relatives_wrap():
    L_ = 5000.0
    me = Vehicle(id=1, is_player=True, total_laps=10, lap_dist=4900, est_lap=100)
    a = Vehicle(id=2, total_laps=11, lap_dist=100)     # 200 m à frente, mesma volta (atravessou a meta)
    b = Vehicle(id=3, total_laps=10, lap_dist=4800)    # 100 m atrás
    c = Vehicle(id=4, total_laps=12, lap_dist=4950)    # 50 m à frente mas 2 voltas à frente
    snap = Snapshot(Session(track_length=L_), [me, a, b, c], me, Player())
    r = {x.v.id: x for x in relatives(snap)}
    assert abs(r[2].dist - 200) < 1e-6 and r[2].lap_diff == 0, r[2]
    assert abs(r[3].dist + 100) < 1e-6 and r[3].lap_diff == 0
    assert abs(r[4].dist - 50) < 1e-6 and r[4].lap_diff == 2
    assert abs(r[2].gap - 4.0) < 1e-6
    print("relativo ok")


def test_wind():
    ident = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    # carro a apontar para -z (frente). Vento a soprar para +z = de frente.
    fwd, left = wind_relative((0, 0, 5), ident)
    assert fwd == -5 and left == 0
    # vento para +x = para a esquerda do carro = vem da direita
    fwd, left = wind_relative((4, 0, 0), ident)
    assert left == 4
    # carro rodado 180° em y: a frente passa a +z, logo vento para +z é por trás
    rot = ((-1, 0, 0), (0, 1, 0), (0, 0, -1))
    fwd, _ = wind_relative((0, 0, 5), rot)
    assert fwd == 5
    print("vento ok")


def test_trackers_demo():
    from lmuov.source_demo import DemoSource
    with tempfile.TemporaryDirectory() as tmp:
        demo = DemoSource()
        tr = Trackers(Path(tmp))
        for _ in range(2500):
            demo.step(0.2)
            ctx = tr.update(demo.snapshot(), now=demo.t)
        f, d = ctx.fuel, ctx.delta
        assert f.uses_ve and f.samples >= 2 and abs(f.per_lap - demo.ve_per_lap) < 0.05, f
        assert f.race_laps_left > 0 and f.needed > 0
        assert d.has_ref and abs(d.delta) < 2.0 and 100 < d.ref_time < 115, d
        saved = list(Path(tmp).rglob("delta_refs/*.json"))
        assert saved, "referência de delta não foi guardada"
        assert ctx.track_map is not None and len(ctx.track_map.pts) > 100, "mapa da pista não foi gravado"
        assert list(Path(tmp).rglob("track_maps/*.json")), "mapa não foi guardado"
        # um segundo arranque carrega o mapa do disco logo de início
        tr2 = Trackers(Path(tmp))
        assert tr2.update(demo.snapshot(), now=demo.t).track_map is not None
        assert all(0 < w < 3 for w in ctx.wear_per_lap), ctx.wear_per_lap
        print(f"trackers ok: VE {f.per_lap:.2f}%/v, delta {d.delta:+.3f}, ref {d.ref_time:.3f}")


def test_overlays_draw():
    """Todos os overlays desenham sem erros, com e sem dados, e em vários estados de bandeira."""
    from lmuov.overlays import ALL
    from lmuov.source_demo import DemoSource
    from lmuov.trackers import Context

    class Null:
        calls = 0

        def __getattr__(self, name):
            def f(*a, **k):
                Null.calls += 1
                return 10.0
            return f

    demo = DemoSource()
    tr = Trackers(None)
    snap = demo.snapshot()
    ctx = tr.update(snap, now=demo.t)
    from lmuov import i18n
    for lang in i18n.LANGS:
        i18n.set_language(lang)
        for over in (None, {"phase": 6, "yellow_state": 2}, {"flag": 6, "penalties": 2}, {"phase": 8},
                     {"sector_flags": (1, 1, 1)}, {"phase": 7}, {"phase": 4}, {"phase": 3}):
            demo.override_flags = over
            for me in ({}, {"in_pits": True, "pit_state": 2}, {"in_pits": True, "pit_state": 3},
                       {"in_pits": True, "pit_state": 4}, {"pit_state": 1}):
                demo.override_me = me
                s = demo.snapshot()
                ctx.edit_mode = bool(me)
                for cls in ALL:
                    ov = cls()
                    w, h = ov.size(s, ctx)
                    ov.draw(Null(), s, ctx, w, h)
                    w, h = ov.size(None, Context())
                    ov.draw(Null(), None, Context(), w, h)
    i18n.set_language("en")
    print("overlays desenham ok:", Null.calls, "primitivas")


def test_blind_spot_and_inputs():
    from lmuov.overlays.blind_spot import BlindSpotOverlay
    from lmuov.source_demo import DemoSource
    demo = DemoSource()
    tr = Trackers(None)
    demo.force_alongside(+1, -1.0)
    snap = demo.snapshot()
    near = BlindSpotOverlay().nearby(snap)
    side = [lx for v, lx, lz, f in near if abs(lz) < 5]
    assert side and all(lx > 2.5 for lx in side), near   # à esquerda (+x local)
    for _ in range(90):
        demo.step(1 / 30)
        ctx = tr.update(demo.snapshot(), now=demo.t)
    assert len(ctx.inputs) > 60 and 0 <= ctx.inputs[-1][1] <= 1
    p = demo.snapshot().player
    assert 1 <= p.gear <= 7 and 0 < p.rpm <= p.max_rpm
    print("radar e comandos ok")


def test_i18n():
    from lmuov import i18n
    for code, table in i18n.TABLES.items():
        extra = set(table) - set(i18n.EN)
        assert not extra, (code, extra)
        missing = set(i18n.EN) - set(table)
        print(f"{code}: {len(table)} textos, {len(missing)} em inglês por omissão")
    i18n.set_language("pt")
    assert i18n.tr("ov.standings") == "Classificação" and i18n.tr("left", t="12:00") == "12:00 restante"
    i18n.set_language("xx")
    assert i18n.tr("ov.standings") == "Standings"
    i18n.set_language("en")


def test_config_upgrade():
    import json
    from lmuov import config as C
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "config.json"
        p.write_text(json.dumps({"global": {"opacity": 0.8}, "overlays": {"tyres": {"enabled": True, "x": 5}}}))
        cfg = C.load(p)
        assert cfg["version"] == C.CONFIG_VERSION and cfg["global"]["opacity"] == 0.8
        assert cfg["overlays"]["tyres"]["enabled"] is False      # layout antigo é descartado
        cfg["overlays"]["delta"]["x"] = 123
        cfg["overlays"]["tower"]["fields"] = ["interval", "gap", "last"]     # defeito antigo
        C.save(p, cfg)
        new = C.load(p)
        assert new["overlays"]["delta"]["x"] == 123
        assert "team" in new["overlays"]["tower"]["fields"] and "team_radio" in new["overlays"]
    print("config ok")


def test_smart_visibility():
    """Modo auto: overlays aparecem/escondem-se sozinhos; espreitar mostra tudo; edição mostra tudo."""
    from lmuov.overlays import ALL, BY_KEY
    from lmuov.source_demo import DemoSource

    demo = DemoSource()
    tr = Trackers(None)
    ovs = [cls() for cls in ALL]
    seen = {o.key: set() for o in ovs}
    tower = next(o for o in ovs if o.key == "tower")
    sizes = set()
    for _ in range(2000):
        demo.step(0.2)
        s = demo.snapshot()
        ctx = tr.update(s, now=demo.t)
        for o in ovs:
            seen[o.key].add(o.visible(s, ctx))
        sizes.add(tower.size(s, ctx)[1])
    for key in ("delta", "fuel", "battle", "relative", "flags", "blind_spot"):
        assert seen[key] == {True, False}, (key, seen[key])     # aparece e desaparece
    assert seen["advanced"] == {True}                          # modo "sempre"
    assert len(sizes) >= 2, sizes                              # torre alterna entre mini e completa
    ctx.peek_until = ctx.now + 5
    assert all(o.visible(s, ctx) for o in ovs if not o.contextual)
    ctx.peek_until = 0
    ctx.edit_mode = True
    assert all(o.visible(s, ctx) for o in ovs)
    rel = BY_KEY["relative"]({"mode": "always"})
    ctx.edit_mode = False
    assert rel.visible(s, ctx)
    print("visibilidade automática ok")


def test_skins():
    """Todos os estilos desenham todos os overlays sem erros, com e sem dados."""
    from lmuov import skins, theme
    from lmuov.overlays import ALL
    from lmuov.source_demo import DemoSource
    from lmuov.trackers import Context

    class Null:
        def __getattr__(self, name):
            return lambda *a, **k: 10.0

    demo = DemoSource()
    tr = Trackers(None)
    s = demo.snapshot()
    ctx = tr.update(s, now=demo.t)
    ctx.peek_until = ctx.now + 5
    try:
        for key in skins.SKINS:
            skins.apply(key)
            assert theme.SKIN["key"] == key
            for over in (None, {"phase": 6, "yellow_state": 4}, {"flag": 6}):
                demo.override_flags = over
                snap = demo.snapshot()
                for cls in ALL:
                    ov = cls()
                    w, h = ov.size(snap, ctx)
                    ov.draw(Null(), snap, ctx, w, h)
                    ov.draw(Null(), None, Context(), *ov.size(None, Context()))
    finally:
        skins.apply("wec")
    assert theme.SKIN["key"] == "wec" and theme.ACCENT == (25, 195, 255, 255)
    print("estilos ok:", ", ".join(skins.names().values()))


def test_team_radio():
    """Cartão "BOX, BOX.": aparece quando pedes boxes e quando um rival perto de ti pede/entra."""
    from lmuov.overlays.team_radio import TeamRadioOverlay
    from lmuov.source_demo import DemoSource

    demo = DemoSource()
    tr = Trackers(None)
    mine = TeamRadioOverlay({"rivals": "off"})
    s = demo.snapshot()
    ctx = tr.update(s, now=demo.t)
    demo.override_me = {"pit_state": 0}
    demo.step(0.2)
    ctx = tr.update(demo.snapshot(), now=demo.t)
    assert not mine.has_content(demo.snapshot(), ctx)
    demo.override_me = {"pit_state": 1}
    demo.step(0.2)
    s = demo.snapshot()
    ctx = tr.update(s, now=demo.t)
    ev = mine.event(s, ctx)
    assert ev and ev[0].is_player and ev[1] == "req", ev
    demo.step(7.0)
    s = demo.snapshot()
    ctx = tr.update(s, now=demo.t)
    assert not mine.has_content(s, ctx)                 # só uns segundos
    demo.override_me = {}

    # por defeito: só o teu carro (pedido teu ou de um colega de equipa)
    rival0 = next(v for v in s.vehicles if v.cls == s.me.cls and abs(v.class_place - s.me.class_place) == 1)
    ctx.radio = [(ctx.now, rival0.id, "req")]
    assert TeamRadioOverlay().event(s, ctx) is None
    near = TeamRadioOverlay({"only_mine": False})
    rival = next(v for v in s.vehicles if v.cls == s.me.cls and abs(v.class_place - s.me.class_place) == 1)
    other = next(v for v in s.vehicles if v.cls != s.me.cls)
    ctx.radio = [(ctx.now, other.id, "in")]
    assert near.event(s, ctx) is None                   # outra classe: não interessa
    ctx.radio.append((ctx.now, rival.id, "req"))
    assert near.event(s, ctx)[0].id == rival.id
    assert TeamRadioOverlay({"rivals": "all", "only_mine": False}).event(s, ctx) is not None
    ctx.radio.append((ctx.now - 1, s.me.id, "req"))
    assert near.event(s, ctx)[0].is_player              # o teu pedido tem prioridade

    # na simulação, os outros carros pedem boxes e entram no pit lane
    kinds = set()
    for _ in range(3000):
        demo.step(0.25)
        ctx = tr.update(demo.snapshot(), now=demo.t)
        kinds |= {k for _t, vid, k in ctx.radio}
    assert {"req"} <= kinds, kinds
    print("team radio ok:", sorted(kinds))


def test_tower_screens():
    """Todos os ecrãs da torre (e o estilo WEC 2025) cabem no tamanho que a torre pede."""
    from lmuov import skins
    from lmuov.overlays.tower import FIELDS, TowerOverlay
    from lmuov.source_demo import DemoSource
    from lmuov import tv

    class BBox:
        def __init__(self):
            self.maxy = 0.0

        def rect(self, x, y, w, h, *a, **k):
            self.maxy = max(self.maxy, y + h)

        def text(self, x, y, w, h, *a, **k):
            self.maxy = max(self.maxy, y + h)

        def measure(self, s, size, weight=400, spacing=0.0):
            return len(s) * size * 0.52

        def __getattr__(self, name):
            return lambda *a, **k: None

    demo = DemoSource()
    tr = Trackers(None)
    for _ in range(300):
        demo.step(0.5)
        ctx = tr.update(demo.snapshot(), now=demo.t)
    try:
        for key in ("wec25", "wec", "aurora"):
            skins.apply(key)
            for kind in ("race", "qualy"):
                s = demo.snapshot()
                s.session.kind = kind
                for i in range(len(FIELDS) + 1):
                    ctx.focus_field = i
                    ctx.peek_until = ctx.now + 5 if i % 2 == 0 else 0     # completa e mini
                    t = TowerOverlay({"mode": "auto"})
                    w, h = t.size(s, ctx)
                    bb = BBox()
                    t.draw(bb, s, ctx, w, h)
                    assert bb.maxy <= h + 9.5, (key, kind, FIELDS[i - 1] if i else "auto", bb.maxy, h)
    finally:
        ctx.focus_field = 0
        skins.apply("wec")
    assert tv.driver_code("Ignazio Pérez") == "PER" and tv.driver_code("Antonio Fuoco") == "FUO"
    assert tv.team_name("Ferrari AF Corse 2024 #50:LM") == "FERRARI AF CORSE"
    assert tv.team_name("#007 Aston Martin Thor Team") == "ASTON MARTIN THOR TEAM"
    assert tv.brand_colors("Cadillac Hertz Team Jota #12")[0] == tv.BRAND_COLORS["CAD"][0]
    print("ecrãs da torre ok:", ", ".join(FIELDS))


def test_smooth_60fps():
    """60 fps: migração dos fps antigos, distância extrapolada entre leituras do scoring e
    cabeçalho dividido (fundo em cache + texto da direita) igual ao cabeçalho inteiro."""
    import json
    from lmuov import config as C
    from lmuov import skins, theme
    from lmuov.model import Player, Session, Snapshot, Vehicle

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "config.json"
        old = C.defaults()
        old["global"]["hz"] = 60
        old["global"].pop("fps_v")
        for k, v in C._OLD_FPS[2].items():
            old["overlays"][k]["fps"] = v
        old["overlays"]["fuel"]["fps"] = 7                       # escolhido à mão: fica
        p.write_text(json.dumps(old))
        cfg = C.load(p)
        g = cfg["global"]
        assert g["hz"] == 20 and g["perf"] == "balanced" and g["fps_v"] == C.FPS_VERSION
        assert cfg["overlays"]["delta"]["fps"] == 20 and cfg["overlays"]["tower"]["fps"] == 2
        assert cfg["overlays"]["inputs"]["fps"] == 15 and cfg["overlays"]["fuel"]["fps"] == 7
        cfg["global"]["hz"] = 60                                   # depois da migração, é escolha
        C.save(p, cfg)
        assert C.load(p)["global"]["hz"] == 60

    me = Vehicle(id=1, lap_dist=1000.0, is_player=True)
    s = Session(track_length=5000.0, current_et=100.0)
    pl = Player(speed=50.0, elapsed=100.2)
    snap = Snapshot(session=s, vehicles=[me], me=me, player=pl)
    assert abs(snap.my_lap_dist() - 1010.0) < 1e-6              # 0.2 s a 50 m/s
    pl.elapsed = 103.0
    assert abs(snap.my_lap_dist() - 1025.0) < 1e-6              # no máximo 0.5 s
    me.lap_dist, pl.elapsed = 4995.0, 100.2
    assert abs(snap.my_lap_dist() - 5.0) < 1e-6                 # passa a meta

    class Log:
        def __init__(self):
            self.ops = []

        def __getattr__(self, name):
            def f(*a, **k):
                self.ops.append((name, a, tuple(sorted(k.items()))))
            return f

        def measure(self, s, size, weight=400, spacing=0.0):
            return len(s) * size * 0.5

    try:
        for key in skins.SKINS:
            skins.apply(key)
            whole, split = Log(), Log()
            theme.panel(whole, 400, 90, "Delta", "PRED 1:44.048")
            theme.panel(split, 400, 90, "Delta", "PRED 1:44.048", part="bg")
            theme.panel(split, 400, 90, "Delta", "PRED 1:44.048", part="right")
            assert sorted(map(repr, whole.ops)) == sorted(map(repr, split.ops)), key
    finally:
        skins.apply("wec")
    print("60 fps ok: migração, extrapolação, cabeçalho em cache")


def test_iracing_yaml():
    from lmuov.source_iracing import parse_yaml, _num
    y = parse_yaml("""---
WeekendInfo:
 TrackDisplayName: Circuit de Spa-Francorchamps
 TrackLength: 6.93 km
 WeekendOptions:
  NumStarters: 40
SessionInfo:
 Sessions:
 - SessionNum: 0
   SessionType: Practice
   ResultsPositions:
 - SessionNum: 2
   SessionType: Race
   ResultsPositions:
   - Position: 1
     CarIdx: 7
   - Position: 2
     CarIdx: 3
DriverInfo:
 DriverCarIdx: 3
 Drivers:
 - CarIdx: 3
   UserName: Zé D'Almeida
   TeamName: Team: "Quoted"
   CarNumber: "007"
   CarClassColor: 0xff8000
 - CarIdx: 7
   UserName: Ana
...
""")
    assert _num(y["WeekendInfo"]["TrackLength"]) == 6.93 and y["WeekendInfo"]["WeekendOptions"]["NumStarters"] == "40"
    ss = y["SessionInfo"]["Sessions"]
    assert len(ss) == 2 and ss[0]["ResultsPositions"] == "" and ss[1]["ResultsPositions"][1]["CarIdx"] == "3"
    d = y["DriverInfo"]["Drivers"]
    assert d[0]["UserName"] == "Zé D'Almeida" and d[0]["TeamName"] == 'Team: "Quoted"' and d[0]["CarNumber"] == "007"
    assert _num(d[0]["CarClassColor"]) == 0xff8000 and d[1]["UserName"] == "Ana" and y["DriverInfo"]["DriverCarIdx"] == "3"
    print("yaml do iRacing ok")


def _iracing_run(seconds: float, session_type: str = "Race", step: float = 1 / 60, every=None):
    """Corre o demo, escreve a memória do iRacing a partir dele e lê-a com o leitor do iRacing."""
    from lmuov.source_demo import DemoSource
    from lmuov.source_iracing import IRacingSource, IRSDK
    sys.path.insert(0, str(ROOT / "tests"))
    from fake_iracing import FakeIRacing

    demo = DemoSource()
    fake = FakeIRacing(session_type)
    src = IRacingSource()
    tr = Trackers(None)
    out = None
    n = int(seconds / step)
    for k in range(n):
        demo.step(step)
        d = demo.snapshot()
        mem = fake.write(d)
        if src.sdk is None or src.sdk.mem is not mem:
            src.sdk = IRSDK(mem)
        snap = src.read_from(src.sdk)
        ctx = tr.update(snap, now=demo.t)
        if every:
            every(k, d, snap, ctx)
        out = (d, snap, ctx, src, fake, demo, tr)
    return out


def test_iracing_source():
    """O leitor do iRacing dá o mesmo que o jogo simulado: pilotos, classes, posições, boxes,
    bandeiras, radar (spotter), mapa (integrado a partir da velocidade) e todos os overlays."""
    from lmuov import i18n, skins, tv
    from lmuov.overlays import ALL
    from lmuov.overlays.blind_spot import BlindSpotOverlay
    from lmuov.trackers import Context

    d, snap, ctx, src, fake, demo, tr = _iracing_run(5.0)
    assert snap is not None and snap.source == "iracing" and not snap.world_pos
    assert src.status == ("ir_connected", d.session.track)
    assert snap.me.id == d.me.id + 1 and snap.me.driver == d.me.driver and snap.me.is_player
    assert len(snap.vehicles) == len(d.vehicles)                         # sem o carro de segurança
    by = {v.id - 1: v for v in snap.vehicles}
    for v in d.vehicles:
        w = by[v.id]
        assert w.place == v.place and w.class_place == v.class_place and w.number == v.number, (v, w)
        assert abs(w.lap_dist - v.lap_dist) < 10 and w.total_laps == v.total_laps
        assert w.in_pits == v.in_pits and tv.brand_code(w.vehicle_name) == tv.brand_code(v.vehicle_name)
    assert snap.session.kind == "race" and abs(snap.session.track_length - 5410) < 1
    assert any(v.team for v in snap.vehicles) and any(":" in v.team for v in snap.vehicles)
    gt = next(v for v in snap.vehicles if v.cls == "GT3")
    assert tv.T.class_info(gt.cls)[0] == "GT3"
    assert abs(snap.player.speed - d.player.speed) < 0.01 and snap.player.gear == d.player.gear
    assert abs(snap.player.steering - d.player.steering) < 1e-3 and abs(snap.player.clutch - d.player.clutch) < 1e-6
    sp = [v for v in snap.vehicles if v.speed > 0]
    assert len(sp) > len(snap.vehicles) / 2                               # velocidades estimadas

    # bandeiras e boxes
    demo.override_flags = {"phase": 6, "yellow_state": 4, "flag": 6}
    demo.override_me = {"in_pits": True, "pit_state": 3}
    dd = demo.snapshot()
    sn = src.read_from(src.sdk.__class__(fake.write(dd)))
    assert sn.session.phase == 6 and sn.session.yellow_state == 4 and sn.me.flag == 6
    assert sn.me.in_pits and sn.me.pit_state == 3
    demo.override_flags, demo.override_me = None, {}

    # radar: um carro ao lado aparece do lado certo
    demo.force_alongside(+1, -1.0)
    demo.step(0.02)
    dd = demo.snapshot()
    sn = src.read_from(src.sdk.__class__(fake.write(dd)))
    near = BlindSpotOverlay().nearby(sn)
    side = [lx for v, lx, lz, f in near if abs(lz) < 5]
    assert side and all(lx > 2.5 for lx in side), near

    # sem ligação
    fake.connected = False
    assert src.read_from(src.sdk.__class__(fake.write(dd))) is None and src.status[0] == "ir_not_running"
    fake.connected = True
    assert src.diag["aberto"] and src.diag["pilotos"] > 0 and src.diag["motivo"] == ""
    yaml_bak = fake._yaml
    fake._yaml = lambda s: "---\nWeekendInfo:\n TrackLength: 5.41 km\n...\n"
    assert src.read_from(src.sdk.__class__(fake.write(dd))) is None and src.status[0] == "ir_no_data"
    assert "pilotos" in src.status[1]
    fake._yaml = yaml_bak

    # todos os overlays, todos os estilos e línguas, com dados do iRacing
    class Null:
        def __getattr__(self, name):
            return lambda *a, **k: 10.0

    s = src.read_from(src.sdk.__class__(fake.write(demo.snapshot())))
    ctx = tr.update(s, now=demo.t)
    ctx.peek_until = ctx.now + 5
    ctx.radio = [(ctx.now - 1, s.me.id, "req")]
    try:
        for key in skins.SKINS:
            skins.apply(key)
            for lang in i18n.LANGS:
                i18n.set_language(lang)
                for cls in ALL:
                    ov = cls()
                    w, h = ov.size(s, ctx)
                    ov.draw(Null(), s, ctx, w, h)
                    ov.draw(Null(), None, Context(), *ov.size(None, Context()))
    finally:
        skins.apply("wec")
        i18n.set_language("en")
    print("iRacing ok:", len(snap.vehicles), "carros,", src.status[1])


def test_iracing_map_and_session_types():
    """Mapa do iRacing desenhado a partir da velocidade (fecha a volta) e tipos de sessão."""
    from lmuov.trackers import Trackers as _T
    d, snap, ctx, src, fake, demo, tr = _iracing_run(250.0, step=1 / 30)
    tm = ctx.track_map
    assert tm is not None and len(tm.pts) > 300, "mapa não gravado"
    (d0, x0, z0), (d1, x1, z1) = tm.pts[0], tm.pts[-1]
    assert math.hypot(x1 - x0, z1 - z0) < 60, (x0, z0, x1, z1)          # a volta fecha
    xs = [p[1] for p in tm.pts]
    zs = [p[2] for p in tm.pts]
    assert max(xs) - min(xs) > 300 and max(zs) - min(zs) > 300
    # forma: comparar com o mapa gravado pelo demo (posições reais)
    demo2 = __import__("lmuov.source_demo", fromlist=["DemoSource"]).DemoSource()
    tr2 = _T(None)
    for _ in range(int(250 * 30)):
        demo2.step(1 / 30)
        c2 = tr2.update(demo2.snapshot(), now=demo2.t)
    ref = c2.track_map
    rx = [p[1] for p in ref.pts]
    rz = [p[2] for p in ref.pts]
    aspect = (max(xs) - min(xs)) / (max(zs) - min(zs))
    raspect = (max(rx) - min(rx)) / (max(rz) - min(rz))
    assert abs(aspect - raspect) / raspect < 0.08, (aspect, raspect)

    from lmuov.overlays.track_map import TrackMapOverlay
    ov = TrackMapOverlay()
    ov.draw(CheckCanvas(), snap, ctx, 290, 290)

    for typ, kind in (("Open Qualify", "qualy"), ("Lone Qualify", "qualy"), ("Practice", "practice"),
                      ("Offline Testing", "test"), ("Warmup", "warmup")):
        _d, sn, *_ = _iracing_run(0.5, typ)
        assert sn.session.kind == kind, (typ, sn.session.kind)
    print("mapa do iRacing ok:", len(tm.pts), "pontos; proporção", round(aspect, 3), "vs", round(raspect, 3))


def test_new_overlays():
    """Track limits, danos, meteorologia (previsão em voltas), contador de voltas, temperaturas e volantes."""
    from lmuov.overlays import BY_KEY
    from lmuov.source_demo import DemoSource
    from lmuov.weathercalc import outlook
    from lmuov.wheels import STYLES, draw_wheel

    demo = DemoSource()
    tr = Trackers(None)
    tl = BY_KEY["track_limits"]()
    states = set()
    for _ in range(int(500 / 0.25)):
        demo.step(0.25)
        s = demo.snapshot()
        ctx = tr.update(s, now=demo.t)
        states.add(tl.state(s, ctx))
    assert {"hit", "clean", "ok"} <= states, states
    assert s.player.tl_limit == 5

    # meteorologia: antes da chuva (previsão do jogo), a chover e a secar (tendência)
    demo = DemoSource()
    tr = Trackers(None)

    def at(t):
        while demo.t < t:
            demo.step(2.0)
            tr.update(demo.snapshot(), now=demo.t)
        s = demo.snapshot()
        return s, tr.update(s, now=demo.t)
    s, ctx = at(1500)                        # o demo começa aos 23 min; chove a partir dos 30
    o = outlook(s, ctx)
    assert o.event == "rain" and o.source == "forecast" and 1.5 < o.eta_laps < 4.5, o
    s, ctx = at(2200)
    o = outlook(s, ctx)
    assert o.rain > 0.05 and o.state in ("wet", "soaked", "damp") and o.event == "dry" and o.source == "forecast", o
    s, ctx = at(2950)
    o = outlook(s, ctx)
    assert o.event == "dry" and o.source == "trend" and o.eta_laps > 0, o
    s.forecast = []
    s2, ctx2 = s, ctx
    assert outlook(s2, ctx2).event == "dry"
    dmg = BY_KEY["damage"]()
    from lmuov.overlays.damage import damage_level
    assert damage_level(s.player) == 2 and dmg.auto_visible(s, ctx)

    for key in ("track_limits", "damage", "weather", "lap_counter", "engine_temps"):
        ov = BY_KEY[key]({"mode": "always"})
        w, h = ov.size(s, ctx)
        ov.draw(CheckCanvas(), s, ctx, w, h)
    for st in STYLES:
        for ang in (-2.0, 0.0, 1.3):
            draw_wheel(CheckCanvas(), 40, 40, 22, ang, st)
        ov = BY_KEY["inputs"]({"wheel": st})
        ov.draw(CheckCanvas(), s, ctx, 450, 118)

    # iRacing: incidentes no lugar dos track limits
    d, snap, *_ = _iracing_run(0.5)
    assert snap.player.tl_kind == "inc" and snap.player.tl_limit == 17 and snap.player.tl_points >= 0
    print("novos overlays ok:", sorted(x for x in states if x))


def test_updater():
    """Atualizações: comparar versões, ler a release do GitHub, preparar o zip e o script de troca."""
    import zipfile
    from lmuov import updater as U
    assert U.is_newer("1.2.0", "1.1.9") and U.is_newer("v2.0", "1.9.9") and U.is_newer("1.10.0", "1.9.0")
    assert not U.is_newer("1.2.0", "1.2.0") and not U.is_newer("1.2", "1.2.0") and not U.is_newer("1.0.9", "1.1")
    rel = U.parse_release({"tag_name": "v1.3.0", "body": "novidades", "html_url": "https://x/r",
                           "assets": [{"name": "outro.txt"}, {"name": "LMU_Overlays_Windows.zip",
                                                              "browser_download_url": "https://x/z.zip", "size": 9}]})
    assert rel == {"version": "1.3.0", "notes": "novidades", "url": "https://x/z.zip", "size": 9, "page": "https://x/r"}
    assert U.parse_release({"tag_name": "v1", "assets": []}) is None
    assert U.parse_release({"tag_name": "v9", "prerelease": True, "assets": [{"name": "a_Windows.zip"}]}) is None
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        install = tmp / "instalado"
        install.mkdir()
        zp = tmp / "u.zip"
        with zipfile.ZipFile(zp, "w") as z:
            z.writestr("LMU Overlays/LMU Overlays.exe", b"MZ")
            z.writestr("LMU Overlays/_internal/x.dll", b"x")
        up = U.Updater("eu/repo", install)
        script = up.prepare(zp, tmp / "work")
        txt = script.read_text("cp1252")
        assert "robocopy" in txt and '"config.json"' in txt and '"data"' in txt and str(install) in txt
        assert (tmp / "work" / "novo" / "LMU Overlays" / "LMU Overlays.exe").exists()
        bad = tmp / "bad.zip"
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("../fora.txt", b"x")
        try:
            up.prepare(bad, tmp / "w2")
            raise AssertionError("zip malformado aceite")
        except ValueError:
            pass
    assert U.Updater("").state == "off"
    print("atualizações ok")


def test_lmu_rest_parsing():
    """API local do LMU: previsão do tempo (em %) e danos (aero, suspensão, travões)."""
    from lmuov.lmu_rest import parse_forecast, parse_wearables
    w = parse_wearables({"wearables": {"body": {"aero": 0.25, "bodywork": 0.1},
                                       "suspension": [0.0, 0.5, 0.1, 1.0], "brakes": [0.3, 0.3, 0.2, 0.2],
                                       "engine": 0.05}})
    assert w["aero"] == 0.25 and w["suspension"] == (0.0, 0.5, 0.1, 1.0) and w["brakes"][2] == 0.2
    assert w["extra"] == {"bodywork": 0.1, "engine": 0.05}
    assert parse_wearables({"x": 1}) is None and parse_wearables({"wearables": {}})["aero"] == -1.0
    data = {"RACE": {n: {"WNV_RAIN_CHANCE": {"currentValue": v}, "WNV_SKY": {"currentValue": 4}}
                     for n, v in (("START", 10), ("NODE_25", 60), ("NODE_50", 80), ("NODE_75", 30), ("FINISH", 0))}}
    f = parse_forecast(data, "race", 3600)
    assert [round(x[1], 2) for x in f] == [0.1, 0.6, 0.8, 0.3, 0.0] and f[2][0] == 1800
    assert parse_forecast(data, "warmup", 3600) == f
    # vento: o LMU deixa o mWind a zero, vem da previsão (m/s, direção de onde sopra 0=N..7=NW)
    from lmuov.lmu_rest import parse_wind, wind_vector
    from lmuov.overlays.wind import wind_relative
    wd = {"RACE": {"START": {"WNV_WINDSPEED": {"currentValue": 3.0}, "WNV_WINDDIRECTION": {"currentValue": 2}},
                   "NODE_50": {"WNV_WINDSPEED": {"currentValue": 6.0}, "WNV_WINDDIRECTION": {"currentValue": 0}}}}
    assert parse_wind(wd, "race", 0.2) == (3.0, 2.0) and parse_wind(wd, "race", 0.7) == (6.0, 0.0)
    assert parse_wind({"RACE": {"START": {}}}, "race", 0.5) is None
    north = [[-1, 0, 0], [0, 1, 0], [0, 0, -1]]               # carro virado a norte
    fwd, left = wind_relative(wind_vector(6.0, 0), north)      # vento de norte = de frente
    assert abs(fwd + 6.0) < 1e-6 and abs(left) < 1e-6
    print("API local do LMU ok")



def test_ratings_avg_tyres():
    """SR/DR (iRacing e LMU), média das últimas 5 voltas e cores fixas dos pneus."""
    from lmuov.source_iracing import ir_license, ir_rating
    from lmuov.lmu_rest import parse_ratings, fmt_rating
    from lmuov import tv, theme as T
    assert ir_license("A 4.32") == "A4.32" and ir_license("") == "" and ir_rating(2412) == "2.4k" and ir_rating(0) == ""
    assert tv.rating_color("A4.32") == tv.LICENSE_COLORS["A"] and tv.rating_color("GLD") == tv.TIER_COLORS["GLD"]
    assert tv.rating_color("") is None and tv.rating_color("2.4k") == tv.RATING_NEUTRAL
    r = parse_ratings([{"driverName": "Ana Silva", "safetyRating": "Silver", "driverRating": {"name": "Gold"},
                        "countryCode": "prt"}, {"driverName": "Sem Dados", "bestLapTime": 100}])
    assert r == {"Ana Silva": ("SLV", "GLD", "PRT")}, r
    assert parse_ratings({"standings": [{"driverName": "X", "DR": 1530}]}) == {"X": ("", "1.5k", "")}
    assert fmt_rating(None) == "" and fmt_rating(3.456) == "3.46"
    # média de 5 voltas: ignora a volta com boxes e guarda só as últimas 5
    from lmuov.trackers import LapAvgTracker
    from lmuov.model import Snapshot, Vehicle, Session, Player
    t = LapAvgTracker(5)
    v = Vehicle(id=1, total_laps=0)
    snap = Snapshot(session=Session(), vehicles=[v], me=v, player=Player())
    t.update(snap)
    for lap, (time_, pit) in enumerate([(100, False), (101, True), (102, False), (103, False), (104, False),
                                        (105, False), (106, False)], 1):
        v.in_pits = pit
        t.update(snap)
        v.in_pits = False
        v.total_laps, v.last = lap, time_
        t.update(snap)
    assert t.laps[1] == [102, 103, 104, 105, 106], t.laps[1]
    assert abs(t.avg[1] - 104.0) < 1e-9
    # pneus: até 50 azul, 51-60 verde claro, 61-75 verde, 76-85 amarelo, acima vermelho
    cols = [T.tyre_band_color(x) for x in (45, 50, 55, 70, 80, 95)]
    assert cols[0] == cols[1] and len({cols[1], cols[2], cols[3], cols[4], cols[5]}) == 5
    print("ratings / média 5 voltas / pneus ok")


def test_compact_columns():
    """Colunas do Relative/Standings compactos: ordem fixa, SR/DR só com dados, SOF do iRacing."""
    from lmuov.overlays import compact as K
    from lmuov.model import Vehicle
    from types import SimpleNamespace
    vs = [Vehicle(id=i, irating=1500) for i in range(10)]
    snap = SimpleNamespace(vehicles=vs)
    cols = K.columns({"columns": ["gap", "sr", "name", "pos", "tyre"]}, K.STANDINGS_COLS, K.STD_DEFAULT, snap)
    assert cols == ["pos", "name", "gap", "tyre"], cols            # sem SR no jogo: coluna escondida
    vs[0].sr = "A4.0"
    assert "sr" in K.columns({"columns": ["sr"]}, K.STANDINGS_COLS, K.STD_DEFAULT, snap)
    assert abs(K.sof(vs) - 1500) < 1 and K.sof([Vehicle()]) == 0
    assert "interval" not in K.columns({"columns": ["interval"]}, K.RELATIVE_COLS, K.REL_DEFAULT, snap)
    x = K.xs(["pos", "name", "gap"], 300)
    assert abs(x["gap"][0] + x["gap"][1] - 296) < 1e-6
    print("colunas compactas ok")


def test_relative_time_gap():
    """Gaps do relativo pela posição em tempo do jogo (como o HUD), com volta à meta."""
    from lmuov.relcalc import time_gap
    from lmuov.model import Vehicle
    me = Vehicle(time_into_lap=50.0)
    assert abs(time_gap(me, Vehicle(time_into_lap=52.3), 100, 5000, 100) - 2.3) < 1e-9     # à frente
    assert abs(time_gap(me, Vehicle(time_into_lap=48.1), -80, 5000, 100) + 1.9) < 1e-9     # atrás
    me2 = Vehicle(time_into_lap=99.0)                                                       # passa a meta
    assert abs(time_gap(me2, Vehicle(time_into_lap=1.5), 120, 5000, 100) - 2.5) < 1e-9
    assert abs(time_gap(me, Vehicle(time_into_lap=0.0), 500, 5000, 100) - 10.0) < 1e-9    # sem dados: distância
    print("gaps do relativo ok")


def test_map_from_all_cars_and_yellow():
    """Mapa feito com todos os carros (sem dar voltas) e amarela só no setor onde estás."""
    from lmuov.source_demo import DemoSource
    from lmuov.trackers import TrackMapRecorder
    from lmuov.flagcalc import active_flags
    demo = DemoSource()
    r = TrackMapRecorder(None)
    t = 0.0
    while r.map is None and t < 120:
        demo.step(0.2)
        t += 0.2
        r.update(demo.snapshot())
    assert r.map is not None, "mapa não ficou pronto"
    s = demo.snapshot()
    s.session.in_realtime = True
    s.me.in_pits = s.me.in_garage = False
    s.session.phase = 5
    s.session.sector_flags = tuple(1 if k == (s.me.sector + 1) % 3 else 0 for k in range(3))
    s.me.under_yellow = False
    assert not any(f.kind == "yellow" for f in active_flags(s, None))     # amarela só no setor seguinte: ainda não
    s.me.under_yellow = True
    assert any(f.kind == "yellow" for f in active_flags(s, None))         # o jogo mostra-te a amarela
    print(f"mapa com todos os carros em {t:.0f} s; amarelas ok")

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("TODOS OS TESTES PASSARAM")
