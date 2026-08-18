"""OpenRouter-Client mit Multi-Key-Fallback.

Mehrere API-Keys hinterlegen und das Budget bündeln: läuft ein Key auf **402 (Guthaben leer)**,
mustert der Client ihn (prozessweit) aus und rotiert automatisch zum nächsten. Rate-Limit (429)
→ kurzer Backoff, dann nächster Key.

Keys werden in dieser Priorität geladen (erste Fundstelle je Key gewinnt, Duplikate raus):
  1. Env  ``OPENROUTER_KEYS``            — Komma-getrennt
  2. Datei ``.secrets/openrouter.keys``  — ein Key je Zeile (``#``-Kommentare erlaubt)
  3. Datei ``.secrets/openrouter.key``   — einzelner Key (Abwärtskompatibilität)
Alle Dateien liegen unter ``.secrets/`` (gitignored). Nutzung:

    from govisor.llm import chat
    text = chat([{"role": "user", "content": "hallo"}], model="google/gemini-2.5-flash")
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import requests

URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("OR_MODEL", "google/gemini-2.5-flash")
_SECRETS = Path(os.environ.get("GOVISOR_SECRETS", ".secrets"))

# ── ZWEITER ANBIETER: CEREBRAS ───────────────────────────────────────────────────────
#
# Am 2026-08-18 lief das OpenRouter-Guthaben mitten im Rueckstau-Abbau leer: 526 Analysen,
# dann 402 bei jedem Aufruf. Der Arbeiter drehte weiter Runden, ohne dass etwas passierte.
# Ein zweiter Anbieter ist deshalb keine Bequemlichkeit, sondern die Sicherung dagegen, dass
# ein leeres Konto die ganze Kette anhaelt.
#
# Cerebras spricht die OpenAI-Schnittstelle, hat aber EIGENE Modellnamen — „google/
# gemini-2.5-flash" gibt es dort nicht. Deshalb traegt jeder Anbieter sein eigenes
# Standardmodell; ein von aussen gesetztes Modell gilt nur fuer den Anbieter, zu dem es passt
# (erkennbar am Schraegstrich in OpenRouter-Namen).
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
CEREBRAS_MODEL = os.environ.get("CEREBRAS_MODEL", "gpt-oss-120b")
TOGETHER_URL = "https://api.together.xyz/v1/chat/completions"
TOGETHER_MODEL = os.environ.get("TOGETHER_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
SAMBANOVA_URL = "https://api.sambanova.ai/v1/chat/completions"
# DeepSeek-V3.1 statt gpt-oss-120b: gemessen findet gpt-oss rund ein Drittel weniger
# Pruefpunkte als Gemini (34 statt 53) und verwirft mehr Zitate (19 % statt 11 %). Ein
# groesseres Modell ist hier die naheliegende Wahl, solange Guthaben da ist.
# Gemessen am 2026-08-18 an derselben Frage: gpt-oss-120b 1,1 s · Llama-3.3-70B 2,0 s ·
# DeepSeek-V3.2 lief nach 180 s in den Timeout, DeepSeek-V3.1 brauchte 78 s. Die grossen
# DeepSeek-Modelle sind dort also unbrauchbar langsam — nicht falsch, nur nicht benutzbar,
# wenn 4.500 Vorgaenge warten.
SAMBANOVA_MODEL = os.environ.get("SAMBANOVA_MODEL", "Meta-Llama-3.3-70B-Instruct")
XAI_URL = "https://api.x.ai/v1/chat/completions"
# Gemessen 2026-08-18: grok-4-fast-non-reasoning 0,9 s, grok-3-mini 8,7 s. Bei 4.300
# wartenden Vorgaengen entscheidet die Antwortzeit ueber Stunden, nicht ueber Sekunden.
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4-fast-non-reasoning")
_LOCK = threading.Lock()
_EXHAUSTED: set[str] = set()   # Keys ohne Guthaben (402), prozessweit gemerkt
# Wer hat zuletzt geantwortet? JE FADEN, nicht global: der Analyse-Lauf schickt 40 Anfragen
# gleichzeitig, und eine gemeinsame Variable wuerde die Herkunft der Ergebnisse vertauschen.
# Ohne diese Angabe steht im Ergebnis nicht, welches Modell es erzeugt hat — und dann laesst
# sich spaeter nicht mehr sagen, warum ein Bestand anders aussieht als der daneben.
_LETZTER = threading.local()


def _load_keys() -> list[str]:
    keys: list[str] = []
    env = os.environ.get("OPENROUTER_KEYS")
    if env:
        keys += [k.strip() for k in env.split(",") if k.strip()]
    for name in ("openrouter.keys", "openrouter.key"):
        p = _SECRETS / name
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                k = line.strip()
                if k and not k.startswith("#") and k not in keys:
                    keys.append(k)
    return keys


def _load_keys_aus(anbieter: str) -> list[str]:
    """Keys eines Anbieters: erst Umgebung, dann `.secrets/<anbieter>.keys|.key`."""
    keys: list[str] = []
    env = os.environ.get(f"{anbieter.upper()}_KEYS")
    if env:
        keys += [k.strip() for k in env.split(",") if k.strip()]
    for name in (f"{anbieter}.keys", f"{anbieter}.key"):
        p = _SECRETS / name
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                k = line.strip()
                if k and not k.startswith("#") and k not in keys:
                    keys.append(k)
    return keys


def _load_cerebras_keys() -> list[str]:
    return _load_keys_aus("cerebras")


def _anbieter() -> list[dict]:
    """Anbieter in der Reihenfolge, in der sie versucht werden.

    OpenRouter zuerst, weil dort die Modellauswahl breiter ist und die bisherigen Analysen
    damit entstanden sind — ein Modellwechsel mitten im Bestand macht die Ergebnisse
    untereinander unvergleichbar. Cerebras ist der Auffangnetz-Anbieter.
    """
    return [
        {"name": "openrouter", "url": URL, "keys": _load_keys(), "model": DEFAULT_MODEL},
        {"name": "cerebras", "url": CEREBRAS_URL, "keys": _load_cerebras_keys(),
         "model": CEREBRAS_MODEL},
        {"name": "together", "url": TOGETHER_URL, "keys": _load_keys_aus("together"),
         "model": TOGETHER_MODEL},
        {"name": "sambanova", "url": SAMBANOVA_URL, "keys": _load_keys_aus("sambanova"),
         "model": SAMBANOVA_MODEL},
        {"name": "xai", "url": XAI_URL, "keys": _load_keys_aus("xai"), "model": XAI_MODEL},
    ]
    # ⚠ PERPLEXITY IST BEWUSST NICHT DABEI, obwohl ein Schluessel mit Guthaben vorliegt
    # (.secrets/perplexity.key, geprueft am 2026-08-18: antwortet in 1,9 s).
    #
    # Die `sonar`-Modelle dort SUCHEN im Web und mischen Gefundenes in die Antwort. Fuer
    # diese Aufgabe ist das genau falsch: die Vergabe-Analyse unterliegt der Belegpflicht,
    # jede Aussage muss ein woertliches Zitat AUS DEM DOKUMENT tragen (govisor/docextract.py,
    # §6a.2). Ein Modell, das nebenbei das Internet befragt, erzeugt Saetze, die stimmen
    # koennen und trotzdem nicht im Dokument stehen — und die Zitatpruefung verwirft sie,
    # nachdem wir dafuer bezahlt haben. Fuer Recherche-Aufgaben ist der Schluessel gut;
    # hier nicht.


def available_keys() -> int:
    """Anzahl konfigurierter Keys ueber ALLE Anbieter, die (noch) nicht leer sind."""
    return sum(1 for a in _anbieter() for k in a["keys"] if k not in _EXHAUSTED)


def letzter_anbieter() -> tuple[str | None, str | None]:
    """(Anbieter, Modell) des letzten erfolgreichen Aufrufs IN DIESEM FADEN."""
    return getattr(_LETZTER, "anbieter", None), getattr(_LETZTER, "modell", None)


def anbieter_stand() -> list[dict]:
    """Wer koennte gerade liefern? Fuer Betriebsanzeigen (s. /api/intern/lauf)."""
    return [{"name": a["name"], "modell": a["model"],
             "keys": len(a["keys"]),
             "frei": sum(1 for k in a["keys"] if k not in _EXHAUSTED)}
            for a in _anbieter()]


def _is_credit_error(status: int, text: str) -> bool:
    if status == 402:
        return True
    t = (text or "").lower()
    return status in (400, 403) and any(w in t for w in ("credit", "insufficient", "quota", "balance"))


class AllKeysExhausted(RuntimeError):
    pass


def chat(messages: list[dict], model: str | None = None, temperature: float = 0,
         timeout: int = 120, max_retries: int = 3) -> str:
    """Chat-Completion mit Key- UND Anbieter-Rotation. Wirft erst, wenn niemand mehr kann.

    Reihenfolge: alle Keys des ersten Anbieters, dann der naechste Anbieter. Leeres Guthaben
    (402) mustert den Key prozessweit aus, 429 fuehrt zu kurzem Backoff und Wiederholung.

    `model` gilt nur fuer den passenden Anbieter: ein Name mit Schraegstrich („google/…")
    ist ein OpenRouter-Name und waere bei Cerebras ein Fehler. Ohne Angabe nimmt jeder
    Anbieter sein eigenes Standardmodell.
    """
    versuchte = 0
    last_err = "?"
    for anb in _anbieter():
        keys = [k for k in anb["keys"] if k not in _EXHAUSTED]
        if not keys:
            continue
        # ⚠ EIN MODELLNAME GILT NUR BEI SEINEM ANBIETER. Der erste Entwurf riet am
        # Schraegstrich („google/…" = OpenRouter) — das faellt spaetestens bei Together auf
        # die Nase, dessen Namen genauso aussehen („meta-llama/Llama-3.3-70B-Instruct-Turbo").
        # Ein von aussen gesetztes Modell (OR_MODEL) meint immer OpenRouter; die anderen
        # Anbieter nehmen ihr eigenes, sonst antwortet die Gegenstelle mit „model not found".
        modell = model if (model and anb["name"] == "openrouter") else anb["model"]
        body = {"model": modell, "temperature": temperature, "messages": messages}
        for key in keys:
            versuchte += 1
            for attempt in range(max_retries):
                try:
                    r = requests.post(anb["url"], headers={"Authorization": f"Bearer {key}",
                                      "Content-Type": "application/json"}, json=body, timeout=timeout)
                    if r.status_code == 200:
                        # ⚠ NICHT BLIND `["content"]`. Cerebras' gpt-oss-120b liefert
                        # `{"role","content","reasoning"}` und laesst `content` gelegentlich
                        # leer, wenn die Antwort im Denkteil steht. Gemessen am 2026-08-18:
                        # 2 von 5 Vorgaengen starben an `KeyError: 'content'` — und weil der
                        # Fehler wie ein Netzfehler aussah, wanderte der Lauf durch alle Keys
                        # und meldete am Ende „alle Anbieter erschoepft". Ein Formatunterschied
                        # als Guthabenproblem verkleidet: die teuerste Sorte Fehlermeldung.
                        m = (r.json().get("choices") or [{}])[0].get("message") or {}
                        inhalt = m.get("content") or m.get("reasoning") or ""
                        if inhalt.strip():
                            _LETZTER.anbieter = anb["name"]
                            _LETZTER.modell = modell
                            return inhalt
                        last_err = f"leere Antwort ({anb['name']})"
                        continue
                    if _is_credit_error(r.status_code, r.text):
                        with _LOCK:
                            _EXHAUSTED.add(key)
                        last_err = f"402/Guthaben leer ({anb['name']}, …{key[-6:]})"
                        break                       # dieser Key ist durch → naechster Key
                    if r.status_code == 429:
                        last_err = f"429 Rate-Limit ({anb['name']})"
                        time.sleep(2 * (attempt + 1))
                        continue
                    last_err = f"HTTP {r.status_code} ({anb['name']}): {r.text[:120]}"
                except Exception as e:              # Netz/Timeout → Retry
                    last_err = f"{type(e).__name__}: {str(e)[:80]}"
                    time.sleep(2 * (attempt + 1))
    raise AllKeysExhausted(f"Alle {versuchte} Keys ueber alle Anbieter fehlgeschlagen — "
                           f"zuletzt: {last_err}")
