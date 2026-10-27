"""Driver Rating e Safety Rating do LMU.

O LMU não põe os ratings na memória partilhada nem na sua API local. Eles vêm do serviço de
ratings do jogo (raceos.gg), o mesmo que outras ferramentas de overlays do LMU usam:

  1. o LMU (a correr, com sessão iniciada no Steam) dá um "bilhete" de sessão:
       GET http://localhost:6397/rest/profile/getAuthSessionTicket
  2. troca-se esse bilhete por um acesso temporário:
       POST https://raceos.gg/authenticate  {"token": bilhete, "game": "lmu", "platform": "steam"}
  3. pedem-se os ratings dos pilotos da grelha, pelo nome (até 50 por pedido):
       POST https://raceos.gg/api/v1/players  {"usernames": [...]}  (cabeçalho Game-Authorization)

Cada registo traz driverRank {rank, tier, progress}, safetyRank {...} e profile.nationality.
Tudo corre numa thread à parte; se falhar, os overlays simplesmente não mostram ratings.
Os resultados ficam em cache (30 min) e guardados em data/ratings.json.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
from pathlib import Path

log = logging.getLogger("lmuov")

TICKET_URL = "http://localhost:6397/rest/profile/getAuthSessionTicket"
AUTH_URL = "https://raceos.gg/authenticate"
PLAYERS_URL = "https://raceos.gg/api/v1/players"
RANKS = ("Bronze", "Silver", "Gold", "Platinum")
LETTER = {"Bronze": "B", "Silver": "S", "Gold": "G", "Platinum": "P", "Pro": "PRO"}
BATCH = 50
TTL = 30 * 60
MISS_TTL = 10 * 60


def _rank(block) -> tuple[str, float]:
    """{"rank": "Silver", "tier": 2, "progress": 70} -> ("S2", 0.70). Desconhecido -> ("", -1)."""
    if not isinstance(block, dict):
        return "", -1.0
    rank = block.get("rank")
    if rank == "Pro":
        return "PRO", -1.0
    if rank not in RANKS:
        return "", -1.0
    tier = block.get("tier")
    code = LETTER[rank] + (str(int(tier)) if isinstance(tier, (int, float)) and not isinstance(tier, bool)
                           and tier > 0 else "")
    prog = block.get("progress")
    pct = max(0.0, min(1.0, float(prog) / 100.0)) if isinstance(prog, (int, float)) and not isinstance(prog, bool) else -1.0
    return code, pct


def parse_players(payload) -> dict:
    """Resposta do serviço -> {nome: {"dr", "dr_pct", "sr", "sr_pct", "country"}}."""
    if isinstance(payload, dict):
        payload = payload.get("players") or payload.get("data")
    out = {}
    if not isinstance(payload, list):
        return out
    for rec in payload:
        if not isinstance(rec, dict):
            continue
        name = rec.get("username") or rec.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        dr, dr_pct = _rank(rec.get("driverRank"))
        sr, sr_pct = _rank(rec.get("safetyRank"))
        prof = rec.get("profile") if isinstance(rec.get("profile"), dict) else {}
        nat = prof.get("nationality")
        country = nat.strip().upper()[:3] if isinstance(nat, str) else ""
        if dr or sr or country:
            out[name.strip()] = {"dr": dr, "dr_pct": dr_pct, "sr": sr, "sr_pct": sr_pct, "country": country}
    return out


def parse_ticket(body: str) -> str:
    """O LMU responde com o bilhete entre aspas, num objeto, ou em texto simples."""
    body = (body or "").strip()
    if not body:
        return ""
    try:
        data = json.loads(body)
    except ValueError:
        return body if " " not in body and "<" not in body else ""
    if isinstance(data, str):
        return data.strip()
    if isinstance(data, dict):
        for k in ("ticket", "authSessionTicket", "token"):
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""


def rating_value(code: str, pct: float) -> float | None:
    """Nível como número contínuo (Bronze 1 = 0 ... Platinum 3 = 11, + progresso), para as variações."""
    if not code or code == "PRO" or code[0] not in "BSGP":
        return None
    tier = int(code[1:]) if code[1:].isdigit() else 1
    return "BSGP".index(code[0]) * 3 + (tier - 1) + max(0.0, pct)


class RatingsService:
    def __init__(self, store: Path | None = None) -> None:
        self.store = store
        self.cache: dict[str, tuple[float, dict | None]] = {}     # nome -> (instante, rating ou None = não existe)
        self.wanted: set[str] = set()
        self.token = ""
        self.token_until = 0.0
        self.not_before = 0.0
        self.backoff = 30.0
        self.status = "à espera"
        self.found = 0
        self._lock = threading.Lock()
        self._thread = None
        self._stop = False
        self._local = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self._load()

    # ---- cache em disco ---------------------------------------------------------------- #
    def _load(self) -> None:
        try:
            data = json.loads(self.store.read_text("utf-8")) if self.store else {}
            now = time.time()
            for name, (t, r) in data.items():
                if now - t < TTL:
                    self.cache[name] = (t, r)
        except Exception:
            pass

    def _save(self) -> None:
        if not self.store:
            return
        try:
            self.store.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                data = dict(self.cache)
            self.store.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        except Exception:
            pass

    # ---- usado pela app ------------------------------------------------------------------ #
    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="lmu-ratings", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop = True

    def request(self, names) -> None:
        with self._lock:
            self.wanted = {n.strip() for n in names if n and n.strip()}

    def get(self, name: str) -> dict | None:
        hit = self.cache.get(name.strip())
        return hit[1] if hit else None

    # ---- thread -------------------------------------------------------------------------- #
    def _due(self) -> list[str]:
        now = time.time()
        with self._lock:
            return [n for n in self.wanted
                    if n not in self.cache or now - self.cache[n][0] > (TTL if self.cache[n][1] else MISS_TTL)]

    def _fail(self, what: str) -> None:
        self.status = what
        self.not_before = time.time() + self.backoff
        log.info("ratings: %s; nova tentativa em %.0f s", what, self.backoff)
        self.backoff = min(self.backoff * 2, 15 * 60)

    def _post(self, url: str, body: dict, headers: dict | None = None):
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", **(headers or {})})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))

    def _auth(self) -> bool:
        if self.token and time.time() < self.token_until - 60:
            return True
        try:
            with self._local.open(TICKET_URL, timeout=2) as r:
                ticket = parse_ticket(r.read().decode("utf-8", errors="replace"))
        except Exception as e:
            self._fail(f"o LMU não deu o bilhete do Steam ({type(e).__name__})")
            return False
        if not ticket:
            self._fail("o LMU não tem sessão iniciada no Steam")
            return False
        try:
            data = self._post(AUTH_URL, {"token": ticket, "game": "lmu", "platform": "steam"})
        except Exception as e:
            self._fail(f"o serviço de ratings recusou o acesso ({type(e).__name__})")
            return False
        tok = data.get("accessToken") if isinstance(data, dict) else None
        if not isinstance(tok, str) or not tok:
            self._fail("o serviço de ratings não deu acesso")
            return False
        self.token = tok
        self.token_until = time.time() + 25 * 60          # o serviço dá ~30 min
        return True

    def _run(self) -> None:
        while not self._stop:
            time.sleep(2.0)
            due = self._due()
            if not due or time.time() < self.not_before or not self._auth():
                continue
            changed = False
            for i in range(0, len(due), BATCH):
                batch = due[i:i + BATCH]
                try:
                    res = parse_players(self._post(PLAYERS_URL, {"usernames": batch},
                                                   {"Game-Authorization": self.token}))
                except Exception as e:
                    if "401" in str(e) or "403" in str(e):
                        self.token = ""
                    self._fail(f"falhou o pedido dos ratings ({type(e).__name__})")
                    break
                low = {k.lower(): v for k, v in res.items()}
                now = time.time()
                with self._lock:
                    for name in batch:
                        self.cache[name] = (now, res.get(name) or low.get(name.lower()))
                changed = True
                self.backoff = 30.0
                self.status = "ok"
            if changed:
                self.found = sum(1 for _t, r in self.cache.values() if r)
                self._save()
