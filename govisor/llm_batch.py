"""OpenRouters Stapelweg — halber Preis, dafuer Wartezeit.

**Warum.** Die Analyse ist der groesste laufende Posten: 0,045 $ je Vorgang, und bei einer
offenen Beschaffungsluecke von ~5.983 Vergaben waeren das ~271 $. Ueber den Stapel kostet
dasselbe Modell **die Haelfte** (gemini-2.5-flash: 0,15 statt 0,30 $/Mio Eingabe, 1,25 statt
2,50 Ausgabe — gemessen an der Modellliste am 2026-08-22).

⚠ **`:batch` ist KEIN Modellname.** Der Anhang taucht in der Modellliste auf, ueber den
normalen Chat-Endpunkt antwortet er mit HTTP 404. Der Rabatt haengt am ENDPUNKT, nicht am
Namen: hier wird der gewoehnliche Slug geschickt.

⚠ **Und es ist kein „etwas langsamer".** Das Fenster ist **24 Stunden**; ein Stapel mit zwei
Trivialanfragen stand nach sieben Minuten noch auf `in_progress`. Wer den Stapelweg wie einen
synchronen Aufruf benutzt, baut eine Schleife, die stundenlang wartet. Deshalb trennt dieses
Modul strikt: absenden, weggehen, spaeter abholen. Der Zustand liegt auf der Platte, damit
ein Neustart des Arbeiters nichts verliert.

Endpunkt: ``https://openrouter.ai/api/beta/batches`` (BETA, nicht ``v1`` — auf ``v1`` liefert
OpenRouter eine HTML-Seite, was beim Abtasten wie ein 404 aussieht).
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

BASIS = "https://openrouter.ai/api/beta/batches"
ROOT = Path(__file__).resolve().parent.parent
LAGER = ROOT / "data" / ".llm_batches"
# Ein Stapel darf nicht beliebig gross werden: bei einem Fehlschlag ist alles darin verloren,
# und das Lager haelt die Zuordnung im Speicher.
MAX_JE_STAPEL = int(os.environ.get("GOVISOR_BATCH_MAX", "200"))


def _schluessel() -> str:
    """Derselbe Schluesselweg wie `chat()` — nicht ein zweiter daneben.

    ⚠ Hier stand bis zum 2026-08-25 eine eigene Suche ueber `OPENROUTER_API_KEY` und
    `.secrets/openrouter.key`. Das ist NICHT der dokumentierte Weg (`OPENROUTER_KEYS`,
    `.secrets/openrouter.keys`, s. Modulkopf von `llm`), sondern ein dritter, der bei
    jeder Schluesselumstellung als Erster stillsteht. Es gab drei solcher Kopien;
    `llm.kontostand()` war die teuerste, weil an ihr die Geldwache haengt.
    """
    from .llm import _load_keys
    return next(iter(_load_keys()), "")


def _ruf(args: list[str], eingabe: str | None = None, frist: int = 120) -> dict:
    r = subprocess.run(args, input=eingabe, capture_output=True, text=True, timeout=frist)
    try:
        return json.loads(r.stdout)
    except Exception:                                         # noqa: BLE001
        return {"_fehler": (r.stdout or r.stderr)[:300]}


def absenden(anfragen: list[dict], modell: str, merkzettel: dict | None = None) -> str | None:
    """``[{custom_id, messages}]`` → Stapel-ID. Legt den Merkzettel neben die ID.

    Der Merkzettel haelt fest, wofuer jede ``custom_id`` steht (Vorgang, Doktyp, der Text,
    gegen den die Zitate geprueft werden). Ohne ihn ist ein Ergebnis, das Stunden spaeter
    eintrifft, nicht mehr zuzuordnen.
    """
    if not anfragen:
        return None
    if len(anfragen) > MAX_JE_STAPEL:
        raise ValueError(f"{len(anfragen)} Anfragen — Obergrenze {MAX_JE_STAPEL}")
    koerper = {"endpoint": "/v1/chat/completions", "model": modell,
               "requests": [{"custom_id": a["custom_id"], "body": {"messages": a["messages"]}}
                            for a in anfragen]}
    d = _ruf(["curl", "-s", "--max-time", "180", BASIS,
              "-H", "Content-Type: application/json",
              "-H", f"Authorization: Bearer {_schluessel()}",
              "-d", "@-"], eingabe=json.dumps(koerper), frist=200)
    sid = d.get("id")
    if not sid:
        return None
    LAGER.mkdir(parents=True, exist_ok=True)
    (LAGER / f"{sid}.json").write_text(json.dumps({
        "id": sid, "modell": modell, "abgesendet": time.time(),
        "n": len(anfragen), "merkzettel": merkzettel or {}}, ensure_ascii=False),
        encoding="utf-8")
    return sid


def abfragen(sid: str) -> dict:
    """Status und — wenn fertig — die Ergebnisse. Beides kommt in EINER Antwort."""
    return _ruf(["curl", "-s", "--max-time", "120",
                 "-H", f"Authorization: Bearer {_schluessel()}", f"{BASIS}/{sid}"])


def offene() -> list[dict]:
    """Alle abgesendeten, noch nicht abgeholten Stapel — aelteste zuerst."""
    if not LAGER.exists():
        return []
    aus = []
    for p in LAGER.glob("*.json"):
        try:
            aus.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:                                     # noqa: BLE001
            continue
    return sorted(aus, key=lambda x: x.get("abgesendet", 0))


def erledigt(sid: str) -> None:
    """Stapel aus dem Lager nehmen — erst NACHDEM das Ergebnis gesichert ist."""
    (LAGER / f"{sid}.json").unlink(missing_ok=True)


def antworten(d: dict) -> dict[str, str]:
    """``custom_id`` → Rohtext der Antwort. Fehlgeschlagene Einzelanfragen fehlen einfach."""
    aus = {}
    for r in d.get("results") or []:
        koerper = (r.get("response") or {}).get("body") or {}
        wahl = (koerper.get("choices") or [{}])[0]
        inhalt = (wahl.get("message") or {}).get("content")
        if inhalt is not None:
            aus[r.get("custom_id")] = inhalt
    return aus
