"""Previsão meteorológica do LMU pela API local do jogo (http://localhost:6397, a mesma que a
interface do jogo usa). Corre numa thread à parte, a cada 20 s, e nunca bloqueia os overlays.
Se a API não responder, simplesmente não há previsão (o overlay usa a tendência)."""

from __future__ import annotations

import json
import logging
import math
import threading
import time
import urllib.request

log = logging.getLogger("lmuov")
URL = "http://localhost:6397/rest/sessions/weather"
REPAIR_URL = "http://localhost:6397/rest/garage/UIScreen/RepairAndRefuel"
NODES = (("START", 0.0), ("NODE_25", 0.25), ("NODE_50", 0.5), ("NODE_75", 0.75), ("FINISH", 1.0))
SESSIONS = {"practice": ("PRACTICE",), "qualy": ("QUALIFY", "QUALIFYING"), "race": ("RACE",),
            "warmup": ("RACE",), "test": ("PRACTICE",)}


def _value(node: dict, *names):
    for n in names:
        v = node.get(n)
        if isinstance(v, dict):
            v = v.get("currentValue", v.get("value"))
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _session(data, kind: str):
    if not isinstance(data, dict):
        return None
    for name in SESSIONS.get(kind, ("RACE",)):
        sess = data.get(name) or data.get(name.lower())
        if isinstance(sess, dict):
            return sess
    return None


def wind_vector(speed: float, direction: float) -> tuple[float, float, float]:
    """Vento da API (velocidade em m/s, direção DE ONDE sopra: 0=N, 1=NE ... 7=NW) para o vetor do
    movimento do ar no mundo do jogo (x = este, z = norte), o mesmo formato do mWind."""
    a = math.radians(direction * 45.0)
    return (-speed * math.sin(a), 0.0, -speed * math.cos(a))


def parse_wind(data, kind: str, progress: float) -> tuple[float, float] | None:
    """(velocidade m/s, direção 0..7) do ponto da previsão em que a sessão está (progress 0..1).
    O LMU deixa o mWind da memória partilhada sempre a zero; esta é a única fonte do vento."""
    sess = _session(data, kind)
    if sess is None:
        return None
    best = None
    for key, frac in NODES:
        node = sess.get(key)
        if not isinstance(node, dict):
            continue
        spd = _value(node, "WNV_WINDSPEED", "windSpeed")
        if spd is None:
            continue
        d = _value(node, "WNV_WINDDIRECTION", "windDirection")
        if best is None or frac <= progress + 1e-9:
            best = (max(0.0, spd), (d or 0.0) % 8)
    return best


def parse_forecast(data, kind: str, length: float) -> list:
    """[(segundos desde o início da sessão, prob. chuva 0..1, céu 0..10)] para a sessão `kind`."""
    if not isinstance(data, dict) or length <= 0:
        return []
    sess = None
    for name in SESSIONS.get(kind, ("RACE",)):
        sess = data.get(name) or data.get(name.lower())
        if isinstance(sess, dict):
            break
    if not isinstance(sess, dict):
        return []
    out = []
    for key, frac in NODES:
        node = sess.get(key)
        if not isinstance(node, dict):
            continue
        ch = _value(node, "WNV_RAIN_CHANCE", "rainChance")
        sky = _value(node, "WNV_SKY", "sky")
        if ch is None and sky is None:
            continue
        ch = (ch or 0.0) / 100.0                         # a API dá a probabilidade em %
        out.append((frac * length, max(0.0, min(1.0, ch)), int(sky if sky is not None else -1)))
    return out


class WeatherFetcher:
    label = "meteorologia"
    retry = 60.0

    def __init__(self, url: str = URL, every: float = 20.0) -> None:
        self.url, self.every = url, every
        self.data = None
        self.ok = self.fail_streak = 0
        self.last_ok = 0.0
        self.last_error = ""
        self._stop = False
        self._thread = None
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # sem proxies: é local

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="lmu-weather", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop = True

    def _run(self) -> None:
        fails = 0
        while not self._stop:
            try:
                with self._opener.open(self.url, timeout=1.0) as r:
                    self.data = json.loads(r.read().decode("utf-8", errors="replace"))
                if fails >= 3:
                    log.info("API do LMU: %s voltou a responder", self.label)
                fails = 0
                self.ok += 1
                self.last_ok = time.time()
            except Exception as e:
                fails += 1
                self.last_error = f"{type(e).__name__}: {str(e)[:80]}"
                if fails == 3:
                    log.info("API do LMU: %s sem resposta (%s: %s) - volta a tentar a cada %.0f s",
                             self.label, type(e).__name__, str(e)[:80], self.retry)
            self.fail_streak = fails
            time.sleep(self.every if fails < 3 else self.retry)

    def status(self) -> dict:
        age = time.time() - self.last_ok if self.last_ok else None
        return {"respostas": self.ok, "falhas_seguidas": self.fail_streak,
                "ultima_resposta_s": None if age is None else round(age, 1), "ultimo_erro": self.last_error}

    def wind(self, kind: str, progress: float) -> tuple[float, float] | None:
        try:
            return parse_wind(self.data, kind, progress)
        except Exception:
            return None

    def forecast(self, kind: str, length: float) -> list:
        try:
            return parse_forecast(self.data, kind, length)
        except Exception:
            return []


def _wheels(v) -> tuple:
    if isinstance(v, list) and len(v) >= 4:
        return tuple(float(x) if isinstance(x, (int, float)) else -1.0 for x in v[:4])
    return (-1.0, -1.0, -1.0, -1.0)


def parse_wearables(data) -> dict | None:
    """Danos do ecrã de reparações do LMU: {"wearables": {"body": {"aero": 0..1}, "suspension": [4],
    "brakes": [4], ...}}. Outras peças numéricas que apareçam também são guardadas."""
    if not isinstance(data, dict):
        return None
    w = data.get("wearables")
    if not isinstance(w, dict):
        return None
    body = w.get("body") if isinstance(w.get("body"), dict) else {}
    aero = body.get("aero")
    extra = {}
    for k, v in list(body.items()) + [(k, v) for k, v in w.items() if k not in ("body", "suspension", "brakes")]:
        if k != "aero" and isinstance(v, (int, float)) and not isinstance(v, bool):
            extra[str(k)] = float(v)
    return {"aero": float(aero) if isinstance(aero, (int, float)) else -1.0,
            "suspension": _wheels(w.get("suspension")), "brakes": _wheels(w.get("brakes")), "extra": extra}


class RepairFetcher(WeatherFetcher):
    """Danos (aero, suspensão por roda, travões) a cada 2 s."""

    label = "danos/reparações"
    retry = 10.0

    def __init__(self) -> None:
        super().__init__(REPAIR_URL, every=2.0)

    def wearables(self) -> dict | None:
        try:
            return parse_wearables(self.data)
        except Exception:
            return None


# ---- ratings (SR / DR) -------------------------------------------------------------- #
STANDINGS_URL = "http://localhost:6397/rest/watch/standings"
TIERS = {"bronze": "BRZ", "silver": "SLV", "gold": "GLD", "platinum": "PLT", "diamond": "DIA", "rookie": "ROO"}


def fmt_rating(v) -> str:
    """Valor de rating da API (texto do nível, número ou {name/value}) para algo curto."""
    if isinstance(v, dict):
        for k in ("name", "tier", "label", "value", "rating"):
            if k in v:
                return fmt_rating(v[k])
        return ""
    if isinstance(v, bool) or v is None:
        return ""
    if isinstance(v, (int, float)):
        if v <= 0:
            return ""
        return f"{v / 1000:.1f}k" if v >= 1000 else (f"{v:.2f}" if v < 10 else f"{v:.0f}")
    s = str(v).strip()
    if not s:
        return ""
    low = s.lower()
    for k, short in TIERS.items():
        if k in low:
            digit = next((ch for ch in s if ch in "123"), "")
            return (short[0] + digit) if digit else short      # "Silver 3" -> "S3"
    return s[:5].upper()


def _cars(data) -> list:
    if isinstance(data, list):
        return [c for c in data if isinstance(c, dict)]
    if isinstance(data, dict):
        for k in ("standings", "vehicles", "cars", "drivers"):
            if isinstance(data.get(k), list):
                return [c for c in data[k] if isinstance(c, dict)]
    return []


def parse_ratings(data) -> dict:
    """{nome do piloto: (sr, dr, país)} a partir de /rest/watch/standings. Os nomes dos campos não estão
    documentados, por isso procura qualquer campo com "safety" (SR) ou "rating" (DR)."""
    out = {}
    for car in _cars(data):
        name = car.get("driverName") or car.get("driver") or car.get("name")
        if not isinstance(name, str) or not name:
            continue
        sr = dr = country = ""
        pct = -1.0
        for k, v in car.items():
            low = k.lower().replace("_", "")
            if ("progress" in low or "percent" in low) and isinstance(v, (int, float)) and not isinstance(v, bool):
                pct = v / 100.0 if v > 1 else float(v)
                continue
            if low in ("country", "countrycode", "nationality", "nation") and isinstance(v, str):
                country = v.strip()[:3].upper()
            elif "safety" in low or low in ("sr", "safetyrating"):
                sr = sr or fmt_rating(v)
            elif "rating" in low or low in ("dr", "driverrating"):
                dr = dr or fmt_rating(v)
        if sr or dr or country:
            out[name.strip()] = (sr, dr, country, pct)
    return out


class StandingsFetcher(WeatherFetcher):
    """Classificação da API do LMU, só para os ratings (a cada 5 s)."""
    label = "ratings"
    retry = 30.0

    def __init__(self) -> None:
        super().__init__(STANDINGS_URL, every=5.0)

    def ratings(self) -> dict:
        try:
            return parse_ratings(self.data)
        except Exception:
            return {}

    def keys(self) -> list:
        """Campos que a API devolve por carro (vai para o diagnóstico, para afinar os ratings)."""
        cars = _cars(self.data)
        return sorted(cars[0].keys()) if cars else []


# ---- estimativa da paragem (tempo de reparação) ------------------------------------------- #
PIT_URL = "http://localhost:6397/rest/strategy/pitstop-estimate"


def parse_pit_estimate(data) -> dict:
    """{"total": s, "damage": s, ...} do jogo -> {"total": s, "repair": s}. Valores em falta = -1."""
    out = {"total": -1.0, "repair": -1.0}
    if not isinstance(data, dict):
        return out
    for key, name in (("total", "total"), ("damage", "repair")):
        v = data.get(key)
        if isinstance(v, dict):
            v = v.get("value", v.get("time"))
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0:
            out[name] = float(v)
    return out


class PitEstimateFetcher(WeatherFetcher):
    """Tempo de reparação e da paragem que o próprio LMU estima (o mesmo do menu das boxes), a cada 1 s."""
    label = "estimativa da paragem"
    retry = 10.0

    def __init__(self) -> None:
        super().__init__(PIT_URL, every=1.0)

    def estimate(self) -> dict:
        try:
            return parse_pit_estimate(self.data)
        except Exception:
            return {"total": -1.0, "repair": -1.0}
