"""Previsão de chuva/seco em voltas (para o overlay Weather).

1) Previsão do jogo, quando existe (LMU: a meteorologia da sessão em 5 pontos: início, 25%, 50%,
   75% e fim). 2) Senão, tendência: como a chuva e a água na pista mudaram nos últimos minutos,
   prolongada até passar o limite. Os dois dão uma estimativa em voltas, com a origem indicada.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .relcalc import ref_lap

RAIN_ON = 0.05        # chuva a partir daqui conta como "a chover"
WET = 0.15            # água na pista a partir daqui = molhado (pneus de chuva)
DRY = 0.05            # abaixo disto = seco


@dataclass
class Outlook:
    rain: float = 0.0
    water: float = 0.0
    water_min: float = 0.0
    water_max: float = 0.0
    sky: int = -1
    state: str = "dry"            # dry, damp, wet, soaked
    trend_rain: float = 0.0       # por minuto
    trend_water: float = 0.0      # por minuto
    event: str = ""               # "rain" (vai chover) ou "dry" (vai secar) ou "" (estável)
    eta_laps: float | None = None
    source: str = ""              # "forecast" ou "trend"
    nodes: list = field(default_factory=list)   # [(voltas a partir de agora, prob. chuva, céu)]


def _slope(hist, idx: int, window: float = 180.0) -> float:
    """Variação por minuto (regressão linear) nos últimos `window` segundos."""
    if len(hist) < 4:
        return 0.0
    t_end = hist[-1][0]
    pts = [(t, h[idx]) for h in hist if (t := h[0]) >= t_end - window]
    if len(pts) < 4:
        return 0.0
    n = len(pts)
    mt = sum(p[0] for p in pts) / n
    mv = sum(p[1] for p in pts) / n
    den = sum((p[0] - mt) ** 2 for p in pts)
    if den <= 0:
        return 0.0
    return 60.0 * sum((p[0] - mt) * (p[1] - mv) for p in pts) / den


def state_of(water: float) -> str:
    if water < DRY:
        return "dry"
    if water < WET:
        return "damp"
    if water < 0.45:
        return "wet"
    return "soaked"


def outlook(snap, ctx) -> Outlook:
    s = snap.session
    o = Outlook(rain=s.rain, water=s.wetness, water_min=s.wetness_min, water_max=s.wetness_max, sky=s.sky,
                state=state_of(s.wetness))
    hist = getattr(ctx, "weather", None) or []
    o.trend_rain = _slope(hist, 1)
    o.trend_water = _slope(hist, 2)
    lap = max(30.0, ref_lap(snap))
    now = s.current_et
    left = s.time_left
    future = [(t, ch, sky) for t, ch, sky in (s.forecast or []) if t > now]
    o.nodes = [((t - now) / lap, ch, sky) for t, ch, sky in future]
    raining = s.rain >= RAIN_ON
    wet = s.wetness >= WET

    def ok(secs):
        return secs is not None and secs >= 0 and (left is None or secs <= left + 60) and secs / lap < 99

    if not raining and not wet:
        hit = next((t for t, ch, sky in future if ch >= 0.5 or sky >= 5), None)
        if hit is not None and ok(hit - now):
            o.event, o.eta_laps, o.source = "rain", (hit - now) / lap, "forecast"
        elif o.trend_rain > 0.004:
            secs = (RAIN_ON - s.rain) / o.trend_rain * 60.0
            if ok(secs):
                o.event, o.eta_laps, o.source = "rain", secs / lap, "trend"
    else:
        hit = next((t for t, ch, sky in future if ch < 0.3 and sky < 5), None) if raining else None
        if hit is not None and ok(hit - now):
            o.event, o.eta_laps, o.source = "dry", (hit - now) / lap, "forecast"
        elif o.trend_water < -0.002 and not raining:
            secs = (s.wetness - DRY) / -o.trend_water * 60.0
            if ok(secs):
                o.event, o.eta_laps, o.source = "dry", secs / lap, "trend"
    return o
