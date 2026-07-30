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
_LOCK = threading.Lock()
_EXHAUSTED: set[str] = set()   # Keys ohne Guthaben (402), prozessweit gemerkt


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


def available_keys() -> int:
    """Anzahl konfigurierter Keys, die (noch) nicht als leer markiert sind."""
    return sum(1 for k in _load_keys() if k not in _EXHAUSTED)


def _is_credit_error(status: int, text: str) -> bool:
    if status == 402:
        return True
    t = (text or "").lower()
    return status in (400, 403) and any(w in t for w in ("credit", "insufficient", "quota", "balance"))


class AllKeysExhausted(RuntimeError):
    pass


def chat(messages: list[dict], model: str | None = None, temperature: float = 0,
         timeout: int = 120, max_retries: int = 3) -> str:
    """Chat-Completion mit Key-Rotation. Gibt den Antworttext zurück; wirft bei totalem Ausfall.

    Wechselt bei leerem Guthaben (402/Kredit-Fehler) sofort auf den nächsten Key; bei 429/Netzfehler
    kurzer Backoff und Retry, dann nächster Key.
    """
    model = model or DEFAULT_MODEL
    keys = [k for k in _load_keys() if k not in _EXHAUSTED]
    if not keys:
        raise AllKeysExhausted("Keine OpenRouter-Keys verfügbar (alle leer/402 oder keiner hinterlegt).")
    body = {"model": model, "temperature": temperature, "messages": messages}
    last_err = "?"
    for key in keys:
        for attempt in range(max_retries):
            try:
                r = requests.post(URL, headers={"Authorization": f"Bearer {key}",
                                  "Content-Type": "application/json"}, json=body, timeout=timeout)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"]
                if _is_credit_error(r.status_code, r.text):
                    with _LOCK:
                        _EXHAUSTED.add(key)
                    last_err = f"402/Guthaben leer (…{key[-6:]})"
                    break                       # dieser Key ist durch → nächster Key
                if r.status_code == 429:
                    last_err = "429 Rate-Limit"
                    time.sleep(2 * (attempt + 1))
                    continue                    # gleicher Key nochmal, dann nächster
                last_err = f"HTTP {r.status_code}: {r.text[:120]}"
            except Exception as e:              # Netz/Timeout → Retry
                last_err = f"{type(e).__name__}: {str(e)[:80]}"
                time.sleep(2 * (attempt + 1))
    raise AllKeysExhausted(f"Alle {len(keys)} Keys fehlgeschlagen — zuletzt: {last_err}")
